import os
from pathlib import Path

from filenotes import note as note_cli
from filenotes.core import read_entries


def test_broadcast_writes_same_note_to_each(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("a.npy", "b.npy", "c.npy"):
        Path(name).touch()

    rc = note_cli.main(["a.npy", "b.npy", "c.npy", "-m", "shared note"])
    assert rc == 0

    stamps = set()
    for name in ("a.npy", "b.npy", "c.npy"):
        entries = read_entries(Path(name + ".notes.md"))
        assert len(entries) == 1
        assert entries[0].text == "shared note"
        stamps.add(entries[0].raw_timestamp)
    # A broadcast shares a single timestamp across all files.
    assert len(stamps) == 1


def test_guard_aborts_whole_broadcast(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    Path("a.npy").touch()

    rc = note_cli.main(["a.npy", "a.npy.notes.md", "-m", "nope"])
    assert rc == 2
    # Nothing was written because validation happens before any append.
    assert not Path("a.npy.notes.md").exists()


def test_no_target_writes_folder_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = note_cli.main(["-m", "folder log"])
    assert rc == 0
    entries = read_entries(Path("NOTES.md"))
    assert len(entries) == 1
    assert entries[0].text == "folder log"
