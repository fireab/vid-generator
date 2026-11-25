"""Shared media helpers: frame-accurate shot timing, ffmpeg/ffprobe wrappers, file hashing."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path

from utils import OUTPUTS

FPS = 24
W, H = 1920, 1080
SR = 48000
NARRATION_DIR = OUTPUTS / "narration"
TAIL_PAD = 0.3  # seconds of air after each narration line


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg/ffprobe not found on PATH")


def ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def wav_duration(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def file_hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def narration_path(shot_id: str) -> Path:
    return NARRATION_DIR / f"{shot_id}.wav"


def shot_frames(shot: dict) -> int:
    """Frame count for a shot: max(duration_sec, narration + tail pad), snapped to whole frames."""
    d = float(shot["duration_sec"])
    p = narration_path(shot["id"])
    if p.exists():
        d = max(d, wav_duration(p) + TAIL_PAD)
    return max(1, round(d * FPS))


def shot_seconds(shot: dict) -> float:
    return shot_frames(shot) / FPS
