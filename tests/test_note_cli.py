import io
import os
from pathlib import Path

from filenotes import note as note_cli
from filenotes.capture import CaptureError
from filenotes.core import read_entries


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


def _setup_selector(tmp_path, monkeypatch, answer):
    """Run the recent-file selector against a fake interactive terminal."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FILENOTES_CONFIG", str(tmp_path / "no-config.toml"))
    monkeypatch.delenv("FILENOTES_RECENT_COUNT", raising=False)
    for i, name in enumerate(["oldest.npy", "newest.log"]):
        p = Path(name)
        p.write_text("data")
        os.utime(p, (2000 + i * 100, 2000 + i * 100))
    monkeypatch.setattr(note_cli.sys, "stdin", FakeTTY())
    monkeypatch.setattr(note_cli.sys, "stderr", FakeTTY())
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)


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


def test_selector_picks_newest(tmp_path, monkeypatch):
    _setup_selector(tmp_path, monkeypatch, answer="1")
    rc = note_cli.main(["-m", "from selector"])
    assert rc == 0
    # Option 1 is the newest file.
    assert read_entries(Path("newest.log.notes.md"))[0].text == "from selector"
    assert not Path("oldest.npy.notes.md").exists()


def test_selector_cancel(tmp_path, monkeypatch):
    _setup_selector(tmp_path, monkeypatch, answer="q")
    rc = note_cli.main(["-m", "from selector"])
    assert rc == 1
    assert not list(Path(".").glob("*.notes.md"))


def test_note_auto_stamps_in_repo(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    monkeypatch.setenv("FILENOTES_CONFIG", str(git_repo / "no-config.toml"))
    monkeypatch.delenv("FILENOTES_STAMP_COMMIT", raising=False)

    rc = note_cli.main(["model.py", "-m", "0.92 accuracy"])
    assert rc == 0
    text = read_entries(Path("model.py.notes.md"))[0].text
    assert "0.92 accuracy" in text
    assert "@ `" in text and "`main`" in text


def test_no_commit_flag_suppresses_stamp(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    monkeypatch.setenv("FILENOTES_CONFIG", str(git_repo / "no-config.toml"))
    monkeypatch.delenv("FILENOTES_STAMP_COMMIT", raising=False)

    rc = note_cli.main(["model.py", "-m", "no stamp", "--no-commit"])
    assert rc == 0
    text = read_entries(Path("model.py.notes.md"))[0].text
    assert text == "no stamp"


def test_config_can_disable_stamp(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    monkeypatch.setenv("FILENOTES_CONFIG", str(git_repo / "no-config.toml"))
    monkeypatch.setenv("FILENOTES_STAMP_COMMIT", "false")

    note_cli.main(["model.py", "-m", "plain"])
    assert read_entries(Path("model.py.notes.md"))[0].text == "plain"


def test_stamp_after_message_before_images(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    monkeypatch.setenv("FILENOTES_CONFIG", str(git_repo / "no-config.toml"))
    monkeypatch.delenv("FILENOTES_STAMP_COMMIT", raising=False)
    Path("p.png").write_bytes(b"IMG")

    note_cli.main(["model.py", "-m", "result", "-i", "p.png"])
    text = read_entries(Path("model.py.notes.md"))[0].text
    assert text.index("result") < text.index("@ `") < text.index("![")


def test_dot_target_still_writes_folder_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = note_cli.main([".", "-m", "folder log"])
    assert rc == 0
    entries = read_entries(Path("NOTES.md"))
    assert len(entries) == 1
    assert entries[0].text == "folder log"
