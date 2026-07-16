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
from . import capture as capture_mod
from .core import (
    ASSET_STAMP_FORMAT,
    append_note,
    copy_image,
    image_markdown,
    is_note_file,
    note_file_for,
)

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
    parser.add_argument(
        "-i",
        "--image",
        action="append",
        default=[],
        metavar="PATH",
        help="Image to attach after the note (repeatable). Copied into "
        "notes-assets/ and linked in Markdown.",
    )
    parser.add_argument(
        "-S", "--screenshot", action="store_true", help="Attach a full-screen capture."
    )
    parser.add_argument(
        "-R", "--region", action="store_true", help="Attach a selected screen region."
    )
    parser.add_argument(
        "-C", "--clipboard", action="store_true", help="Attach the clipboard image."
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

    # Validate images up front too, so nothing is written on a bad path.
    images = [Path(p) for p in args.image]
    for img in images:
        if not img.is_file():
            print(f"error: image not found: '{img}'", file=sys.stderr)
            return 2

    note_paths = [note_file_for(t) for t in targets]

    # Captured images (screenshot / region / clipboard) live in a temp dir until
    # copied into each note's notes-assets/. Capture happens before the editor so
    # an empty caption still records the shot.
    captures = []
    if args.screenshot:
        captures.append(("screenshot.png", capture_mod.capture_fullscreen))
    if args.region:
        captures.append(("region.png", capture_mod.capture_region))
    if args.clipboard:
        captures.append(("clipboard.png", capture_mod.capture_clipboard))

    tmpdir = tempfile.mkdtemp(prefix="note-capture-") if captures else None
    try:
        for base, fn in captures:
            dest = os.path.join(tmpdir, base)
            try:
                tool = fn(dest)
            except capture_mod.CaptureError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            print(f"Captured {Path(base).stem} via {tool}", file=sys.stderr)
            images.append(Path(dest))

        if args.message is not None:
            message = args.message
        else:
            message = capture_from_editor()
            if message is None:
                # An empty editor still counts as a note when images are attached.
                if not images:
                    print("Cancelled — nothing appended.", file=sys.stderr)
                    return 1
                message = ""

        # Single timestamp so a broadcast note shares one moment across files.
        when = datetime.now()
        stamp = when.strftime(ASSET_STAMP_FORMAT)
        for note_path in note_paths:
            note_dir = note_path.parent
            img_lines = []
            for img in images:
                dest = copy_image(note_dir, img, stamp)
                img_lines.append(image_markdown(note_dir, dest, img.name))
            body = "\n\n".join(p for p in [message.strip("\n"), *img_lines] if p)
            append_note(note_path, body, when=when)
            print(f"Appended note to {note_path}")
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
