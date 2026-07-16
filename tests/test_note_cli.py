from pathlib import Path

from filenotes import note as note_cli
from filenotes.capture import CaptureError
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


def test_attach_images(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("after.npy").touch()
    Path("p1.png").write_bytes(b"PNG-A")
    Path("p2.png").write_bytes(b"PNG-B")

    rc = note_cli.main(["after.npy", "-m", "readings", "-i", "p1.png", "-i", "p2.png"])
    assert rc == 0

    entries = read_entries(Path("after.npy.notes.md"))
    assert entries[0].text.startswith("readings")
    assert entries[0].text.count("![") == 2
    assert "notes-assets/" in entries[0].text
    # Short summary collapses image markdown.
    assert entries[0].summary() == "readings [img] [img]"

    copies = sorted(Path("notes-assets").iterdir())
    assert len(copies) == 2
    # Copy is frozen against regeneration of the original.
    frozen = next(c for c in copies if c.name.endswith("p1.png")).read_bytes()
    Path("p1.png").write_bytes(b"REGENERATED")
    assert frozen == b"PNG-A"


def test_missing_image_aborts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("after.npy").touch()
    rc = note_cli.main(["after.npy", "-m", "x", "-i", "nope.png"])
    assert rc == 2
    assert not Path("after.npy.notes.md").exists()
    assert not Path("notes-assets").exists()


def test_broadcast_images_share_one_copy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("a.npy", "b.npy"):
        Path(name).touch()
    Path("shared.png").write_bytes(b"IMG")

    rc = note_cli.main(["a.npy", "b.npy", "-m", "shared", "-i", "shared.png"])
    assert rc == 0
    # One physical copy, linked from both notes.
    assert len(list(Path("notes-assets").iterdir())) == 1
    for name in ("a.npy", "b.npy"):
        assert "shared.png" in read_entries(Path(name + ".notes.md"))[0].text


def test_screenshot_capture_wiring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("run.npy").touch()

    def fake_capture(dest):
        Path(dest).write_bytes(b"FAKEPNG")
        return "faketool"

    monkeypatch.setattr(note_cli.capture_mod, "capture_fullscreen", fake_capture)

    rc = note_cli.main(["run.npy", "-m", "state", "-S"])
    assert rc == 0
    text = read_entries(Path("run.npy.notes.md"))[0].text
    assert "![screenshot.png](notes-assets/" in text
    # The captured image was copied into notes-assets with the frozen bytes.
    copy = next(Path("notes-assets").iterdir())
    assert copy.read_bytes() == b"FAKEPNG"


def test_capture_failure_aborts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("run.npy").touch()

    def boom(dest):
        raise CaptureError("no image in clipboard")

    monkeypatch.setattr(note_cli.capture_mod, "capture_clipboard", boom)

    rc = note_cli.main(["run.npy", "-m", "x", "-C"])
    assert rc == 2
    assert not Path("run.npy.notes.md").exists()
    assert not Path("notes-assets").exists()


def test_no_target_writes_folder_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = note_cli.main(["-m", "folder log"])
    assert rc == 0
    entries = read_entries(Path("NOTES.md"))
    assert len(entries) == 1
    assert entries[0].text == "folder log"
