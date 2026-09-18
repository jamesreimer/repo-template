#!/usr/bin/env python3
"""Check repository-local Markdown links using Lychee, without network requests."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from validate import enumerate_repository_files


def check_links(root: Path) -> int:
    root = root.resolve()
    executable = shutil.which("lychee")
    if executable is None:
        print(
            "Lychee is required: install version 0.24.2 from "
            "https://github.com/lycheeverse/lychee/releases/tag/lychee-v0.24.2",
            file=sys.stderr,
        )
        return 1
    inventory = enumerate_repository_files(root)
    files = [
        "./" + name for name in inventory if name.endswith(".md") and not (root / name).is_symlink()
    ]
    if not files:
        print("No Markdown files to check.")
        return 0
    for name in files:
        path = root / name
        if any(parent.is_symlink() for parent in [path] + list(path.parents) if parent != root):
            print(f"Markdown input traverses a symbolic link: {name}", file=sys.stderr)
            return 1
    # Disable implicit tool configuration so repository boundary and offline
    # behavior cannot differ between extraction and checking.
    options = [executable, "--config", os.devnull, "--offline", "--no-progress"]
    extracted = subprocess.run(
        options + ["--dump", "--"] + files,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if extracted.returncode:
        print(extracted.stderr or extracted.stdout, file=sys.stderr)
        return 1
    for destination in extracted.stdout.splitlines():
        url = urlsplit(destination)
        if url.scheme != "file":
            continue
        target = Path(unquote(url.path)).resolve()
        if url.netloc not in {"", "localhost"} or not target.is_relative_to(root):
            print(f"Link escapes repository: {destination}", file=sys.stderr)
            return 1
        relative = target.relative_to(root).as_posix()
        if (
            target.exists()
            and relative != "."
            and relative not in inventory
            and not any(name.startswith(relative + "/") for name in inventory)
        ):
            print(
                f"Link target is outside the repository file inventory: {destination}",
                file=sys.stderr,
            )
            return 1
    checked = subprocess.run(
        options + ["--include-fragments", "--"] + files,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    print(checked.stdout, end="")
    print(checked.stderr, end="", file=sys.stderr)
    return checked.returncode


if __name__ == "__main__":
    raise SystemExit(check_links(Path(__file__).resolve().parents[1]))
