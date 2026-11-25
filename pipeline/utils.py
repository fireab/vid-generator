"""Shared utilities for The Heritage Short pipeline.

- JSON schema validation of storyboard.json
- Deterministic SHA-256 input hashing + cache manifest
- Exponential backoff retry wrapper
- Unified runs.jsonl logger
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "storyboard.schema.json"
STORYBOARD_PATH = ROOT / "storyboard.json"
OUTPUTS = ROOT / "outputs"
RUNS_LOG = ROOT / "runs.jsonl"
CACHE_MANIFEST = OUTPUTS / ".cache_manifest.json"


def load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing environment variable {name} (see .env.example)")
    return val


# ---------------------------------------------------------------- validation
def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_storyboard(path: Path = STORYBOARD_PATH) -> dict:
    """Validate storyboard against schema; raise ValueError listing all errors."""
    schema = load_json(SCHEMA_PATH)
    data = load_json(path)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        msgs = [f"  - {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]
        raise ValueError("storyboard.json failed validation:\n" + "\n".join(msgs))
    ids = [s["id"] for s in data["shots"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Duplicate shot ids: {sorted(dupes)}")
    return data


# ------------------------------------------------------------------- caching
def input_hash(payload: dict) -> str:
    """SHA-256 of canonical JSON of a stage's exact inputs."""
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _load_manifest() -> dict:
    if CACHE_MANIFEST.exists():
        return load_json(CACHE_MANIFEST)
    return {}


def _save_manifest(m: dict) -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(CACHE_MANIFEST)


def cache_lookup(stage: str, shot_id: str, h: str) -> Path | None:
    """Return the cached output path if hash matches and file exists."""
    entry = _load_manifest().get(stage, {}).get(shot_id)
    if entry and entry.get("hash") == h:
        p = ROOT / entry["path"]
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def cache_store(stage: str, shot_id: str, h: str, path: Path) -> None:
    m = _load_manifest()
    m.setdefault(stage, {})[shot_id] = {
        "hash": h,
        "path": str(path.resolve().relative_to(ROOT)),
        "updated": now_iso(),
    }
    _save_manifest(m)


def clear_cache() -> None:
    if CACHE_MANIFEST.exists():
        CACHE_MANIFEST.unlink()


# --------------------------------------------------------------------- retry
def with_retry(max_attempts: int = 5, base_delay: float = 1.0, max_delay: float = 30.0,
               retry_on: tuple[type[BaseException], ...] = (Exception,)) -> Callable:
    """Exponential backoff with full jitter."""

    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on as e:  # noqa: PERF203
                    if attempt == max_attempts:
                        raise
                    delay = min(max_delay, base_delay * 2 ** (attempt - 1))
                    delay = random.uniform(0, delay)
                    print(f"  [retry] {fn.__name__} attempt {attempt} failed: {e!r}; sleeping {delay:.1f}s")
                    time.sleep(delay)

        return wrapper

    return deco


# ------------------------------------------------------------------- logging
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_run(*, stage: str, shot_id: str | None, model: str | None, params: dict | None = None,
            seed: int | None = None, latency_ms: float = 0.0, gpu_seconds: float = 0.0,
            estimated_usd: float = 0.0, cache_hit: bool = False, status: str = "ok",
            error: str | None = None, **extra: Any) -> dict:
    """Append one JSON line per model call to runs.jsonl."""
    rec = {
        "timestamp": now_iso(),
        "stage": stage,
        "shot_id": shot_id,
        "model": model,
        "params": params or {},
        "seed": seed,
        "latency_ms": round(latency_ms, 1),
        "gpu_seconds": gpu_seconds,
        "estimated_usd": round(estimated_usd, 6),
        "cache_hit": cache_hit,
        "status": status,
        "error": error,
    }
    rec.update(extra)
    with open(RUNS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, *exc):
        self.ms = (time.perf_counter() - self.t0) * 1000
        return False
