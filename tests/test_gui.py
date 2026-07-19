"""Offscreen smoke/logic tests for the PySide6 GUI.

Skipped entirely when PySide6 is absent, so the core suite stays Qt-free. When
present they run headless (QT_QPA_PLATFORM=offscreen) and drive the window's
logic directly rather than through native dialogs.
"""

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from filenotes import history  # noqa: E402
from filenotes.core import read_entries  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from filenotes.gui.window import NoteWindow

    win = NoteWindow()
    yield win
    win.close()


def test_default_context_is_folder_note_in_cwd(window, tmp_path):
    base, target = window.context.current_context()
    assert target == "."
    assert Path(base).resolve() == tmp_path.resolve()


def test_save_writes_folder_note(window, tmp_path):
    window.editor.setPlainText("note from the gui")
    window._on_save()
    entries = read_entries(tmp_path / "NOTES.md")
    assert len(entries) == 1
    assert entries[0].text == "note from the gui"


def test_save_targets_a_file_in_the_folder(window, tmp_path):
    (tmp_path / "run.dat").touch()
    window.context._set_folder(tmp_path)
    # Simulate choosing the file target.
    window.context.target_combo.addItem("run.dat", ("file", "run.dat"))
    window.context.target_combo.setCurrentIndex(window.context.target_combo.count() - 1)
    window.editor.setPlainText("about the run")
    window._on_save()
    assert (tmp_path / "run.dat.notes.md").is_file()
    assert not (tmp_path / "NOTES.md").exists()


def test_attached_image_is_copied_and_linked(window, tmp_path):
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    window._add_image(img)
    # isHidden reflects our explicit setVisible even when the top-level window
    # is never shown (offscreen), unlike isVisible.
    assert not window.thumbs.isHidden()
    window.editor.setPlainText("with an image")
    window._on_save()
    text = read_entries(tmp_path / "NOTES.md")[0].text
    assert "![" in text and "notes-assets/" in text
    assert len(list((tmp_path / "notes-assets").iterdir())) == 1


def test_removing_the_only_image_hides_strip(window, tmp_path):
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG\r\n")
    window._add_image(img)
    thumb = window.thumbs_layout.itemAt(0).widget()
    window._remove_thumbnail(thumb)
    assert window._images == []
    assert window.thumbs.isHidden()


def test_save_disabled_until_there_is_content(window):
    assert not window.save_btn.isEnabled()
    window.editor.setPlainText("something")
    assert window.save_btn.isEnabled()
    window.editor.setPlainText("")
    assert not window.save_btn.isEnabled()


def test_save_records_history(window, tmp_path):
    window.editor.setPlainText("recorded")
    window._on_save()
    assert tmp_path.resolve() in history.recent_dirs()


def test_note_file_target_is_rejected(window, tmp_path, monkeypatch):
    # Force an illegal target (a note file) and confirm the error path is hit
    # without writing anything.
    window.context.target_combo.addItem("NOTES.md", ("file", "NOTES.md"))
    window.context.target_combo.setCurrentIndex(window.context.target_combo.count() - 1)
    window.editor.setPlainText("should not persist")

    shown = {}
    from filenotes.gui import window as window_mod

    monkeypatch.setattr(
        window_mod.QMessageBox, "critical", lambda *a, **k: shown.setdefault("hit", a)
    )
    window._on_save()
    assert "hit" in shown
    assert not (tmp_path / "NOTES.md.notes.md").exists()
