"""Headless note-writing core, shared by every front-end.

The CLI (:mod:`filenotes.note`) and any GUI both funnel through
:func:`write_note`, so "what a note *is*" — validation, copying attachments
into ``notes-assets/``, the git provenance stamp, a single shared timestamp for
a broadcast — lives in exactly one place and can't drift between front-ends.

This module never prints, never reads argv, and never captures screenshots.
Callers gather the message and any images (including captured ones) however
they like, then hand them here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from . import gitctx, history
from .config import load_config
from .core import (
    ASSET_STAMP_FORMAT,
    append_note,
    copy_image,
    image_markdown,
    is_note_file,
    note_file_for,
)


class NoteError(Exception):
    """Raised for bad input (a note-file target, a missing image)."""


def validate_targets(targets: Iterable[Optional[str]]) -> None:
    """Reject targets that are themselves note files, so notes never nest."""
    for target in targets:
        if target is not None and target != "." and is_note_file(Path(target)):
            raise NoteError(
                f"'{target}' is itself a note file; refusing to nest notes."
            )


def validate_images(images: Iterable[Path]) -> None:
    """Reject image paths that do not point at an existing file."""
    for img in images:
        if not Path(img).is_file():
            raise NoteError(f"image not found: '{img}'")


@dataclass
class WriteResult:
    note_paths: List[Path]
    # The git stamp actually applied (or None when there was none).
    stamp_line: Optional[str]
    # True when a stamp was wanted but no git context was available. Front-ends
    # may surface this (e.g. warn only when the user *explicitly* asked).
    stamp_requested_but_missing: bool


def write_note(
    targets: Iterable[Optional[str]],
    message: str,
    images: Iterable[Path] = (),
    *,
    stamp_commit: Optional[bool] = None,
    when: Optional[datetime] = None,
    record: bool = True,
) -> WriteResult:
    """Append one timestamped note to each target's note file.

    *targets* are file paths, ``"."``/``None`` for the current folder, or a mix
    (a broadcast writes the same note to each). *images* are existing files that
    get copied into each note's ``notes-assets/`` and linked after the message.

    *stamp_commit* controls the git provenance stamp: ``None`` uses the config
    default, ``True``/``False`` forces it on/off. *when* pins the timestamp (all
    targets in one call share it); it defaults to now.

    Raises :class:`NoteError` on bad input *before* writing anything, so a
    broadcast is never left half-written.

    On success each written note's directory is pushed onto the recently-used
    MRU list (:mod:`filenotes.history`) so front-ends can suggest it later; pass
    ``record=False`` to skip that.
    """
    targets = list(targets)
    images = [Path(p) for p in images]
    validate_targets(targets)
    validate_images(images)

    if stamp_commit is None:
        stamp_commit = bool(load_config()["stamp_commit"])

    when = when or datetime.now()

    stamp_line: Optional[str] = None
    stamp_missing = False
    if stamp_commit:
        ctx = gitctx.git_context()
        if ctx is not None:
            stamp_line = ctx.stamp()
        else:
            stamp_missing = True

    # One asset stamp so a broadcast shares image copies by name/timestamp.
    asset_stamp = when.strftime(ASSET_STAMP_FORMAT)
    body_message = (message or "").strip("\n")

    written: List[Path] = []
    for target in targets:
        note_path = note_file_for(target)
        note_dir = note_path.parent
        img_lines = []
        for img in images:
            dest = copy_image(note_dir, img, asset_stamp)
            img_lines.append(image_markdown(note_dir, dest, img.name))
        body = "\n\n".join(p for p in [body_message, *img_lines] if p)
        append_note(note_path, body, when=when, header_suffix=stamp_line)
        written.append(note_path)

    if record:
        seen = set()
        for note_path in written:
            note_dir = note_path.parent
            if str(note_dir) not in seen:
                seen.add(str(note_dir))
                history.record_dir(note_dir)

    return WriteResult(written, stamp_line, stamp_missing)
