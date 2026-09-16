#!/usr/bin/env python3
"""Regenerate the deterministic repository structure snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

from validate import (
    STRUCTURE_SNAPSHOT_PATH,
    ConfigError,
    enumerate_repository_files,
    load_config,
    render_repository_structure,
)


def update_snapshot(root: Path) -> str:
    """Write the snapshot described by validate.json and return its path."""
    config = load_config(root)
    options = config["structure-snapshot"]
    snapshot_path = options.get("path", STRUCTURE_SNAPSHOT_PATH)

    paths = set(enumerate_repository_files(root))
    paths.add(snapshot_path)
    snapshot = render_repository_structure(sorted(paths))

    destination = root / snapshot_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as snapshot_file:
        snapshot_file.write(snapshot)
    return snapshot_path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        snapshot_path = update_snapshot(root)
    except (ConfigError, OSError, RuntimeError, UnicodeError) as error:
        print(f"Repository structure update failed: {error}", file=sys.stderr)
        return 1
    print(f"Updated {snapshot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
