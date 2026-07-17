"""``cat-notes`` command: concatenate notes into one Markdown document.

Unlike ``ls-notes`` (a colored terminal listing), this emits a plain Markdown
document suitable for redirecting to a file or feeding a Markdown renderer.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import __version__
from .core import (
    FOLDER_NOTE_NAME,
    is_note_file,
    note_file_for,
    source_for,
    walk_note_files,
)


def _collect(targets: List[str], recursive: bool) -> Tuple[Path, List[Path]]:
    """Return (base directory, note files) for the given targets."""
    base = Path(".")
    note_files: List[Path] = []
    if not targets:
        note_files = walk_note_files(base, recursive)
    else:
        for target in targets:
            path = Path(target)
            if path.is_dir():
                note_files.extend(walk_note_files(path, recursive))
            elif is_note_file(path) and path.exists():
                note_files.append(path)
            else:
                candidate = note_file_for(target)
                if candidate.exists():
                    note_files.append(candidate)
                else:
                    print(f"cat-notes: no notes for '{target}'", file=sys.stderr)
    # De-duplicate while preserving discovery.
    seen = set()
    unique = []
    for p in note_files:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return base, unique


def _sort_key(base: Path, note_path: Path):
    reldir = os.path.relpath(note_path.parent, base)
    parts = () if reldir == "." else tuple(reldir.split(os.sep))
    is_folder_note = note_path.name == FOLDER_NOTE_NAME
    # Within a directory, the folder note comes before per-file notes.
    return (parts, 0 if is_folder_note else 1, note_path.name.lower())


def _label(base: Path, note_path: Path) -> str:
    if note_path.name == FOLDER_NOTE_NAME:
        reldir = os.path.relpath(note_path.parent, base)
        return "(folder)" if reldir == "." else f"{reldir}/"
    return os.path.relpath(source_for(note_path), base)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cat-notes",
        description="Concatenate notes into one Markdown document (to stdout).",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Folders/files to include. Default: the current folder.",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Include subfolders."
    )
    parser.add_argument(
        "--version", action="version", version=f"cat-notes {__version__}"
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)

    base, note_files = _collect(args.targets, args.recursive)
    if not note_files:
        print("cat-notes: no notes found.", file=sys.stderr)
        return 0

    note_files.sort(key=lambda p: _sort_key(base, p))

    where = Path(args.targets[0]).name if args.targets else base.resolve().name
    blocks = [f"# Notes under {where or '.'}"]
    for note_path in note_files:
        try:
            body = note_path.read_text(encoding="utf-8").strip("\n")
        except OSError:
            continue
        if not body:
            continue
        blocks.append(f"## {_label(base, note_path)}\n\n{body}")

    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
