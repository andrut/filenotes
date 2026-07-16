"""``note`` command: append a note to a file, folder, or (later) git HEAD."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import __version__
from .core import append_note, is_note_file, note_file_for

EDITOR_TEMPLATE = """
# Enter your note above. Lines starting with '#' are ignored.
# Save an empty note to cancel.
"""


def _editor_command() -> list:
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        return editor.split()
    for candidate in ("nano", "vi", "vim"):
        if shutil.which(candidate):
            return [candidate]
    return ["vi"]


def capture_from_editor() -> Optional[str]:
    """Open $EDITOR and return the typed note, or None if cancelled."""
    fd, path = tempfile.mkstemp(suffix=".md", prefix="note-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(EDITOR_TEMPLATE)
        try:
            subprocess.call(_editor_command() + [path])
        except FileNotFoundError:
            print("error: could not launch an editor; set $EDITOR.", file=sys.stderr)
            return None
        content = Path(path).read_text(encoding="utf-8")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    kept = [ln for ln in content.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(kept).strip()
    return text or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="note",
        description="Append a timestamped note to a file or the current folder.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="File(s) to annotate. Omit (or use '.') for the current folder. "
        "Multiple files get the same note (broadcast).",
    )
    parser.add_argument(
        "-m", "--message", help="Note text. Without it, your $EDITOR opens."
    )
    parser.add_argument("--version", action="version", version=f"note {__version__}")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)

    # No targets means a single folder note; otherwise one note file per target.
    targets = args.targets or [None]

    # Validate up front so we never write a partial broadcast.
    for target in targets:
        if target is not None and target != "." and is_note_file(Path(target)):
            print(
                f"error: '{target}' is itself a note file; refusing to nest notes.",
                file=sys.stderr,
            )
            return 2

    note_paths = [note_file_for(t) for t in targets]

    if args.message is not None:
        message = args.message
    else:
        message = capture_from_editor()
        if message is None:
            print("Cancelled — nothing appended.", file=sys.stderr)
            return 1

    # Single timestamp so a broadcast note shares one moment across files.
    when = datetime.now()
    for note_path in note_paths:
        append_note(note_path, message, when=when)
        print(f"Appended note to {note_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
