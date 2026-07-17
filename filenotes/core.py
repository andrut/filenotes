"""Shared logic for the note / ls-notes commands.

A note file is plain Markdown living next to the thing it describes:

  * notes about a file ``exp_08.npy``   ->  ``exp_08.npy.notes.md``
  * notes about the current folder      ->  ``NOTES.md``

Each note is appended as an entry that looks exactly like this::

    2026-07-16 15:07:02

    Results for using influctor device on setting 1123

Entries are delimited implicitly by their timestamp header line, so the file
stays clean, human-readable Markdown with no bookkeeping markers.
"""

from __future__ import annotations

import filecmp
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Suffix for per-file note files and the fixed name for folder notes.
NOTE_SUFFIX = ".notes.md"
FOLDER_NOTE_NAME = "NOTES.md"
ASSETS_DIRNAME = "notes-assets"

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
# Used to build collision-resistant copied-image filenames.
ASSET_STAMP_FORMAT = "%Y-%m-%d_%H%M%S"
# A line that is *only* a timestamp marks the start of a note entry.
_TIMESTAMP_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
# Markdown image: ![alt](path)
_IMAGE_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")


# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #
def is_note_file(path: Path) -> bool:
    """True if *path* is itself a note file (so we never take notes on notes)."""
    return path.name == FOLDER_NOTE_NAME or path.name.endswith(NOTE_SUFFIX)


def note_file_for(target: Optional[str]) -> Path:
    """Return the note-file path for a target.

    ``None`` or ``"."`` means the current folder -> ``NOTES.md``.
    Anything else is treated as a file path -> ``<file>.notes.md``.
    """
    if target is None or target == ".":
        return Path(FOLDER_NOTE_NAME)
    return Path(str(target) + NOTE_SUFFIX)


def source_for(note_path: Path) -> Path:
    """Return the file/folder a note file is *about* (used for sorting)."""
    if note_path.name == FOLDER_NOTE_NAME:
        return note_path.parent
    if note_path.name.endswith(NOTE_SUFFIX):
        return note_path.with_name(note_path.name[: -len(NOTE_SUFFIX)])
    return note_path


def source_label(note_path: Path) -> str:
    """Human-facing label for a note file in listings."""
    if note_path.name == FOLDER_NOTE_NAME:
        name = note_path.parent.resolve().name
        return (name + "/") if name else "./"
    return source_for(note_path).name


def sort_mtime(note_path: Path) -> float:
    """Sort key: mtime of the source file/folder, falling back to the note file."""
    source = source_for(note_path)
    for candidate in (source, note_path):
        try:
            return candidate.stat().st_mtime
        except OSError:
            continue
    return 0.0


# --------------------------------------------------------------------------- #
# Reading / writing entries
# --------------------------------------------------------------------------- #
@dataclass
class Entry:
    timestamp: Optional[datetime]
    raw_timestamp: str
    text: str

    def summary(self) -> str:
        """Collapse the entry body to a single line for short mode.

        Image markdown is replaced with a compact ``[img]`` marker so a
        wall of ``![...](...)`` links doesn't drown the text.
        """
        text = _IMAGE_MD.sub("[img]", self.text)
        return " ".join(text.split())


def append_note(note_path: Path, message: str, when: Optional[datetime] = None) -> None:
    """Append a timestamped entry to *note_path*, creating it if needed."""
    when = when or datetime.now()
    body = message.strip("\n")
    entry = f"{when.strftime(TIMESTAMP_FORMAT)}\n\n{body}\n\n"

    # Ensure earlier content is separated from the new entry by a blank line.
    prefix = ""
    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            prefix = "\n\n"
        elif existing and not existing.endswith("\n\n"):
            prefix = "\n"
    with note_path.open("a", encoding="utf-8") as fh:
        fh.write(prefix + entry)


def copy_image(note_dir: Path, src: Path, stamp: str) -> Path:
    """Copy *src* into ``<note_dir>/notes-assets/`` and return the copy's path.

    The copy is named ``<stamp>_<original-name>``. If a *different* file already
    claims that name, a numeric suffix is added so nothing is overwritten. An
    identical existing copy (e.g. the same image broadcast to sibling notes) is
    reused in place.
    """
    assets = Path(note_dir) / ASSETS_DIRNAME
    assets.mkdir(parents=True, exist_ok=True)
    base = f"{stamp}_{src.name}"
    dest = assets / base
    n = 1
    while dest.exists() and not filecmp.cmp(dest, src, shallow=False):
        stem, ext = os.path.splitext(base)
        dest = assets / f"{stem}_{n}{ext}"
        n += 1
    shutil.copy2(src, dest)
    return dest


def image_markdown(note_dir: Path, dest: Path, alt: str) -> str:
    """Render a Markdown image link from *note_dir* to the copied image."""
    rel = os.path.relpath(dest, note_dir if str(note_dir) else ".")
    # Markdown wants forward slashes even on non-POSIX filesystems.
    rel = rel.replace(os.sep, "/")
    return f"![{alt}]({rel})"


def parse_entries(text: str) -> List[Entry]:
    """Split note-file text into entries keyed by their timestamp header."""
    lines = text.splitlines()
    entries: List[Entry] = []
    idx = 0
    n = len(lines)
    while idx < n:
        if _TIMESTAMP_LINE.match(lines[idx].strip()):
            raw = lines[idx].strip()
            idx += 1
            body_lines: List[str] = []
            while idx < n and not _TIMESTAMP_LINE.match(lines[idx].strip()):
                body_lines.append(lines[idx])
                idx += 1
            try:
                ts: Optional[datetime] = datetime.strptime(raw, TIMESTAMP_FORMAT)
            except ValueError:
                ts = None
            entries.append(Entry(ts, raw, "\n".join(body_lines).strip("\n")))
        else:
            idx += 1
    return entries


def read_entries(note_path: Path) -> List[Entry]:
    try:
        text = note_path.read_text(encoding="utf-8")
    except OSError:
        return []
    return parse_entries(text)


def discover_note_files(directory: Path = Path(".")) -> List[Path]:
    """All note files in *directory* (non-recursive)."""
    found = [p for p in directory.iterdir() if is_note_file(p) and p.is_file()]
    return found


def recent_files(directory: Path = Path("."), count: int = 5) -> List[Path]:
    """The *count* most recently modified note-able files in *directory*.

    Excludes note files, dotfiles, and directories — these are candidates the
    user might want to annotate, newest first.
    """
    candidates = []
    for entry in directory.iterdir():
        if entry.name.startswith(".") or is_note_file(entry) or not entry.is_file():
            continue
        try:
            candidates.append((entry.stat().st_mtime, entry))
        except OSError:
            continue
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in candidates[:count]]


def humanize_age(mtime: float, now: Optional[float] = None) -> str:
    """A short, friendly description of how long ago *mtime* was."""
    now = now if now is not None else datetime.now().timestamp()
    delta = int(now - mtime)
    if delta < 0:
        delta = 0
    if delta < 60:
        return "just now"
    for unit, secs in (("min", 60), ("hour", 3600), ("day", 86400)):
        if delta < secs * (60 if unit == "min" else 24 if unit == "hour" else 7):
            n = delta // secs
            plural = "" if n == 1 or unit == "min" else "s"
            return f"{n} {unit}{plural} ago"
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------- #
# Terminal colors
# --------------------------------------------------------------------------- #
class Color:
    def __init__(self, stream=None) -> None:
        stream = stream or sys.stdout
        self.enabled = (
            hasattr(stream, "isatty")
            and stream.isatty()
            and os.environ.get("NO_COLOR") is None
            and os.environ.get("TERM") != "dumb"
        )

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def name(self, text: str) -> str:
        return self._wrap("1;36", text)  # bold cyan

    def time(self, text: str) -> str:
        return self._wrap("33", text)  # yellow

    def dim(self, text: str) -> str:
        return self._wrap("2", text)
