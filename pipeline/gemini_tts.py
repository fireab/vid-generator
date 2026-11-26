"""Shared Gemini TTS helper (used by smoke_test and narration)."""
from __future__ import annotations

import wave
from pathlib import Path

TTS_MODEL = "gemini-2.5-flash-preview-tts"
TEXT_MODEL = "gemini-2.5-flash"
SAMPLE_RATE = 24000  # Gemini TTS returns 16-bit mono PCM @ 24 kHz


def get_client():
    from google import genai

    from utils import require_env

    return genai.Client(
        api_key=require_env("GEMINI_API_KEY"),
        http_options={"api_version": "v1beta"},
    )


def tts_to_wav(client, text: str, voice: str, style: str, out_path: Path, model: str = TTS_MODEL) -> float:
    """Synthesize `text` with style direction into a WAV file. Returns duration in seconds."""
    from google.genai import types

    prompt = f"{style}\n\n{text}" if style else text
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    pcm = resp.candidates[0].content.parts[0].inline_data.data
    if not pcm:
        raise RuntimeError("TTS returned empty audio")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    tmp.replace(out_path)
    return len(pcm) / (2 * SAMPLE_RATE)
