"""Import the participant ZIP into an ignored directory without executing its contents."""

import argparse
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "archive", type=Path, help="Path to hackathon-knowledge-kit-participant.zip"
    )
    args = parser.parse_args()
    destination = ROOT / ".local" / "kit"
    if destination.exists():
        parser.error(
            f"Kit already exists at {destination}; keep or move it before importing again."
        )

    with zipfile.ZipFile(args.archive) as archive:
        entries = []
        for info in archive.infolist():
            if "\\" in info.filename:
                parser.error("Archive contains a nonportable path.")
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or ":" in info.filename:
                parser.error("Archive contains an unsafe path.")
            if stat.S_ISLNK(info.external_attr >> 16):
                parser.error("Archive contains a symbolic link.")
            entries.append((info, path))

        roots = {path.parts[0] for _, path in entries if path.parts}
        prefix = next(iter(roots)) if len(roots) == 1 else None
        normalized = [
            (info, PurePosixPath(*path.parts[1:]) if prefix else path) for info, path in entries
        ]
        files = {path.as_posix() for info, path in normalized if not info.is_dir()}
        required = {"harness/run_eval.py", "harness/contract.py", "eval/public_eval.jsonl"}
        if not required <= files:
            parser.error("This archive does not look like the supplied participant kit.")

        for info, path in normalized:
            target = destination.joinpath(*path.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                parser.error("Archive path escapes the destination.")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)

    print(f"Imported kit into {destination}")
    print("The .local directory is ignored by Git. Do not redistribute it.")


if __name__ == "__main__":
    main()
