"""Recently-used note directories (an MRU list), for context suggestions.

The CLI and GUI both record the directory a note was written to via
:func:`record_dir`; a front-end reads :func:`recent_dirs` to pre-fill its
context chooser (e.g. the coming GUI). Storage is a small JSON list in an XDG
*state* directory (``$XDG_STATE_HOME/filenotes/recent-dirs.json``, i.e.
``~/.local/state/filenotes/...``), overridable with ``$FILENOTES_HISTORY``.

Every operation is best-effort: a missing, unreadable, corrupt, or unwritable
store never raises, so history bookkeeping can never break note-taking.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

# Cap the stored list so it can't grow without bound.
MAX_ENTRIES = 20


def history_path() -> Path:
    override = os.environ.get("FILENOTES_HISTORY")
    if override:
        return Path(override)
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "filenotes" / "recent-dirs.json"


def _load_raw() -> List[dict]:
    """Return the stored entries (MRU-ordered), or [] on any problem."""
    try:
        data = json.loads(history_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or not isinstance(data.get("dirs"), list):
        return []
    clean: List[dict] = []
    for entry in data["dirs"]:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            try:
                ts = float(entry.get("ts", 0) or 0)
            except (TypeError, ValueError):
                ts = 0.0
            clean.append({"path": entry["path"], "ts": ts})
    return clean


def _atomic_write(entries: List[dict]) -> None:
    """Write *entries* via a temp file + rename; swallow any IO error."""
    path = history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), prefix=".recent-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "dirs": entries}, fh)
            os.replace(tmp, path)
        finally:
            try:
                os.unlink(tmp)  # no-op once replace() consumed it
            except OSError:
                pass
    except OSError:
        pass  # best-effort; never break the caller


def record_dir(directory) -> None:
    """Push *directory* to the front of the MRU list (deduped, capped)."""
    try:
        resolved = str(Path(directory).resolve())
    except OSError:
        return
    entries = [e for e in _load_raw() if e["path"] != resolved]
    entries.insert(0, {"path": resolved, "ts": time.time()})
    del entries[MAX_ENTRIES:]
    _atomic_write(entries)


def recent_dir_entries(
    count: Optional[int] = None, existing_only: bool = True
) -> List[Tuple[Path, float]]:
    """Recent (dir, last-used-epoch) pairs, most-recent first."""
    pairs: List[Tuple[Path, float]] = []
    for entry in _load_raw():
        p = Path(entry["path"])
        if existing_only and not p.is_dir():
            continue
        pairs.append((p, entry["ts"]))
    return pairs if count is None else pairs[:count]


def recent_dirs(count: Optional[int] = None, existing_only: bool = True) -> List[Path]:
    """Recent note directories, most-recent first."""
    return [p for p, _ in recent_dir_entries(count, existing_only)]
