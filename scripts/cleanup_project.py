"""Project cleanup utility for temporary/build artifacts."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PATTERNS = [
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
]

EXTRA_FILES = [
    "dev-backend.err.log",
    "dev-backend.log",
    "dev-recheck.log",
    "dev-startup.log",
    "workspace.txt",
]


def find_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    for pattern in PATTERNS:
        targets.extend(root.rglob(pattern))
    for pattern in ("*.egg-info",):
        targets.extend(root.rglob(pattern))
    for file_name in EXTRA_FILES:
        path = root / file_name
        if path.exists():
            targets.append(path)
    extracted = root / "extracted_scaffold"
    if extracted.exists():
        targets.append(extracted)
    return sorted(set(targets))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually delete files")
    args = parser.parse_args()

    root = Path.cwd()
    targets = find_targets(root)
    if not targets:
        print("No cleanup targets found.")
        return 0
    for target in targets:
        print(target)
        if args.apply:
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
    print(f"{'Deleted' if args.apply else 'Found'} {len(targets)} targets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
