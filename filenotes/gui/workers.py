"""Background workers so screen capture never blocks the UI thread.

Interactive captures (region select, full-screen) block until the user finishes
picking, so they must run off the GUI thread or the window freezes.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal

from ..capture import CaptureError


class CaptureWorker(QThread):
    """Run one capture function in a thread; report the result via signals."""

    done = Signal(str, str)   # (dest path, tool name)
    failed = Signal(str)      # human-readable error message

    def __init__(self, fn: Callable[[str], str], dest: str, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn
        self._dest = dest

    def run(self) -> None:  # noqa: D401 - QThread entry point
        try:
            tool = self._fn(self._dest)
        except CaptureError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # any backend surprise shouldn't kill the app
            self.failed.emit(str(exc))
        else:
            self.done.emit(self._dest, tool)
