"""Music stage: use the chosen ACE-Step 1.5 score if present, else a placeholder ambient bed."""
from __future__ import annotations

from pathlib import Path

from media import SR, ffmpeg, file_hash, require_ffmpeg, shot_seconds
from utils import OUTPUTS, Timer, cache_lookup, cache_store, input_hash, log_run, validate_storyboard

STAGE = "music"
OUT_DIR = OUTPUTS / "music"
SCORE_CANDIDATES = [OUT_DIR / "score.wav", OUT_DIR / "score.mp3"]
ACE_MODEL = "ace-step-1.5 (kaggle)"
BED_MODEL = "ffmpeg-ambient-bed"


def _bed(out: Path, d: float) -> None:
    # A-minor-ish drone: slowly breathing partials + filtered pink noise + room echo, faded.
    def partial(f, a, lfo, ph):
        return f"{a}*sin(2*PI*{f}*t)*(0.6+0.4*sin(2*PI*{lfo}*t+{ph}))"
    tone = "+".join([partial(110, 0.10, 0.05, 0), partial(164.81, 0.07, 0.07, 1),
                     partial(220, 0.05, 0.03, 2), partial(261.63, 0.03, 0.045, 3),
                     partial(329.63, 0.02, 0.06, 4)])
    fc = (f"aevalsrc='{tone}':s={SR}:d={d:.3f}[t];"
          f"anoisesrc=color=pink:amplitude=0.03:r={SR}:d={d:.3f},lowpass=f=600[n];"
          f"[t][n]amix=inputs=2:normalize=0,aecho=0.8:0.7:120|240:0.25|0.15,"
          f"lowpass=f=2500,afade=t=in:d=3,afade=t=out:st={max(0, d - 4):.3f}:d=4,"
          f"pan=stereo|c0=c0|c1=c0,alimiter=limit=0.5[a]")
    ffmpeg(["-filter_complex", fc, "-map", "[a]", "-ar", str(SR), str(out)])


def run(sb: dict | None = None, only: set[str] | None = None) -> Path:
    require_ffmpeg()
    sb = sb or validate_storyboard()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = round(sum(shot_seconds(s) for s in sb["shots"]), 3)

    for p in SCORE_CANDIDATES:
        if p.exists() and p.stat().st_size > 0:
            log_run(stage=STAGE, shot_id=None, model=ACE_MODEL, cache_hit=True,
                    params={"path": p.name, "sha256": file_hash(p), "music_cue": sb["music_cue"]})
            print(f"  [score] using {p.name}")
            return p

    inputs = {"stage": STAGE, "model": BED_MODEL, "duration": total, "version": 1}
    h = input_hash(inputs)
    out = OUT_DIR / "placeholder_bed.wav"
    params = {"duration": total, "input_hash": h}
    if (c := cache_lookup(STAGE, "bed", h)):
        log_run(stage=STAGE, shot_id=None, model=BED_MODEL, params=params, cache_hit=True)
        print("  [cache] placeholder bed")
        return c
    t = Timer()
    with t:
        _bed(out, total)
    cache_store(STAGE, "bed", h, out)
    log_run(stage=STAGE, shot_id=None, model=BED_MODEL, params=params, latency_ms=t.ms,
            status="fallback", error="no ACE-Step score found; generated placeholder bed")
    print(f"  [warn]  no score.wav/mp3 — generated placeholder bed ({total:.1f}s)")
    return out


if __name__ == "__main__":
    run()
