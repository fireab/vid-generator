"""Narration stage: one TTS WAV per shot, cached by input hash.

Primary backend: Gemini TTS (`gemini-2.5-flash-preview-tts`).
Automatic fallback on daily quota exhaustion (or when TTS_BACKEND=cloudflare):
Cloudflare Workers AI Deepgram Aura-1 (`@cf/deepgram/aura-1`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

from gemini_tts import SAMPLE_RATE, TTS_MODEL, get_client, tts_to_wav
from media import ffmpeg, narration_path, require_ffmpeg, wav_duration
from utils import (OUTPUTS, Timer, cache_lookup, cache_store, input_hash, load_env,
                   log_run, require_env, validate_storyboard, with_retry)

STAGE = "narration"
OUT_DIR = OUTPUTS / "narration"
CF_TTS_MODEL = "@cf/deepgram/aura-1"
CF_TTS_SPEAKER = os.environ.get("CF_TTS_SPEAKER", "luna")  # warm, calm female narrator
# Rough estimate: Gemini 2.5 Flash TTS ~ $10 / 1M audio output tokens, ~25 tokens/sec audio.
USD_PER_AUDIO_SEC = 25 * 10 / 1_000_000


def _cf_tts_to_wav(text: str, speaker: str, out_path: Path) -> float:
    """Synthesize `text` via Cloudflare Workers AI Deepgram Aura-1 into a 24kHz mono WAV."""
    require_ffmpeg()
    acct = require_env("CLOUDFLARE_ACCOUNT_ID")
    token = require_env("CLOUDFLARE_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{CF_TTS_MODEL}"
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
                      json={"text": text, "speaker": speaker}, timeout=60)
    if r.status_code != 200 or not r.content:
        raise RuntimeError(f"Cloudflare TTS {r.status_code}: {r.text[:300]}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = out_path.with_suffix(".tmp.mp3")
    tmp = out_path.with_suffix(".tmp.wav")
    raw.write_bytes(r.content)
    ffmpeg(["-i", str(raw), "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(tmp)])
    raw.unlink(missing_ok=True)
    tmp.replace(out_path)
    return wav_duration(out_path)


def shot_inputs(sb: dict, shot: dict, model: str = TTS_MODEL) -> dict:
    if model == CF_TTS_MODEL:
        return {
            "stage": STAGE,
            "model": CF_TTS_MODEL,
            "text": shot["narration_text"],
            "speaker": CF_TTS_SPEAKER,
            "language": sb["language"],
        }
    return {
        "stage": STAGE,
        "model": TTS_MODEL,
        "text": shot["narration_text"],
        "voice": sb["tts_voice"],
        "style": sb["tts_style"],
        "language": sb["language"],
    }


def _is_daily_quota_error(exc: BaseException) -> bool:
    s = str(exc)
    return "429" in s and ("PerDay" in s or "RESOURCE_EXHAUSTED" in s)


def run(sb: dict | None = None, only: set[str] | None = None) -> dict[str, Path]:
    load_env()
    sb = sb or validate_storyboard()
    client = None
    use_cf = os.environ.get("TTS_BACKEND", "").lower() == "cloudflare"
    results: dict[str, Path] = {}
    for shot in sb["shots"]:
        sid = shot["id"]
        if only and sid not in only:
            continue
        if not shot["narration_text"].strip():
            print(f"  [skip] {sid}: empty narration")
            continue

        # Check cache for preferred backend first (and fallback backend if already cached).
        active_model = CF_TTS_MODEL if use_cf else TTS_MODEL
        inputs = shot_inputs(sb, shot, active_model)
        h = input_hash(inputs)
        cached = cache_lookup(STAGE, sid, h)
        if not cached and not use_cf:
            cf_in = shot_inputs(sb, shot, CF_TTS_MODEL)
            cf_h = input_hash(cf_in)
            if (cf_c := cache_lookup(STAGE, sid, cf_h)):
                active_model, inputs, h, cached = CF_TTS_MODEL, cf_in, cf_h, cf_c

        params = {k: v for k, v in inputs.items() if k not in ("stage", "model", "text")} | {"input_hash": h}
        if cached:
            log_run(stage=STAGE, shot_id=sid, model=active_model, params=params, cache_hit=True)
            print(f"  [cache] {sid} ({active_model})")
            results[sid] = cached
            continue

        out = narration_path(sid)
        t = Timer()
        try:
            if not use_cf:
                try:
                    client = client or get_client()
                    with t:
                        dur = with_retry(max_attempts=5)(tts_to_wav)(
                            client, shot["narration_text"], sb["tts_voice"], sb["tts_style"], out)
                except Exception as e:  # noqa: BLE001
                    if not _is_daily_quota_error(e):
                        raise
                    print(f"  [warn]  {sid}: Gemini TTS quota exhausted; switching to Cloudflare {CF_TTS_MODEL} ({CF_TTS_SPEAKER})")
                    log_run(stage=STAGE, shot_id=sid, model=TTS_MODEL, params=params, latency_ms=t.ms,
                            status="fallback", error=repr(e))
                    use_cf = True
                    active_model = CF_TTS_MODEL
                    inputs = shot_inputs(sb, shot, CF_TTS_MODEL)
                    h = input_hash(inputs)
                    params = {k: v for k, v in inputs.items() if k not in ("stage", "model", "text")} | {"input_hash": h}
            if use_cf:
                with t:
                    dur = with_retry(max_attempts=5)(_cf_tts_to_wav)(
                        shot["narration_text"], CF_TTS_SPEAKER, out)

            cache_store(STAGE, sid, h, out)
            usd = dur * USD_PER_AUDIO_SEC if active_model == TTS_MODEL else 0.0
            log_run(stage=STAGE, shot_id=sid, model=active_model, params=params, latency_ms=t.ms,
                    estimated_usd=usd, audio_sec=round(dur, 2))
            print(f"  [gen]   {sid} ({dur:.1f}s audio, {active_model}, {t.ms:.0f} ms)")
            if dur > shot["duration_sec"] + 0.5:
                print(f"  [warn]  {sid}: narration {dur:.1f}s exceeds duration_sec {shot['duration_sec']}")
            results[sid] = out
        except Exception as e:  # noqa: BLE001
            print(f"  [err]   {sid}: {e}")
            log_run(stage=STAGE, shot_id=sid, model=active_model, params=params, latency_ms=t.ms,
                    status="error", error=repr(e))
            raise
    return results


if __name__ == "__main__":
    only = set(sys.argv[1:]) or None
    run(only=only)
