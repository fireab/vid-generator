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
    music_path = a.music
    for stage in (RADIO_STAGES if a.mode == "radio" else FILM_STAGES):
        print(f"== {stage}")
        if stage == "assemble":
            import assemble
            (assemble.radio if a.mode == "radio" else assemble.film)(sb, music_path)
        elif stage == "music":
            import music
            music_path = music_path or music.run(sb)
        else:
            __import__(stage).run(sb, only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
