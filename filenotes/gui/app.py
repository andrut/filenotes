"""``notes-gui`` entry point: launch the note window."""

from __future__ import annotations

import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    # Imported lazily so the module import graph for the CLI never pulls in Qt.
    from PySide6.QtWidgets import QApplication

    from .window import NoteWindow

    args = list(sys.argv if argv is None else [sys.argv[0], *argv])
    app = QApplication.instance() or QApplication(args)
    app.setApplicationName("filenotes")
    app.setApplicationDisplayName("filenotes")

    window = NoteWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
