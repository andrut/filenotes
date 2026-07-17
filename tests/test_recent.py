import os
from pathlib import Path

from filenotes.core import humanize_age, recent_files


def _touch(path: Path, mtime: float):
    path.write_text("x")
    os.utime(path, (mtime, mtime))


def test_recent_files_order_and_exclusions(tmp_path):
    _touch(tmp_path / "a.npy", 1000)
    _touch(tmp_path / "b.npy", 2000)
    _touch(tmp_path / "c.npy", 3000)
    _touch(tmp_path / "old.notes.md", 4000)  # note file, excluded
    _touch(tmp_path / "NOTES.md", 4000)       # folder note, excluded
    _touch(tmp_path / ".hidden", 5000)        # dotfile, excluded
    (tmp_path / "sub").mkdir()                 # directory, excluded

    got = [p.name for p in recent_files(tmp_path, 5)]
    assert got == ["c.npy", "b.npy", "a.npy"]


def test_recent_files_respects_count(tmp_path):
    for i in range(6):
        _touch(tmp_path / f"f{i}.dat", 1000 + i)
    got = recent_files(tmp_path, 2)
    assert [p.name for p in got] == ["f5.dat", "f4.dat"]


def test_humanize_age():
    now = 1_000_000.0
    assert humanize_age(now - 5, now) == "just now"
    assert humanize_age(now - 90, now) == "1 min ago"
    assert humanize_age(now - 130, now) == "2 min ago"
    assert humanize_age(now - 3700, now) == "1 hour ago"
    assert humanize_age(now - 7300, now) == "2 hours ago"
    assert humanize_age(now - 90000, now) == "1 day ago"
    # older than a week falls back to an absolute date
    assert "-" in humanize_age(now - 30 * 86400, now)
