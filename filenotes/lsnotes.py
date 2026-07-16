"""``ls-notes`` command: list files that have notes and show their contents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .core import (
    Color,
    Entry,
    discover_note_files,
    is_note_file,
    note_file_for,
    read_entries,
    sort_mtime,
    source_label,
)


def _resolve_targets(targets: List[str]) -> List[Path]:
    """Map user arguments to existing note files.

    Each argument may be a source file (``exp_08.npy``), a note file
    (``exp_08.npy.notes.md``), or ``.`` for the current folder.
    """
    resolved: List[Path] = []
    for target in targets:
        path = Path(target)
        note_path = path if is_note_file(path) else note_file_for(target)
        if note_path.exists():
            resolved.append(note_path)
        else:
            print(f"ls-notes: no notes for '{target}'", file=sys.stderr)
    return resolved


def _render_long(note_path: Path, entries: List[Entry], color: Color) -> str:
    lines = [color.name(source_label(note_path)) + ":"]
    for i, entry in enumerate(entries):
        if i:
            lines.append("")
        lines.append("  " + color.time(entry.raw_timestamp))
        lines.append("")
        for body_line in entry.text.splitlines() or [""]:
            lines.append("  " + body_line)
    return "\n".join(lines)


def _render_short(note_path: Path, entries: List[Entry], color: Color) -> str:
    label = color.name(source_label(note_path)) + ":"
    if not entries:
        return label
    latest = entries[-1]  # newest note in the file
    return f"{label} {color.time(latest.raw_timestamp)} {latest.summary()}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ls-notes",
        description="List files with notes (oldest source first) and show them.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Specific files/folders to show. Default: every note file here.",
    )
    parser.add_argument(
        "-s", "--short", action="store_true", help="Collapse each file to one line."
    )
    parser.add_argument(
        "--version", action="version", version=f"ls-notes {__version__}"
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    color = Color(sys.stdout)

    if args.targets:
        note_files = _resolve_targets(args.targets)
    else:
        note_files = discover_note_files(Path("."))

    if not note_files:
        print("No notes found.")
        return 0

    # Oldest source first, matching the DEVDOC default.
    note_files.sort(key=sort_mtime)

    blocks: List[str] = []
    for note_path in note_files:
        entries = read_entries(note_path)
        if not entries:
            continue
        if args.short:
            blocks.append(_render_short(note_path, entries, color))
        else:
            blocks.append(_render_long(note_path, entries, color))

    if not blocks:
        print("No notes found.")
        return 0

    print("\n".join(blocks) if args.short else "\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
