"""Assembly stage.

--mode radio : narration over black 16:9 (User Test #1)
--mode film  : shot clips + narration + ducked music + soft English subtitles -> outputs/film.mp4
Both modes use media.shot_frames() so every shot segment is frame-identical across modes.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from media import FPS, H, SR, W, ffmpeg, narration_path, require_ffmpeg, shot_frames
from utils import OUTPUTS, ROOT, Timer, log_run, validate_storyboard

TMP = OUTPUTS / "tmp_assemble"


def _voice_track(sb: dict) -> tuple[Path, float]:
    """Concatenate per-shot narration, each padded/trimmed to its exact frame-aligned length."""
    segs, total = [], 0.0
    for shot in sb["shots"]:
        sid, d = shot["id"], shot_frames(shot) / FPS
        seg = TMP / f"{sid}.wav"
        src = narration_path(sid)
        if src.exists():
            ffmpeg(["-i", str(src), "-af", f"aresample={SR},apad,atrim=0:{d:.4f}",
                    "-ac", "1", "-ar", str(SR), str(seg)])
        else:
            print(f"  [warn] missing narration for {sid}; inserting {d:.2f}s silence")
            ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{d:.4f}", str(seg)])
        segs.append(seg)
        total += d
    lst = TMP / "voice.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    voice = TMP / "voice.wav"
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(voice)])
    return voice, total


def _srt(sb: dict, path: Path) -> None:
    def ts(s: float) -> str:
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    t, lines, n = 0.0, [], 1
    for shot in sb["shots"]:
        d = shot_frames(shot) / FPS
        if shot["subtitle_en"].strip():
            lines.append(f"{n}\n{ts(t + 0.1)} --> {ts(t + d - 0.2)}\n{shot['subtitle_en'].strip()}\n")
            n += 1
        t += d
    path.write_text("\n".join(lines), encoding="utf-8")


def _music_filter(total: float, music_db: float) -> str:
    # Duck music under narration with a sidechain compressor.
    return (f"[1:a]aresample={SR},aformat=channel_layouts=stereo,asplit[v1][v2];"
            f"[2:a]aresample={SR},aformat=channel_layouts=stereo,volume={music_db}dB,"
            f"atrim=0:{total:.4f},afade=t=out:st={max(0, total - 3):.3f}:d=3[m0];"
            f"[m0][v1]sidechaincompress=threshold=0.03:ratio=8:attack=40:release=700[m];"
            f"[v2][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")


def radio(sb: dict, music: Path | None = None, music_db: float = -18.0) -> Path:
    require_ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    voice, total = _voice_track(sb)
    out = OUTPUTS / "radio_cut.mp4"
    inputs = ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={total:.4f}", "-i", str(voice)]
    if music and music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        maps = ["-filter_complex", _music_filter(total, music_db), "-map", "0:v", "-map", "[a]"]
    else:
        maps = ["-map", "0:v", "-map", "1:a"]
    t = Timer()
    with t:
        ffmpeg([*inputs, *maps, "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)])
    log_run(stage="assemble", shot_id=None, model="ffmpeg",
            params={"mode": "radio", "music": str(music) if music else None},
            latency_ms=t.ms, duration_sec=round(total, 2))
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"  wrote {out.relative_to(ROOT)} ({total:.1f}s)")
    return out


def film(sb: dict, music: Path | None = None, music_db: float = -14.0) -> Path:
    require_ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    clips = []
    for shot in sb["shots"]:
        c = OUTPUTS / "shots" / f"{shot['id']}.mp4"
        if not c.exists():
            raise FileNotFoundError(f"missing {c} — run the shots stage first")
        clips.append(c)
    vlist = TMP / "video.txt"
    vlist.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    video = TMP / "video.mp4"
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(vlist), "-c", "copy", str(video)])
    voice, total = _voice_track(sb)
    srt = OUTPUTS / "film.en.srt"
    _srt(sb, srt)

    out = OUTPUTS / "film.mp4"
    inputs = ["-i", str(video), "-i", str(voice)]
    if music and music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music), "-i", str(srt)]
        amap = ["-filter_complex", _music_filter(total, music_db), "-map", "[a]"]
        sub_idx = 3
    else:
        inputs += ["-i", str(srt)]
        amap = ["-map", "1:a"]
        sub_idx = 2
    t = Timer()
    with t:
        ffmpeg([*inputs, "-map", "0:v", *amap, "-map", f"{sub_idx}:s", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
                "-t", f"{total:.4f}", "-movflags", "+faststart", str(out)])
    log_run(stage="assemble", shot_id=None, model="ffmpeg",
            params={"mode": "film", "music": str(music) if music else None},
            latency_ms=t.ms, duration_sec=round(total, 2))
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"  wrote {out.relative_to(ROOT)} ({total:.1f}s) + {srt.relative_to(ROOT)}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["radio", "film"], default="radio")
    ap.add_argument("--music", type=Path, help="music track (film mode defaults to music stage output)")
    a = ap.parse_args(argv)
    sb = validate_storyboard()
    if a.mode == "radio":
        radio(sb, a.music)
    else:
        if a.music is None:
            import music
            a.music = music.run(sb)
        film(sb, a.music)
    return 0


if __name__ == "__main__":
    sys.exit(main())
