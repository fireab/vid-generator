"""Merge a Kaggle kaggle_runs.jsonl into runs.jsonl (dedupes by timestamp+stage+shot_id)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from utils import RUNS_LOG


def key(r: dict) -> tuple:
    return (r.get("timestamp"), r.get("stage"), r.get("shot_id"), r.get("source"))


def main(path: str) -> int:
    existing = set()
    if RUNS_LOG.exists():
        existing = {key(json.loads(line)) for line in RUNS_LOG.read_text().splitlines() if line.strip()}
    added = 0
    with open(RUNS_LOG, "a", encoding="utf-8") as out:
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            r.setdefault("source", "kaggle")
            if key(r) in existing:
                continue
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            added += 1
    print(f"merged {added} records into {RUNS_LOG.name}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: merge_kaggle_log.py path/to/kaggle_runs.jsonl")
    sys.exit(main(sys.argv[1]))
