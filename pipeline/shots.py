"""Shots stage: per-shot 1920x1080@24fps clip, frame-matched to narration length.

- motion_mode "wan":       use Kaggle clip outputs/shots/<id>_wan.mp4 if valid, else fall back to Ken Burns.
- motion_mode "ken_burns": FFmpeg zoompan over outputs/keyframes/<id>.png with eased, varied motion.
Final clips: outputs/shots/<id>.mp4 (cached by hash of source file + timing + motion).
"""
from __future__ import annotations

import sys
from pathlib import Path

from media import FPS, H, W, ffmpeg, ffprobe, file_hash, require_ffmpeg, shot_frames
from utils import (OUTPUTS, Timer, cache_lookup, cache_store, input_hash, log_run,
                   validate_storyboard)

STAGE = "shots"
OUT_DIR = OUTPUTS / "shots"
KF_DIR = OUTPUTS / "keyframes"
WAN_MODEL = "wan2.2-ti2v-5b (kaggle)"
KB_MODEL = "ffmpeg-zoompan"
MOTIONS = ["zoom_in", "pan_right", "zoom_out", "tilt_down", "pan_left", "drift_in", "tilt_up"]
KEYWORDS = [  # motion_prompt keyword -> Ken Burns motion
    (("push-in", "push in", "zoom in", "close in"), "zoom_in"),
    (("pull-out", "pull out", "zoom out", "pull back"), "zoom_out"),
    (("pan right", "drift right", "track right"), "pan_right"),
    (("pan left", "drift left", "track left"), "pan_left"),
    (("tilt down",), "tilt_down"),
    (("tilt up", "rise", "crane up"), "tilt_up"),
]


def pick_motion(shot: dict, idx: int, prev: str | None) -> str:
    mp = shot["motion_prompt"].lower()
    for keys, motion in KEYWORDS:
        if any(k in mp for k in keys):
            return motion
    m = MOTIONS[(shot["seed"] + idx) % len(MOTIONS)]
    return MOTIONS[(MOTIONS.index(m) + 1) % len(MOTIONS)] if m == prev else m


def zoompan_expr(motion: str, n: int) -> str:
    e = f"(3*pow(on/{n},2)-2*pow(on/{n},3))"  # smoothstep easing 0->1
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z, x, y = {
        "zoom_in":   (f"1.0+0.15*{e}", cx, cy),
        "zoom_out":  (f"1.15-0.15*{e}", cx, cy),
        "pan_right": ("1.12", f"(iw-iw/zoom)*(0.15+0.7*{e})", cy),
        "pan_left":  ("1.12", f"(iw-iw/zoom)*(0.85-0.7*{e})", cy),
        "tilt_down": ("1.12", cx, f"(ih-ih/zoom)*(0.15+0.7*{e})"),
        "tilt_up":   ("1.12", cx, f"(ih-ih/zoom)*(0.85-0.7*{e})"),
        "drift_in":  (f"1.04+0.1*{e}", f"(iw-iw/zoom)*(0.4+0.2*{e})", cy),
    }[motion]
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS}"


def ken_burns(png: Path, out: Path, motion: str, n: int) -> None:
    # Center-crop to 16:9 (subject is centered by prompt), upscale 2x for sub-pixel smoothness.
    vf = (f"crop='min(iw,ih*16/9)':'min(ih,iw*9/16)',scale={W * 2}:{H * 2}:flags=lanczos,"
          f"{zoompan_expr(motion, n)},format=yuv420p")
    ffmpeg(["-i", str(png), "-vf", vf, "-frames:v", str(n), "-r", str(FPS), "-c:v", "libx264",
            "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(out)])


def validate_wan(p: Path) -> str | None:
    """Return None if usable, else a reason string."""
    if not p.exists():
        return "missing"
    try:
        info = ffprobe(p)
    except Exception as e:  # noqa: BLE001
        return f"ffprobe failed: {e}"
    v = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not v:
        return "no video stream"
    if float(info.get("format", {}).get("duration", 0)) < 1.0:
        return "duration < 1s"
    return None


def conform_wan(src: Path, out: Path, n: int) -> None:
    """Scale/crop to 1920x1080, 24fps, hold last frame if short, trim to exactly n frames."""
    d = n / FPS
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
          f"fps={FPS},tpad=stop_mode=clone:stop_duration={d:.3f},format=yuv420p")
    ffmpeg(["-i", str(src), "-vf", vf, "-frames:v", str(n), "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-an", str(out)])


def run(sb: dict | None = None, only: set[str] | None = None) -> dict[str, Path]:
    require_ffmpeg()
    sb = sb or validate_storyboard()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results, prev = {}, None
    for idx, shot in enumerate(sb["shots"]):
        sid = shot["id"]
        motion = pick_motion(shot, idx, prev)
        prev = motion
        if only and sid not in only:
            continue
        n = shot_frames(shot)
        wan_src = OUT_DIR / f"{sid}_wan.mp4"
        png = KF_DIR / f"{sid}.png"
        mode, fallback_reason = "ken_burns", None
        if shot["motion_mode"] == "wan":
            fallback_reason = validate_wan(wan_src)
            if fallback_reason is None:
                mode = "wan"
        src = wan_src if mode == "wan" else png
        if not src.exists():
            raise FileNotFoundError(f"{sid}: source {src} missing — run keyframes stage first")
        model = WAN_MODEL if mode == "wan" else KB_MODEL
        inputs = {"stage": STAGE, "mode": mode, "src_sha256": file_hash(src), "frames": n,
                  "fps": FPS, "size": f"{W}x{H}", "motion": motion if mode == "ken_burns" else None}
        h = input_hash(inputs)
        params = {"mode": mode, "frames": n, "motion": inputs["motion"], "input_hash": h}
        if fallback_reason:
            msg = f"wan clip {wan_src.name} {fallback_reason}; fell back to ken_burns"
            print(f"  [warn]  {sid}: {msg}")
            log_run(stage=STAGE, shot_id=sid, model=WAN_MODEL, params=params, seed=shot["seed"],
                    status="fallback", error=msg)
        out = OUT_DIR / f"{sid}.mp4"
        if (c := cache_lookup(STAGE, sid, h)):
            log_run(stage=STAGE, shot_id=sid, model=model, params=params, seed=shot["seed"], cache_hit=True)
            print(f"  [cache] {sid} ({mode})")
            results[sid] = c
            continue
        t = Timer()
        try:
            with t:
                (conform_wan(src, out, n) if mode == "wan" else ken_burns(src, out, motion, n))
            cache_store(STAGE, sid, h, out)
            log_run(stage=STAGE, shot_id=sid, model=model, params=params, seed=shot["seed"], latency_ms=t.ms)
            print(f"  [gen]   {sid} ({mode}{'/' + motion if mode == 'ken_burns' else ''}, "
                  f"{n / FPS:.2f}s, {t.ms:.0f} ms)")
            results[sid] = out
        except Exception as e:  # noqa: BLE001
            log_run(stage=STAGE, shot_id=sid, model=model, params=params, seed=shot["seed"],
                    latency_ms=t.ms, status="error", error=repr(e))
            raise
    return results


if __name__ == "__main__":
    run(only=set(sys.argv[1:]) or None)
