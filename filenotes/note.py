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
from . import gitctx
from .config import load_config
from .core import (
    ASSET_STAMP_FORMAT,
    Color,
    append_note,
    copy_image,
    humanize_age,
    image_markdown,
    is_note_file,
    note_file_for,
    recent_files,
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


def select_recent_target() -> Optional[str]:
    """Interactively pick a recent file to annotate.

    Returns the chosen path, or None if there is nothing to choose or the user
    cancels. The menu is drawn on stderr so stdout stays clean.
    """
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        print(
            "note: no file given and no interactive terminal for the selector; "
            "pass a file, or use 'note .' for a folder note.",
            file=sys.stderr,
        )
        return None

    count = load_config()["recent_count"]
    files = recent_files(Path("."), count)
    if not files:
        print("note: no recent files here to annotate.", file=sys.stderr)
        return None

    color = Color(sys.stderr)
    now = datetime.now().timestamp()
    width = max(len(f.name) for f in files)
    print("Recent files:", file=sys.stderr)
    for i, f in enumerate(files, 1):
        age = humanize_age(f.stat().st_mtime, now)
        print(
            f"  {color.dim(str(i) + ')')} {f.name.ljust(width)}  {color.time(age)}",
            file=sys.stderr,
        )

    prompt = f"Select 1-{len(files)} (Enter/q to cancel): "
    while True:
        try:
            choice = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return None
        if choice == "" or choice.lower() == "q":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            return str(files[int(choice) - 1])
        print(f"  '{choice}' is not 1-{len(files)}.", file=sys.stderr)


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
    parser.add_argument(
        "--commit",
        dest="commit",
        action="store_true",
        default=None,
        help="Stamp the note with the current commit/branch/dirty state.",
    )
    parser.add_argument(
        "--no-commit",
        dest="commit",
        action="store_false",
        help="Do not add the version-control stamp (overrides the config default).",
    )
    parser.add_argument("--version", action="version", version=f"note {__version__}")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)

    # Bare `note` (no targets) opens the recent-file selector. `note .` is the
    # explicit folder note. Otherwise one note file per target.
    if args.targets:
        targets = args.targets
    else:
        selected = select_recent_target()
        if selected is None:
            print("Cancelled — nothing appended.", file=sys.stderr)
            return 1
        targets = [selected]

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

        # Version-control stamp: default on (config), forced by --commit /
        # --no-commit. Computed once so a broadcast stamps every file the same.
        want_stamp = load_config()["stamp_commit"] if args.commit is None else args.commit
        stamp_line = None
        if want_stamp:
            ctx = gitctx.git_context()
            if ctx is not None:
                stamp_line = ctx.stamp()
            elif args.commit is True:
                print(
                    "note: --commit requested but no git commit found here; "
                    "writing without a stamp.",
                    file=sys.stderr,
                )

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
            append_note(note_path, body, when=when, header_suffix=stamp_line)
            print(f"Appended note to {note_path}")
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
