"""Run the unchanged official evaluator against the private local kit."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--starter", action="store_true", help="Evaluate the supplied naive starter"
    )
    args = parser.parse_args()
    kit = ROOT / ".local" / "kit"
    harness = kit / "harness" / "run_eval.py"
    if not harness.is_file():
        parser.error("Import the participant ZIP first: python scripts/import_kit.py <path-to-zip>")
    label = "starter" if args.starter else "solution"
    command = [
        sys.executable,
        str(harness),
        "--submission",
        str(kit / "starter" if args.starter else ROOT),
        "--snapshots",
        str(kit / "snapshots"),
        "--eval",
        str(kit / "eval" / "public_eval.jsonl"),
        "--out",
        str(ROOT / ".local" / "results" / label),
    ]
    raise SystemExit(subprocess.call(command, cwd=kit))


if __name__ == "__main__":
    main()
