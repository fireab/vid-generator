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


def _extract_pcm(resp) -> tuple[bytes | None, str]:
    """Safely extract audio bytes from a GenerateContentResponse, or return (None, diagnostic)."""
    candidates = getattr(resp, "candidates", None) or []
    prompt_fb = getattr(resp, "prompt_feedback", None)
    if not candidates:
        return None, f"no candidates (prompt_feedback={prompt_fb!r})"
    cand = candidates[0]
    finish_reason = getattr(cand, "finish_reason", None)
    content = getattr(cand, "content", None)
    parts = getattr(content, "parts", None) if content is not None else None
    if parts:
        for part in parts:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline is not None else None
            if data:
                return data, ""
    return None, f"empty audio content (finish_reason={finish_reason!r}, prompt_feedback={prompt_fb!r})"


def tts_to_wav(client, text: str, voice: str, style: str, out_path: Path, model: str = TTS_MODEL) -> float:
    """Synthesize `text` with style direction into a WAV file. Returns duration in seconds."""
    from google.genai import types

    cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
    )

    prompts = [f"Read the following aloud in a {style.rstrip('.')} tone:\n{text}"] if style else []
    prompts.append(text)

    pcm, diag = None, ""
    for i, prompt in enumerate(prompts):
        resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
        pcm, diag = _extract_pcm(resp)
        if pcm:
            break
        if i == 0 and len(prompts) > 1:
            print(f"  [warn] styled TTS returned {diag}; retrying with plain text")

    if not pcm:
        raise RuntimeError(f"TTS failed: {diag}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    tmp.replace(out_path)
    return len(pcm) / (2 * SAMPLE_RATE)
