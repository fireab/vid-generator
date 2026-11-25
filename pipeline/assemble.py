"""Assembly stage. Phase 1: --mode radio (narration over black 16:9)."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from narration import narration_path
from utils import OUTPUTS, ROOT, Timer, log_run, validate_storyboard

W, H, FPS, SR = 1920, 1080, 24, 24000


def _wav_dur(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def _ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    subprocess.run(cmd, check=True)


def radio(sb: dict, music: Path | None = None, music_db: float = -18.0) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH")
    tmp = OUTPUTS / "tmp_radio"
    tmp.mkdir(parents=True, exist_ok=True)
    segs = []
    # Each shot segment = narration padded with silence to max(duration_sec, narration length).
    for shot in sb["shots"]:
        sid = shot["id"]
        src = narration_path(sid)
        seg = tmp / f"{sid}.wav"
        target = float(shot["duration_sec"])
        if src.exists():
            target = max(target, _wav_dur(src) + 0.3)
            _ffmpeg(["-i", str(src), "-af", f"apad,atrim=0:{target:.3f},aresample={SR}",
                     "-ac", "1", "-ar", str(SR), str(seg)])
        else:
            print(f"  [warn] missing narration for {sid}; inserting {target}s silence")
            _ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{target:.3f}", str(seg)])
        segs.append(seg)
    lst = tmp / "concat.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    voice = tmp / "voice.wav"
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(voice)])
    total = _wav_dur(voice)

    out = OUTPUTS / "radio_cut.mp4"
    inputs = ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={total:.3f}", "-i", str(voice)]
    if music and music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        filt = (f"[2:a]volume={music_db}dB,atrim=0:{total:.3f}[m];"
                f"[1:a][m]amix=inputs=2:duration=first:normalize=0[a]")
        maps = ["-filter_complex", filt, "-map", "0:v", "-map", "[a]"]
    else:
        maps = ["-map", "0:v", "-map", "1:a"]
    t = Timer()
    with t:
        _ffmpeg([*inputs, *maps, "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)])
    log_run(stage="assemble", shot_id=None, model="ffmpeg", params={"mode": "radio", "music": str(music) if music else None},
            latency_ms=t.ms, duration_sec=round(total, 2))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"  wrote {out.relative_to(ROOT)} ({total:.1f}s)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["radio", "film"], default="radio")
    ap.add_argument("--music", type=Path, help="optional temp music track")
    a = ap.parse_args(argv)
    sb = validate_storyboard()
    if a.mode == "radio":
        radio(sb, a.music)
    else:
        raise NotImplementedError("film assembly is Phase 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
