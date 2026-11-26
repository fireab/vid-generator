"""Assembly stage.

--mode radio : narration over black 16:9 (User Test #1)
--mode film  : Phase 3 production export
    1. voice track: per-shot narration at frame-exact shot timings (+3 s end-card silence)
    2. score looped/trimmed to film + end card, ducked with sidechaincompress, faded
    3. 2-pass loudnorm -> -14 LUFS integrated, -1 dBTP
    4. outputs/subtitles.srt from subtitle_en timed to real narration length (<=2 lines x ~40 chars)
    5. 3 s AI-disclosure end card
    6. outputs/final_16x9.mp4 (1920x1080) and outputs/final_9x16.mp4 (1080x1920), burned-in subs,
       H.264 / AAC / 24 fps
All timing comes from media.shot_frames() so picture, voice, subs and music stay frame-aligned.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from media import (FPS, H, SR, W, ffmpeg, narration_path, require_ffmpeg, shot_frames,
                   wav_duration)
from utils import OUTPUTS, ROOT, Timer, log_run, validate_storyboard

TMP = OUTPUTS / "tmp_assemble"
END_CARD_SEC = 3.0
LINE_CHARS, MAX_LINES = 40, 2
TARGET_LUFS, TARGET_TP, TARGET_LRA = -14.0, -1.0, 11.0
DUCK = {"threshold": 0.02, "ratio": 6, "attack": 300, "release": 1500}
MUSIC_GAIN_DB = -6.0  # pre-duck bed level relative to narration
VW, VH = 1080, 1920   # vertical export


# ------------------------------------------------------------------ helpers
def _font() -> tuple[str, str]:
    """(family name for libass, file path for drawtext)."""
    for fam in ("Inter", "Noto Sans", "DejaVu Sans", "Liberation Sans", "sans-serif"):
        try:
            out = subprocess.run(["fc-match", "-f", "%{family[0]}|%{file}", fam],
                                 capture_output=True, text=True, check=True).stdout
            name, path = out.split("|", 1)
            if Path(path).exists():
                return name, path
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("No usable font found (install fonts-dejavu)")


def _shot_timeline(sb: dict) -> list[tuple[dict, float, float]]:
    """[(shot, start_sec, dur_sec)] using frame-exact durations."""
    t, rows = 0.0, []
    for shot in sb["shots"]:
        d = shot_frames(shot) / FPS
        rows.append((shot, t, d))
        t += d
    return rows


def _voice_track(sb: dict, tail: float = 0.0) -> tuple[Path, float]:
    """Concatenate per-shot narration padded/trimmed to exact shot lengths, plus `tail` silence."""
    segs, total = [], 0.0
    for shot, _, d in _shot_timeline(sb):
        sid = shot["id"]
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
    if tail > 0:
        seg = TMP / "tail.wav"
        ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{tail:.4f}", str(seg)])
        segs.append(seg)
        total += tail
    lst = TMP / "voice.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    voice = TMP / "voice.wav"
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(voice)])
    return voice, total


# -------------------------------------------------------------------- audio
def _duck_filter(total: float, voice_in: str = "1:a", music_in: str = "2:a") -> str:
    d = DUCK
    return (f"[{voice_in}]aresample={SR},aformat=channel_layouts=stereo,asplit[v1][v2];"
            f"[{music_in}]aresample={SR},aformat=channel_layouts=stereo,volume={MUSIC_GAIN_DB}dB,"
            f"atrim=0:{total:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d=1.5,afade=t=out:st={max(0, total - END_CARD_SEC):.3f}:d={END_CARD_SEC}[m0];"
            f"[m0][v1]sidechaincompress=threshold={d['threshold']}:ratio={d['ratio']}:"
            f"attack={d['attack']}:release={d['release']}[m];"
            f"[v2][m]amix=inputs=2:duration=first:normalize=0[a]")


def _mix(voice: Path, music: Path | None, total: float) -> Path:
    pre = TMP / "mix_pre.wav"
    if music and music.exists():
        ffmpeg(["-i", str(voice), "-stream_loop", "-1", "-i", str(music),
                "-filter_complex", _duck_filter(total, "0:a", "1:a"), "-map", "[a]",
                "-t", f"{total:.4f}", "-ar", str(SR), str(pre)])
    else:
        print("  [warn] no music; narration only")
        ffmpeg(["-i", str(voice), "-ac", "2", "-ar", str(SR), str(pre)])
    return pre


def _loudnorm(src: Path, dst: Path) -> dict:
    """Two-pass EBU R128 normalization. Returns pass-1 measurements + pass-2 output stats."""
    base = f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}"
    p1 = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af",
                         f"{base}:print_format=json", "-f", "null", "-"],
                        capture_output=True, text=True, check=True)
    m = json.loads(re.findall(r"\{[^{}]+\}", p1.stderr)[-1])
    af = (f"{base}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
          f"offset={m['target_offset']}:linear=true:print_format=json")
    p2 = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(src), "-af", af,
                         "-ar", str(SR), "-ac", "2", str(dst)],
                        capture_output=True, text=True, check=True)
    m2 = json.loads(re.findall(r"\{[^{}]+\}", p2.stderr)[-1])
    return {"pass1": m, "pass2": m2}


def _measure(path: Path) -> dict:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                        f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    m = json.loads(re.findall(r"\{[^{}]+\}", p.stderr)[-1])
    return {"lufs": float(m["input_i"]), "true_peak": float(m["input_tp"])}


# ---------------------------------------------------------------- subtitles
def _cues(sb: dict) -> list[tuple[float, float, list[str]]]:
    """Split each subtitle into <=2-line chunks and spread them across the real narration span."""
    cues = []
    for shot, start, d in _shot_timeline(sb):
        text = " ".join(shot["subtitle_en"].split())
        if not text:
            continue
        lines = textwrap.wrap(text, LINE_CHARS, break_long_words=False)
        chunks = [lines[i:i + MAX_LINES] for i in range(0, len(lines), MAX_LINES)]
        p = narration_path(shot["id"])
        speech = wav_duration(p) if p.exists() else max(1.0, d - 0.3)
        t0, t_end = start + 0.05, min(start + d - 0.05, start + speech + 0.25)
        span, total_chars = t_end - t0, sum(len(" ".join(c)) for c in chunks)
        t = t0
        for c in chunks:
            dur = span * len(" ".join(c)) / total_chars
            cues.append((t, t + dur, c))
            t += dur
    return cues


def _srt(cues, path: Path) -> None:
    def ts(s: float) -> str:
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    path.write_text("\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n" + "\n".join(ls) + "\n"
                              for i, (a, b, ls) in enumerate(cues, 1)), encoding="utf-8")


def _ass(cues, path: Path, w: int, h: int, font: str, size: int, margin_v: int, margin_lr: int) -> None:
    def ts(s: float) -> str:
        cs = int(round(s * 100))
        return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"
    esc = lambda s: s.replace("\\", "/").replace("{", "(").replace("}", ")")
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H000000FF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,{max(2, size // 18)},1,2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = "".join(f"Dialogue: 0,{ts(a)},{ts(b)},Default,,0,0,0,,{r'\N'.join(esc(x) for x in ls)}\n"
                   for a, b, ls in cues)
    path.write_text(head + body, encoding="utf-8")


# ----------------------------------------------------------------- end card
def _end_card(title: str, w: int, h: int, font_file: str, out: Path) -> None:
    text = f"Created with AI — {title}"
    txt = TMP / f"endcard_{w}x{h}.txt"
    txt.write_text(text, encoding="utf-8")
    size = min(int(h * 0.045), int(w * 1.7 / max(len(text), 1)))
    fade = 0.6
    vf = (f"drawtext=fontfile='{font_file}':textfile='{txt}':fontsize={size}:fontcolor=white@0.92:"
          f"x=(w-text_w)/2:y=(h-text_h)/2,"
          f"fade=t=in:st=0:d={fade},fade=t=out:st={END_CARD_SEC - fade}:d={fade},format=yuv420p")
    ffmpeg(["-f", "lavfi", "-i", f"color=c=0x0b0b0d:s={w}x{h}:r={FPS}:d={END_CARD_SEC}", "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(out)])


# ------------------------------------------------------------------ exports
def _export(concat_list: Path, end_card: Path, ass: Path, audio: Path, out: Path, total: float,
            vertical: bool) -> None:
    if vertical:  # center-crop 16:9 -> 9:16 (subjects are prompted centered), upscale
        pre = f"[0:v]crop=ih*9/16:ih,scale={VW}:{VH}:flags=lanczos,setsar=1,fps={FPS}[s];"
    else:
        pre = f"[0:v]scale={W}:{H},setsar=1,fps={FPS}[s];"
    fc = (pre + f"[1:v]setsar=1,fps={FPS}[e];[s][e]concat=n=2:v=1:a=0[c];"
          f"[c]ass='{ass}',format=yuv420p[v]")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-i", str(end_card), "-i", str(audio),
            "-filter_complex", fc, "-map", "[v]", "-map", "2:a",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "18", "-r", str(FPS),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
            "-t", f"{total:.4f}", "-movflags", "+faststart", str(out)])


def radio(sb: dict, music: Path | None = None) -> Path:
    require_ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    voice, total = _voice_track(sb)
    mix = _mix(voice, music, total)
    out = OUTPUTS / "radio_cut.mp4"
    t = Timer()
    with t:
        ffmpeg(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={total:.4f}", "-i", str(mix),
                "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)])
    log_run(stage="assemble", shot_id=None, model="ffmpeg",
            params={"mode": "radio", "music": str(music) if music else None},
            latency_ms=t.ms, duration_sec=round(total, 2))
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"  wrote {out.relative_to(ROOT)} ({total:.1f}s)")
    return out


def film(sb: dict, music: Path | None = None) -> dict[str, Path]:
    require_ffmpeg()
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)
    clips = [OUTPUTS / "shots" / f"{s['id']}.mp4" for s in sb["shots"]]
    if missing := [c.name for c in clips if not c.exists()]:
        raise FileNotFoundError(f"missing shot clips {missing} — run the shots stage first")
    font_name, font_file = _font()
    t = Timer()
    with t:
        # audio
        voice, total = _voice_track(sb, tail=END_CARD_SEC)
        mix = TMP / "mix.wav"
        ln = _loudnorm(_mix(voice, music, total), mix)
        # subtitles
        cues = _cues(sb)
        srt = OUTPUTS / "subtitles.srt"
        _srt(cues, srt)
        ass_h, ass_v = TMP / "subs_16x9.ass", TMP / "subs_9x16.ass"
        _ass(cues, ass_h, W, H, font_name, size=50, margin_v=70, margin_lr=160)
        # vertical: keep subs above Reels/TikTok/Shorts bottom UI (~bottom 20-25%) and off right rail
        _ass(cues, ass_v, VW, VH, font_name, size=46, margin_v=470, margin_lr=90)
        # end cards
        ec_h, ec_v = TMP / "endcard_16x9.mp4", TMP / "endcard_9x16.mp4"
        _end_card(sb["title"], W, H, font_file, ec_h)
        _end_card(sb["title"], VW, VH, font_file, ec_v)
        # picture
        lst = TMP / "shots.txt"
        lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
        out_h, out_v = OUTPUTS / "final_16x9.mp4", OUTPUTS / "final_9x16.mp4"
        _export(lst, ec_h, ass_h, mix, out_h, total, vertical=False)
        _export(lst, ec_v, ass_v, mix, out_v, total, vertical=True)
    meas = _measure(out_h)
    log_run(stage="assemble", shot_id=None, model="ffmpeg",
            params={"mode": "film", "music": str(music) if music else None, "duck": DUCK,
                    "target_lufs": TARGET_LUFS, "target_tp": TARGET_TP, "end_card_sec": END_CARD_SEC,
                    "subtitle_cues": len(cues)},
            latency_ms=t.ms, duration_sec=round(total, 2),
            loudness_in={"lufs": float(ln["pass1"]["input_i"]), "tp": float(ln["pass1"]["input_tp"])},
            loudness_out=meas)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"  wrote {out_h.relative_to(ROOT)}, {out_v.relative_to(ROOT)}, {srt.relative_to(ROOT)} "
          f"({total:.2f}s, {meas['lufs']:.1f} LUFS, {meas['true_peak']:.1f} dBTP)")
    return {"16x9": out_h, "9x16": out_v, "srt": srt}


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
