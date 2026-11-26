"""Narration stage: one TTS WAV per shot, cached by input hash.

Primary backend: Gemini TTS (`gemini-2.5-flash-preview-tts`).
Automatic fallback on daily quota exhaustion:
- Amharic / non-English (`language` starting with 'am', etc.): `edge-tts` (`am-ET-MekdesNeural`).
- English (`language` starting with 'en'): Cloudflare Workers AI Deepgram Aura-1 (`@cf/deepgram/aura-1`).
"""
from __future__ import annotations

import asyncio
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
CF_TTS_SPEAKER = os.environ.get("CF_TTS_SPEAKER", "luna")
EDGE_TTS_MODEL = "edge-tts"
EDGE_AM_VOICE = os.environ.get("EDGE_TTS_VOICE", "am-ET-MekdesNeural")
EDGE_EN_VOICE = os.environ.get("EDGE_TTS_EN_VOICE", "en-US-AriaNeural")
# Rough estimate: Gemini 2.5 Flash TTS ~ $10 / 1M audio output tokens, ~25 tokens/sec audio.
USD_PER_AUDIO_SEC = 25 * 10 / 1_000_000


def _fallback_model_for(sb: dict) -> tuple[str, str]:
    """Return (model_name, voice_or_speaker) for the language-aware fallback TTS."""
    lang = sb.get("language", "en").lower()
    backend = os.environ.get("TTS_BACKEND", "").lower()
    if backend == "cloudflare":
        return CF_TTS_MODEL, CF_TTS_SPEAKER
    if backend == "edge" or not lang.startswith("en"):
        voice = EDGE_AM_VOICE if lang.startswith("am") else EDGE_EN_VOICE
        return EDGE_TTS_MODEL, voice
    return CF_TTS_MODEL, CF_TTS_SPEAKER


def _edge_tts_to_wav(text: str, voice: str, out_path: Path) -> float:
    """Synthesize `text` via Microsoft Edge Neural TTS (`edge-tts`) into a 24kHz mono WAV."""
    import edge_tts

    require_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = out_path.with_suffix(".tmp.mp3")
    tmp = out_path.with_suffix(".tmp.wav")

    async def _save() -> None:
        comm = edge_tts.Communicate(text, voice)
        await comm.save(str(raw))

    asyncio.run(_save())
    if not raw.exists() or raw.stat().st_size == 0:
        raise RuntimeError(f"edge-tts ({voice}) produced empty audio")
    ffmpeg(["-i", str(raw), "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(tmp)])
    raw.unlink(missing_ok=True)
    tmp.replace(out_path)
    return wav_duration(out_path)


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


def shot_inputs(sb: dict, shot: dict, model: str = TTS_MODEL, voice_override: str | None = None) -> dict:
    if model != TTS_MODEL:
        return {
            "stage": STAGE,
            "model": model,
            "text": shot["narration_text"],
            "voice": voice_override or "",
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
    fb_model, fb_voice = _fallback_model_for(sb)
    use_fallback = os.environ.get("TTS_BACKEND", "").lower() in ("cloudflare", "edge")
    results: dict[str, Path] = {}
    for shot in sb["shots"]:
        sid = shot["id"]
        if only and sid not in only:
            continue
        if not shot["narration_text"].strip():
            print(f"  [skip] {sid}: empty narration")
            continue

        active_model = fb_model if use_fallback else TTS_MODEL
        active_voice = fb_voice if use_fallback else sb["tts_voice"]
        inputs = shot_inputs(sb, shot, active_model, active_voice)
        h = input_hash(inputs)
        cached = cache_lookup(STAGE, sid, h)
        if not cached and not use_fallback:
            fb_in = shot_inputs(sb, shot, fb_model, fb_voice)
            fb_h = input_hash(fb_in)
            if (fb_c := cache_lookup(STAGE, sid, fb_h)):
                active_model, active_voice, inputs, h, cached = fb_model, fb_voice, fb_in, fb_h, fb_c

        params = {k: v for k, v in inputs.items() if k not in ("stage", "model", "text")} | {"input_hash": h}
        if cached:
            log_run(stage=STAGE, shot_id=sid, model=active_model, params=params, cache_hit=True)
            print(f"  [cache] {sid} ({active_model})")
            results[sid] = cached
            continue

        out = narration_path(sid)
        t = Timer()
        try:
            if not use_fallback:
                try:
                    client = client or get_client()
                    with t:
                        dur = with_retry(max_attempts=5)(tts_to_wav)(
                            client, shot["narration_text"], sb["tts_voice"], sb["tts_style"], out)
                except Exception as e:  # noqa: BLE001
                    if not _is_daily_quota_error(e):
                        raise
                    print(f"  [warn]  {sid}: Gemini TTS quota exhausted; switching to {fb_model} ({fb_voice})")
                    log_run(stage=STAGE, shot_id=sid, model=TTS_MODEL, params=params, latency_ms=t.ms,
                            status="fallback", error=repr(e))
                    use_fallback = True
                    active_model, active_voice = fb_model, fb_voice
                    inputs = shot_inputs(sb, shot, fb_model, fb_voice)
                    h = input_hash(inputs)
                    params = {k: v for k, v in inputs.items() if k not in ("stage", "model", "text")} | {"input_hash": h}
            if use_fallback:
                with t:
                    fn = _edge_tts_to_wav if active_model == EDGE_TTS_MODEL else _cf_tts_to_wav
                    dur = with_retry(max_attempts=5)(fn)(shot["narration_text"], active_voice, out)

            cache_store(STAGE, sid, h, out)
            usd = dur * USD_PER_AUDIO_SEC if active_model == TTS_MODEL else 0.0
            log_run(stage=STAGE, shot_id=sid, model=active_model, params=params, latency_ms=t.ms,
                    estimated_usd=usd, audio_sec=round(dur, 2))
            print(f"  [gen]   {sid} ({dur:.1f}s audio, {active_model}/{active_voice}, {t.ms:.0f} ms)")
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
