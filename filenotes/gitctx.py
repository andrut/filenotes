"""Version-control (git) context used to provenance-stamp notes.

Shells out to the ``git`` CLI (no dependency) to read the current commit,
branch, and dirty state. Everything degrades to ``None`` when git is missing,
the directory is not a repo, or the repo has no commits yet.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class GitContext:
    sha: str
    branch: str  # git's abbrev-ref; "HEAD" means detached
    dirty: bool

    def stamp(self) -> str:
        """One-line Markdown provenance footer."""
        head = "detached" if self.branch == "HEAD" else self.branch
        line = f"— `{head}` @ `{self.sha}`"
        if self.dirty:
            line += " (dirty)"
        return line


def _git(args: List[str], cwd: Optional[str]) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return None  # git not installed
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def git_context(cwd: Optional[Path] = None) -> Optional[GitContext]:
    """Return the git context for *cwd*, or None if unavailable."""
    where = str(cwd) if cwd is not None else None
    if _git(["rev-parse", "--is-inside-work-tree"], where) != "true":
        return None
    sha = _git(["rev-parse", "--short", "HEAD"], where)
    if not sha:
        return None  # repo exists but has no commits yet
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], where) or "HEAD"
    # Only tracked changes count as dirty; untracked files (which include the
    # notes and assets this tool creates) would otherwise mark every note dirty.
    dirty = bool(_git(["status", "--porcelain", "--untracked-files=no"], where))
    return GitContext(sha=sha, branch=branch, dirty=dirty)
