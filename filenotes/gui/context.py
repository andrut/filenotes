"""The context chooser: pick which folder/file the note attaches to.

Pre-fills from the recently-used-directory history (:mod:`filenotes.history`)
so the common case — annotate where you were just working — needs no clicks,
while a folder ``Browse…`` and a per-folder file list cover everything else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import history
from ..core import recent_files

RECENT_FILES_SHOWN = 8

# target_combo item payloads
_FOLDER_NOTE = ("folder", ".")
_CHOOSE_FILE = ("choose", None)


def _display(path: Path) -> str:
    """A compact, home-relative label for a directory."""
    try:
        home = Path.home()
        if path == home or home in path.parents:
            rel = path.relative_to(home)
            return "~" if str(rel) == "." else f"~/{rel}"
    except (ValueError, RuntimeError):
        pass
    return str(path)


class ContextChooser(QWidget):
    """Two combos — folder, then note target within that folder."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._folder: Path = Path.cwd()

        self.folder_combo = QComboBox()
        self.folder_combo.setToolTip("Recently used note folders")
        browse = QToolButton()
        browse.setText("Browse…")
        browse.clicked.connect(self._browse_folder)

        self.target_combo = QComboBox()
        self.target_combo.setToolTip("The folder note, or a file in this folder")

        frow = QHBoxLayout()
        frow.addWidget(QLabel("Folder"))
        frow.addWidget(self.folder_combo, 1)
        frow.addWidget(browse)

        trow = QHBoxLayout()
        trow.addWidget(QLabel("Note on"))
        trow.addWidget(self.target_combo, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(frow)
        lay.addLayout(trow)

        self._populate_folders()
        self.folder_combo.currentIndexChanged.connect(self._on_folder_changed)
        self.target_combo.activated.connect(self._on_target_activated)
        self._populate_targets()

    # -- folders ---------------------------------------------------------- #
    def _populate_folders(self) -> None:
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        dirs = history.recent_dirs() or [Path.cwd()]
        seen = []
        for d in dirs:
            r = d.resolve()
            if r not in seen:
                seen.append(r)
        for d in seen:
            self.folder_combo.addItem(_display(d), str(d))
        self.folder_combo.setCurrentIndex(0)
        self._folder = Path(self.folder_combo.itemData(0))
        self.folder_combo.blockSignals(False)

    def _browse_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose folder", str(self._folder)
        )
        if chosen:
            self._set_folder(Path(chosen))

    def _set_folder(self, folder: Path) -> None:
        folder = folder.resolve()
        idx = self.folder_combo.findData(str(folder))
        self.folder_combo.blockSignals(True)
        if idx < 0:
            self.folder_combo.insertItem(0, _display(folder), str(folder))
            idx = 0
        self.folder_combo.setCurrentIndex(idx)
        self.folder_combo.blockSignals(False)
        self._folder = folder
        self._populate_targets()

    def _on_folder_changed(self, idx: int) -> None:
        data = self.folder_combo.itemData(idx)
        if data:
            self._folder = Path(data)
            self._populate_targets()

    # -- targets ---------------------------------------------------------- #
    def _find_target(self, payload) -> int:
        for i in range(self.target_combo.count()):
            if self.target_combo.itemData(i) == payload:
                return i
        return -1

    def _populate_targets(self) -> None:
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItem("📁  Folder note (NOTES.md)", _FOLDER_NOTE)
        try:
            files = recent_files(self._folder, RECENT_FILES_SHOWN)
        except OSError:
            files = []
        for f in files:
            self.target_combo.addItem(f.name, ("file", f.name))
        self.target_combo.addItem("Choose file…", _CHOOSE_FILE)
        self.target_combo.setCurrentIndex(0)
        self.target_combo.blockSignals(False)

    def _on_target_activated(self, idx: int) -> None:
        if self.target_combo.itemData(idx) != _CHOOSE_FILE:
            return
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Choose file to annotate", str(self._folder)
        )
        if not chosen:
            self.target_combo.setCurrentIndex(0)  # back to folder note
            return
        picked = Path(chosen).resolve()
        self._set_folder(picked.parent)  # keep the note beside its file
        payload = ("file", picked.name)
        fidx = self._find_target(payload)
        if fidx < 0:
            self.target_combo.insertItem(1, picked.name, payload)
            fidx = 1
        self.target_combo.setCurrentIndex(fidx)

    # -- public ----------------------------------------------------------- #
    def current_context(self) -> Tuple[Path, str]:
        """Return ``(base_dir, target)`` for :func:`filenotes.writer.write_note`.

        ``target`` is ``"."`` for the folder note, else a filename inside
        ``base_dir``.
        """
        data = self.target_combo.currentData()
        if data and data[0] == "file":
            return self._folder, data[1]
        return self._folder, "."
