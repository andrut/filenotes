from datetime import datetime
from pathlib import Path

from filenotes.core import (
    append_note,
    is_note_file,
    note_file_for,
    parse_entries,
    read_entries,
    source_for,
    source_label,
)


def test_note_file_for():
    assert note_file_for("exp_08.npy") == Path("exp_08.npy.notes.md")
    assert note_file_for(None) == Path("NOTES.md")
    assert note_file_for(".") == Path("NOTES.md")


def test_is_note_file():
    assert is_note_file(Path("exp_08.npy.notes.md"))
    assert is_note_file(Path("NOTES.md"))
    assert not is_note_file(Path("exp_08.npy"))


def test_source_for():
    assert source_for(Path("exp_08.npy.notes.md")) == Path("exp_08.npy")
    assert source_for(Path("sub/NOTES.md")) == Path("sub")


def test_append_and_parse_roundtrip(tmp_path):
    note = tmp_path / "x.npy.notes.md"
    append_note(note, "first note", when=datetime(2026, 7, 16, 15, 7, 2))
    append_note(note, "second note\nwith two lines", when=datetime(2026, 7, 16, 16, 0, 0))

    entries = read_entries(note)
    assert len(entries) == 2
    assert entries[0].text == "first note"
    assert entries[0].raw_timestamp == "2026-07-16 15:07:02"
    assert entries[1].text == "second note\nwith two lines"
    assert entries[1].summary() == "second note with two lines"


def test_parse_ignores_non_timestamp_preamble():
    text = "some markdown heading\n\n2026-07-16 15:07:02\n\nhello\n"
    entries = parse_entries(text)
    assert len(entries) == 1
    assert entries[0].text == "hello"


def test_source_label_folder(tmp_path):
    note = tmp_path / "NOTES.md"
    note.write_text("2026-07-16 15:07:02\n\nhi\n")
    assert source_label(note).endswith("/")
