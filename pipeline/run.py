"""Orchestrator: validate storyboard.json, then run stages in order."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import load_env, validate_storyboard  # noqa: E402

FILM_STAGES = ["narration", "keyframes", "shots", "music", "assemble"]
RADIO_STAGES = ["narration", "assemble"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The Heritage Short pipeline")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--mode", choices=["radio", "film"], default="radio")
    ap.add_argument("--shots", nargs="*", help="limit to these shot ids")
    ap.add_argument("--music", type=Path)
    a = ap.parse_args(argv)

    load_env()
    try:
        sb = validate_storyboard()
    except ValueError as e:
        print(e)
        return 1
    print(f"storyboard.json valid: {len(sb['shots'])} shots, "
          f"{sum(s['duration_sec'] for s in sb['shots'])}s total")
    if a.validate_only:
        return 0

    only = set(a.shots) if a.shots else None
    for stage in (RADIO_STAGES if a.mode == "radio" else FILM_STAGES):
        print(f"== {stage}")
        if stage == "narration":
            import narration
            narration.run(sb, only)
        elif stage == "assemble":
            import assemble
            if a.mode == "radio":
                assemble.radio(sb, a.music)
            else:
                assemble.main(["--mode", "film"])
        else:
            mod = __import__(stage)
            mod.run(sb, only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
