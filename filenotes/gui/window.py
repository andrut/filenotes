"""The note window: context chooser, text, attachments, save.

Minimal by default — the attachment controls hide behind a single ``＋ Attach``
menu and captured/attached images only appear once they exist. All the real
work (copying assets, git stamp, history) is delegated to
:func:`filenotes.writer.write_note`, so this stays thin UI glue.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import capture as capture_mod
from ..writer import NoteError, write_note
from .context import ContextChooser
from .workers import CaptureWorker

_IMAGE_FILTER = (
    "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff);;All files (*)"
)


class _Thumbnail(QFrame):
    """A small preview chip with a remove button for one attached image."""

    def __init__(self, path: Path, on_remove) -> None:
        super().__init__()
        self.path = path
        self.setFrameShape(QFrame.StyledPanel)

        preview = QLabel()
        preview.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            preview.setPixmap(
                pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            preview.setText("file")

        name = QLabel()
        name.setToolTip(str(path))
        name.setText(name.fontMetrics().elidedText(path.name, Qt.ElideMiddle, 84))

        remove = QToolButton()
        remove.setText("✕")
        remove.setAutoRaise(True)
        remove.setToolTip("Remove")
        remove.clicked.connect(lambda: on_remove(self))

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch(1)
        top.addWidget(remove)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 4)
        lay.setSpacing(1)
        lay.addLayout(top)
        lay.addWidget(preview)
        lay.addWidget(name, 0, Qt.AlignCenter)


class NoteWindow(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New note — filenotes")
        self.resize(560, 500)

        self._images: List[Path] = []
        self._tmpdir: Optional[str] = None
        self._worker: Optional[CaptureWorker] = None

        self.context = ContextChooser()

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Write your note…   (⌘⏎ / Ctrl+Enter to save)")

        # Attachments hide behind one button until used (progressive disclosure).
        self.attach_btn = QToolButton()
        self.attach_btn.setText("＋ Attach")
        self.attach_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.attach_btn)
        menu.addAction("Image file…", self._attach_files)
        menu.addSeparator()
        menu.addAction(
            "Screenshot (full screen)",
            lambda: self._start_capture(
                capture_mod.capture_fullscreen, "screenshot.png", hide=True
            ),
        )
        menu.addAction(
            "Screenshot (region)",
            lambda: self._start_capture(
                capture_mod.capture_region, "region.png", hide=True
            ),
        )
        menu.addAction(
            "Paste image from clipboard",
            lambda: self._start_capture(
                capture_mod.capture_clipboard, "clipboard.png", hide=False
            ),
        )
        self.attach_btn.setMenu(menu)

        self.status = QLabel("")
        self.status.setStyleSheet("color: gray;")

        # Thumbnail strip: hidden until there is at least one attachment.
        self.thumbs = QWidget()
        self.thumbs_layout = QHBoxLayout(self.thumbs)
        self.thumbs_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbs_layout.addStretch(1)
        self.thumbs.setVisible(False)

        attach_row = QHBoxLayout()
        attach_row.addWidget(self.attach_btn)
        attach_row.addWidget(self.status, 1)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.save_btn = QPushButton("Save note")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)

        lay = QVBoxLayout(self)
        lay.addWidget(self.context)
        lay.addWidget(self.editor, 1)
        lay.addWidget(self.thumbs)
        lay.addLayout(attach_row)
        lay.addLayout(btn_row)

        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(seq), self).activated.connect(self._on_save)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_cancel)

        self.editor.textChanged.connect(self._update_save_enabled)
        self._update_save_enabled()
        self.editor.setFocus()

    # -- attachments ------------------------------------------------------ #
    def _ensure_tmpdir(self) -> str:
        if self._tmpdir is None:
            self._tmpdir = tempfile.mkdtemp(prefix="notes-gui-")
        return self._tmpdir

    def _attach_files(self) -> None:
        base = str(self.context.current_context()[0])
        files, _ = QFileDialog.getOpenFileNames(
            self, "Attach images", base, _IMAGE_FILTER
        )
        for f in files:
            self._add_image(Path(f))

    def _start_capture(self, fn, name: str, hide: bool) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        dest = os.path.join(self._ensure_tmpdir(), f"{len(self._images) + 1:02d}_{name}")
        self.attach_btn.setEnabled(False)
        self.status.setText("Capturing…")
        if hide:
            self.hide()
        worker = CaptureWorker(fn, dest, self)
        worker.done.connect(self._on_capture_done)
        worker.failed.connect(self._on_capture_failed)
        worker.finished.connect(lambda: self.attach_btn.setEnabled(True))
        self._worker = worker
        worker.start()

    def _restore(self) -> None:
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        self.editor.setFocus()

    def _on_capture_done(self, path: str, tool: str) -> None:
        self._restore()
        self.status.setText(f"Captured via {tool}")
        self._add_image(Path(path))

    def _on_capture_failed(self, message: str) -> None:
        self._restore()
        self.status.setText("")
        QMessageBox.warning(self, "Capture failed", message)

    def _add_image(self, path: Path) -> None:
        self._images.append(path)
        thumb = _Thumbnail(path, self._remove_thumbnail)
        self.thumbs_layout.insertWidget(self.thumbs_layout.count() - 1, thumb)
        self.thumbs.setVisible(True)
        self._update_save_enabled()

    def _remove_thumbnail(self, thumb: _Thumbnail) -> None:
        try:
            self._images.remove(thumb.path)
        except ValueError:
            pass
        thumb.setParent(None)
        thumb.deleteLater()
        if not self._images:
            self.thumbs.setVisible(False)
        self._update_save_enabled()

    # -- save / cancel ---------------------------------------------------- #
    def _update_save_enabled(self) -> None:
        has_content = bool(self.editor.toPlainText().strip()) or bool(self._images)
        self.save_btn.setEnabled(has_content)

    def _on_save(self) -> None:
        base, target = self.context.current_context()
        message = self.editor.toPlainText().strip()
        if not message and not self._images:
            return
        try:
            result = write_note([target], message, list(self._images), base=base)
        except (NoteError, OSError) as exc:
            QMessageBox.critical(self, "Could not save note", str(exc))
            return
        for note_path in result.note_paths:
            print(f"Appended note to {note_path}")
        self._cleanup()
        self.close()

    def _on_cancel(self) -> None:
        self._cleanup()
        self.close()

    def _cleanup(self) -> None:
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
            self._tmpdir = None

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._cleanup()
        super().closeEvent(event)
