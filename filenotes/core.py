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

import base64
import filecmp
import mimetypes
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
# A line starting with a timestamp marks the start of a note entry. It may carry
# a trailing context suffix (e.g. a git provenance stamp) after the timestamp.
_TIMESTAMP_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: .*)?$")
# Markdown image: ![alt](path)
_IMAGE_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")
# Same, but capturing the prefix / path / suffix so the path can be rewritten.
_IMAGE_LINK = re.compile(r"(!\[[^\]]*\]\()([^)]*)(\))")
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


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


def append_note(
    note_path: Path,
    message: str,
    when: Optional[datetime] = None,
    header_suffix: Optional[str] = None,
) -> None:
    """Append a timestamped entry to *note_path*, creating it if needed.

    *header_suffix* (e.g. a git provenance stamp) is placed on the timestamp
    line, after the timestamp.
    """
    when = when or datetime.now()
    body = message.strip("\n")
    header = when.strftime(TIMESTAMP_FORMAT)
    if header_suffix:
        header += f" {header_suffix}"
    entry = f"{header}\n\n{body}\n\n"

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


def embed_image_markdown(src: Path, alt: str) -> str:
    """Render a Markdown image with *src* inlined as a base64 data URI.

    The note becomes self-contained — no ``notes-assets/`` copy to carry — at the
    cost of a larger file (base64 is ~33% bigger than the bytes). base64's
    alphabet has no ``)`` or ``]``, so the link stays a single well-formed token
    that the summary/link regexes still handle.
    """
    data = Path(src).read_bytes()
    mime = mimetypes.guess_type(str(src))[0] or "application/octet-stream"
    encoded = base64.b64encode(data).decode("ascii")
    return f"![{alt}](data:{mime};base64,{encoded})"


def _is_external_link(path: str) -> bool:
    """True for links that must not be rewritten (URLs, absolute, anchors)."""
    return (
        path.startswith("/")
        or path.startswith("#")
        or path.startswith("data:")
        or bool(_URL_SCHEME.match(path))
    )


def rewrite_image_links(body: str, note_dir: Path, base: Path) -> str:
    """Rewrite relative Markdown image links so they resolve from *base*.

    A note in ``sub/`` links to ``notes-assets/x.png`` relative to itself; when
    that note is concatenated into a document living in *base*, the link becomes
    ``sub/notes-assets/x.png``. External and absolute links are left untouched.
    """
    note_dir_s = str(note_dir) or "."
    base_s = str(base) or "."

    def repl(match: "re.Match") -> str:
        path = match.group(2).strip()
        if not path or _is_external_link(path):
            return match.group(0)
        target = os.path.normpath(os.path.join(note_dir_s, path))
        new = os.path.relpath(target, base_s).replace(os.sep, "/")
        return f"{match.group(1)}{new}{match.group(3)}"

    return _IMAGE_LINK.sub(repl, body)


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
            # The timestamp is the fixed-width prefix; anything after it (a git
            # stamp) is kept as part of the raw header for display.
            try:
                ts: Optional[datetime] = datetime.strptime(raw[:19], TIMESTAMP_FORMAT)
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


def walk_note_files(root: Path = Path("."), recursive: bool = False) -> List[Path]:
    """All note files under *root*.

    With ``recursive=False`` only *root* itself is scanned. With ``recursive=True``
    subfolders are walked too, skipping dotfolders and notes-assets/ directories.
    """
    if not recursive:
        return discover_note_files(root)
    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if not d.startswith(".") and d != ASSETS_DIRNAME
        ]
        for name in filenames:
            candidate = Path(dirpath) / name
            if is_note_file(candidate):
                found.append(candidate)
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


# Age units for compact_age, largest first: (suffix, seconds per unit).
# Months/years are approximations — this is a glanceable age, not a calendar.
_COMPACT_UNITS = (
    ("y", 365 * 86400),
    ("mo", 30 * 86400),
    ("w", 7 * 86400),
    ("d", 86400),
    ("h", 3600),
    ("m", 60),
)


def compact_age(when: float, now: Optional[float] = None) -> str:
    """An ultra-terse age like ``2d``, ``1h``, ``3mo`` — always rounded *down*.

    The largest unit that fits wins and the remainder is dropped, so 1h32m
    reads ``1h`` and only a full two hours reads ``2h``. Ages under a minute
    fall through to seconds (``5s``).
    """
    now = now if now is not None else datetime.now().timestamp()
    delta = int(now - when)
    if delta < 0:
        delta = 0  # clock skew / a note stamped in the future
    for suffix, size in _COMPACT_UNITS:
        if delta >= size:
            return f"{delta // size}{suffix}"
    return f"{delta}s"


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
