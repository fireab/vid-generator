"""Smoke test: one tiny call each to Gemini text, Gemini TTS, Cloudflare Workers AI Flux."""
from __future__ import annotations

import base64
import sys

import requests

from gemini_tts import TEXT_MODEL, TTS_MODEL, get_client, tts_to_wav
from utils import OUTPUTS, Timer, load_env, log_run, require_env, with_retry

FLUX_MODEL = "@cf/black-forest-labs/flux-1-schnell"
SMOKE_DIR = OUTPUTS / "smoke"


@with_retry(max_attempts=3)
def _gemini_text(client):
    r = client.models.generate_content(model=TEXT_MODEL, contents="Reply with exactly: OK")
    if not (r.text or "").strip():
        raise RuntimeError("empty text response")
    return r.text.strip()


@with_retry(max_attempts=3)
def _gemini_tts(client):
    return tts_to_wav(client, "Hello from the Heritage Short.", "Kore", "Say cheerfully:", SMOKE_DIR / "tts.wav")


@with_retry(max_attempts=3)
def _flux():
    acct = require_env("CLOUDFLARE_ACCOUNT_ID")
    token = require_env("CLOUDFLARE_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{FLUX_MODEL}"
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
                      json={"prompt": "a small red cube on a white table", "steps": 4, "seed": 42}, timeout=60)
    r.raise_for_status()
    img = r.json()["result"]["image"]
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    (SMOKE_DIR / "flux.jpg").write_bytes(base64.b64decode(img))


def _run(name, model, params, fn, seed=None):
    t = Timer()
    try:
        with t:
            out = fn()
        log_run(stage="smoke", shot_id=name, model=model, params=params, seed=seed, latency_ms=t.ms)
        print(f"  PASS {name:12s} ({t.ms:.0f} ms) {out if isinstance(out, str) else ''}")
        return True
    except Exception as e:  # noqa: BLE001
        log_run(stage="smoke", shot_id=name, model=model, params=params, seed=seed,
                latency_ms=t.ms, status="error", error=repr(e))
        print(f"  FAIL {name:12s} {e!r}")
        return False


def main() -> int:
    load_env()
    print("Smoke test")
    try:
        client = get_client()
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL gemini client: {e}")
        client = None
    results = [
        client is not None and _run("gemini_text", TEXT_MODEL, {"prompt": "Reply with exactly: OK"}, lambda: _gemini_text(client)),
        client is not None and _run("gemini_tts", TTS_MODEL, {"voice": "Kore"}, lambda: _gemini_tts(client)),
        _run("cf_flux", FLUX_MODEL, {"steps": 4}, _flux, seed=42),
    ]
    ok = all(results)
    print("ALL PASS" if ok else "SOME CHECKS FAILED (see runs.jsonl)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
