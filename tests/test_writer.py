"""Tests for the headless note-writing core (filenotes.writer).

This is the API every front-end (CLI, GUI) funnels through, so these lock in
its contract independently of any argv/stdout wrapper.
"""

from datetime import datetime
from pathlib import Path

import pytest

from filenotes.core import read_entries
from filenotes.writer import NoteError, write_note


def test_writes_single_target(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("data.csv").touch()

    result = write_note(["data.csv"], "a plain note", stamp_commit=False)

    assert result.note_paths == [Path("data.csv.notes.md")]
    assert read_entries(Path("data.csv.notes.md"))[0].text == "a plain note"


def test_dot_and_none_target_write_folder_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for target in (".", None):
        write_note([target], f"folder via {target!r}", stamp_commit=False)
    entries = read_entries(Path("NOTES.md"))
    assert [e.text for e in entries] == ["folder via '.'", "folder via None"]


def test_broadcast_shares_one_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("a.npy", "b.npy", "c.npy"):
        Path(name).touch()

    result = write_note(["a.npy", "b.npy", "c.npy"], "shared", stamp_commit=False)

    assert len(result.note_paths) == 3
    stamps = {
        read_entries(Path(name + ".notes.md"))[0].raw_timestamp
        for name in ("a.npy", "b.npy", "c.npy")
    }
    assert len(stamps) == 1


def test_images_copied_and_linked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("run.npy").touch()
    Path("p.png").write_bytes(b"IMG")

    write_note(["run.npy"], "caption", images=[Path("p.png")], stamp_commit=False)

    entry = read_entries(Path("run.npy.notes.md"))[0]
    assert entry.text.index("caption") < entry.text.index("![")
    assert len(list(Path("notes-assets").iterdir())) == 1


def test_empty_message_with_image_still_writes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("run.npy").touch()
    Path("p.png").write_bytes(b"IMG")

    write_note(["run.npy"], "", images=[Path("p.png")], stamp_commit=False)

    text = read_entries(Path("run.npy.notes.md"))[0].text
    assert text.startswith("![") and "notes-assets/" in text


def test_when_pins_the_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("run.npy").touch()
    when = datetime(2021, 3, 4, 5, 6, 7)

    write_note(["run.npy"], "fixed", when=when, stamp_commit=False)

    assert read_entries(Path("run.npy.notes.md"))[0].raw_timestamp == "2021-03-04 05:06:07"


def test_note_file_target_is_rejected_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("a.npy").touch()

    with pytest.raises(NoteError, match="refusing to nest notes"):
        write_note(["a.npy", "a.npy.notes.md"], "nope", stamp_commit=False)
    # A rejected broadcast writes nothing at all.
    assert not Path("a.npy.notes.md").exists()


def test_missing_image_is_rejected_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("a.npy").touch()

    with pytest.raises(NoteError, match="image not found"):
        write_note(["a.npy"], "x", images=[Path("gone.png")], stamp_commit=False)
    assert not Path("a.npy.notes.md").exists()
    assert not Path("notes-assets").exists()


def test_stamp_applied_in_repo(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)

    result = write_note(["model.py"], "0.92 acc", stamp_commit=True)

    assert result.stamp_line is not None and "`main`" in result.stamp_line
    assert not result.stamp_requested_but_missing
    assert "@ `" in read_entries(Path("model.py.notes.md"))[0].raw_timestamp


def test_stamp_wanted_but_no_git_is_reported(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("x.dat").touch()

    result = write_note(["x.dat"], "note", stamp_commit=True)

    # Note is still written, just without a stamp; the caller is told.
    assert result.stamp_line is None
    assert result.stamp_requested_but_missing is True
    assert read_entries(Path("x.dat.notes.md"))[0].text == "note"


def test_stamp_commit_none_uses_config_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FILENOTES_CONFIG", str(tmp_path / "none.toml"))
    monkeypatch.setenv("FILENOTES_STAMP_COMMIT", "false")
    Path("x.dat").touch()

    result = write_note(["x.dat"], "note")  # stamp_commit defaults to None

    assert result.stamp_line is None
    assert result.stamp_requested_but_missing is False
