"""Tests for the recently-used note-directory MRU (filenotes.history).

The autouse ``_isolate_history`` fixture (conftest) points FILENOTES_HISTORY at
a throwaway file, so these exercise a real on-disk store without touching the
user's state directory.
"""

from pathlib import Path

from filenotes import history


def test_record_then_read_roundtrip(tmp_path):
    d = tmp_path / "expA"
    d.mkdir()
    history.record_dir(d)
    assert history.recent_dirs() == [d.resolve()]


def test_mru_order_and_dedup(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    history.record_dir(a)
    history.record_dir(b)
    history.record_dir(a)  # touching a again moves it to the front, no dup
    assert history.recent_dirs() == [a.resolve(), b.resolve()]


def test_relative_paths_resolve_to_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    history.record_dir(Path("sub"))
    assert history.recent_dirs() == [(tmp_path / "sub").resolve()]


def test_capped_at_max_entries(tmp_path):
    made = []
    for i in range(history.MAX_ENTRIES + 5):
        d = tmp_path / f"d{i:02d}"
        d.mkdir()
        made.append(d)
        history.record_dir(d)
    recent = history.recent_dirs()
    assert len(recent) == history.MAX_ENTRIES
    # The newest MAX_ENTRIES survive, most-recent first; the oldest fall off.
    assert recent[0] == made[-1].resolve()
    assert made[0].resolve() not in recent


def test_existing_only_filters_deleted_dirs(tmp_path):
    keep = tmp_path / "keep"
    gone = tmp_path / "gone"
    keep.mkdir()
    gone.mkdir()
    history.record_dir(keep)
    history.record_dir(gone)
    gone.rmdir()
    assert history.recent_dirs() == [keep.resolve()]  # default existing_only
    # ...but the raw record is still there when asked for.
    assert gone.resolve() in history.recent_dirs(existing_only=False)


def test_recent_dir_entries_carries_timestamps(tmp_path):
    d = tmp_path / "e"
    d.mkdir()
    history.record_dir(d)
    (path, ts), = history.recent_dir_entries()
    assert path == d.resolve()
    assert ts > 0


def test_count_limits_results(tmp_path):
    for name in ("x", "y", "z"):
        (tmp_path / name).mkdir()
        history.record_dir(tmp_path / name)
    assert len(history.recent_dirs(count=2)) == 2


def test_corrupt_store_reads_as_empty(monkeypatch, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not json")
    monkeypatch.setenv("FILENOTES_HISTORY", str(bad))
    assert history.recent_dirs() == []
    # ...and recording over a corrupt file still works.
    d = tmp_path / "ok"
    d.mkdir()
    history.record_dir(d)
    assert history.recent_dirs() == [d.resolve()]


def test_unwritable_store_never_raises(monkeypatch, tmp_path):
    # Parent path is a file, so mkdir/replace can't succeed -> must stay silent.
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    monkeypatch.setenv("FILENOTES_HISTORY", str(blocker / "sub" / "recent.json"))
    history.record_dir(tmp_path)  # should not raise
    assert history.recent_dirs() == []
