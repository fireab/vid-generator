"""Narration stage: one Gemini TTS WAV per shot, cached by input hash."""
from __future__ import annotations

import sys
from pathlib import Path

from gemini_tts import TTS_MODEL, get_client, tts_to_wav
from utils import (OUTPUTS, Timer, cache_lookup, cache_store, input_hash, load_env,
                   log_run, validate_storyboard, with_retry)

STAGE = "narration"
OUT_DIR = OUTPUTS / "narration"
# Rough estimate: Gemini 2.5 Flash TTS ~ $10 / 1M audio output tokens, ~25 tokens/sec audio.
USD_PER_AUDIO_SEC = 25 * 10 / 1_000_000


def shot_inputs(sb: dict, shot: dict) -> dict:
    return {
        "stage": STAGE,
        "model": TTS_MODEL,
        "text": shot["narration_text"],
        "voice": sb["tts_voice"],
        "style": sb["tts_style"],
        "language": sb["language"],
    }


def narration_path(shot_id: str) -> Path:
    return OUT_DIR / f"{shot_id}.wav"


def run(sb: dict | None = None, only: set[str] | None = None) -> dict[str, Path]:
    load_env()
    sb = sb or validate_storyboard()
    client = None
    results: dict[str, Path] = {}
    for shot in sb["shots"]:
        sid = shot["id"]
        if only and sid not in only:
            continue
        inputs = shot_inputs(sb, shot)
        h = input_hash(inputs)
        params = {k: inputs[k] for k in ("voice", "style", "language")} | {"input_hash": h}
        cached = cache_lookup(STAGE, sid, h)
        if cached:
            log_run(stage=STAGE, shot_id=sid, model=TTS_MODEL, params=params, cache_hit=True)
            print(f"  [cache] {sid}")
            results[sid] = cached
            continue
        if not shot["narration_text"].strip():
            print(f"  [skip] {sid}: empty narration")
            continue
        client = client or get_client()
        out = narration_path(sid)
        t = Timer()
        try:
            with t:
                dur = with_retry(max_attempts=5)(tts_to_wav)(
                    client, shot["narration_text"], sb["tts_voice"], sb["tts_style"], out)
            cache_store(STAGE, sid, h, out)
            log_run(stage=STAGE, shot_id=sid, model=TTS_MODEL, params=params, latency_ms=t.ms,
                    estimated_usd=dur * USD_PER_AUDIO_SEC, audio_sec=round(dur, 2))
            print(f"  [gen]   {sid} ({dur:.1f}s audio, {t.ms:.0f} ms)")
            if dur > shot["duration_sec"] + 0.5:
                print(f"  [warn]  {sid}: narration {dur:.1f}s exceeds duration_sec {shot['duration_sec']}")
            results[sid] = out
        except Exception as e:  # noqa: BLE001
            log_run(stage=STAGE, shot_id=sid, model=TTS_MODEL, params=params, latency_ms=t.ms,
                    status="error", error=repr(e))
            raise
    return results


if __name__ == "__main__":
    only = set(sys.argv[1:]) or None
    run(only=only)
