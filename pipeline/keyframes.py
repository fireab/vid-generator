"""Keyframes stage: character/style reference sheet + one keyframe per shot via Cloudflare Workers AI.

Note: FLUX.1 schnell on Workers AI is text-to-image only, so consistency is enforced by
prepending the same style_block + character_description to every prompt and fixing seeds.
The ref sheet is a visual anchor for review and for Wan / future image-conditioned models.
"""
from __future__ import annotations

import base64
import os
import sys

import requests

from media import ffmpeg, require_ffmpeg
from utils import (OUTPUTS, Timer, cache_lookup, cache_store, input_hash, load_env, log_run,
                   require_env, validate_storyboard, with_retry)

STAGE = "keyframes"
OUT_DIR = OUTPUTS / "keyframes"
MODEL = os.environ.get("CF_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
STEPS = 8  # schnell max
REF_ID, REF_SEED = "ref_sheet", 7
# Workers AI flux-1-schnell: ~$0.0000528 / 512px tile + ~$0.0001056 / step; 1024x1024 = 4 tiles.
EST_USD = 4 * 0.0000528 + STEPS * 0.0001056

COMPOSITION = ("Centered composition: main subject in the middle third of the frame, eye level, "
               "generous headroom and empty margin on all sides, nothing important near the edges, "
               "safe for both 16:9 and 9:16 center crops.")


def ref_prompt(sb: dict) -> str:
    return (f"{sb['style_block']}. Character reference sheet: {sb['character_description']}. "
            "Full-body front view and head-and-shoulders portrait side by side, neutral pose, "
            "plain soft neutral background, even lighting, consistent costume and features.")


def shot_prompt(sb: dict, shot: dict) -> str:
    return (f"{sb['style_block']}. Recurring character (keep identical): {sb['character_description']}. "
            f"Scene: {shot['image_prompt']}. {COMPOSITION}")


@with_retry(max_attempts=5)
def _flux(prompt: str, seed: int) -> bytes:
    acct, token = require_env("CLOUDFLARE_ACCOUNT_ID"), require_env("CLOUDFLARE_API_TOKEN")
    r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{MODEL}",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"prompt": prompt[:2048], "steps": STEPS, "seed": seed}, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Cloudflare {r.status_code}: {r.text[:300]}")
    return base64.b64decode(r.json()["result"]["image"])


def _generate(item_id: str, prompt: str, seed: int) -> str:
    inputs = {"stage": STAGE, "model": MODEL, "prompt": prompt, "seed": seed, "steps": STEPS}
    h = input_hash(inputs)
    params = {"steps": STEPS, "prompt": prompt, "input_hash": h}
    if (p := cache_lookup(STAGE, item_id, h)):
        log_run(stage=STAGE, shot_id=item_id, model=MODEL, params=params, seed=seed, cache_hit=True)
        print(f"  [cache] {item_id}")
        return str(p)
    out = OUT_DIR / f"{item_id}.png"
    raw = OUT_DIR / f"{item_id}.tmp.jpg"
    t = Timer()
    try:
        with t:
            raw.write_bytes(_flux(prompt, seed))
        ffmpeg(["-i", str(raw), str(out)])  # normalize to PNG
        raw.unlink(missing_ok=True)
        cache_store(STAGE, item_id, h, out)
        log_run(stage=STAGE, shot_id=item_id, model=MODEL, params=params, seed=seed,
                latency_ms=t.ms, estimated_usd=EST_USD)
        print(f"  [gen]   {item_id} ({t.ms:.0f} ms)")
        return str(out)
    except Exception as e:  # noqa: BLE001
        log_run(stage=STAGE, shot_id=item_id, model=MODEL, params=params, seed=seed,
                latency_ms=t.ms, status="error", error=repr(e))
        raise


def run(sb: dict | None = None, only: set[str] | None = None) -> dict:
    load_env()
    require_ffmpeg()
    sb = sb or validate_storyboard()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {REF_ID: _generate(REF_ID, ref_prompt(sb), REF_SEED)}
    for shot in sb["shots"]:
        if only and shot["id"] not in only:
            continue
        results[shot["id"]] = _generate(shot["id"], shot_prompt(sb, shot), shot["seed"])
    return results


if __name__ == "__main__":
    run(only=set(sys.argv[1:]) or None)
