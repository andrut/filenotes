"""Screen and clipboard capture backends for the ``note`` command.

Each capability (fullscreen, region select, clipboard image) has an ordered
list of backends. The first backend whose external tool is installed and whose
session matches is used, so this works across machines with different
screenshot stacks. Supports Linux (X11 and Wayland) and macOS.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union


class CaptureError(Exception):
    """Raised when a capture cannot be produced (no tool, cancelled, empty)."""


def _has(tool: str) -> bool:
    return shutil.which(tool) is not None


def _on_x11() -> bool:
    return bool(os.environ.get("DISPLAY"))


def _on_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _on_linux_desktop() -> bool:
    return _on_x11() or _on_wayland()


def _on_macos() -> bool:
    return sys.platform == "darwin"


# AppleScript that writes the clipboard's PNG image to the file given as argv[1].
# The clipboard coercion is attempted *before* the output file is opened, so a
# clipboard holding no image errors out without leaving an empty file behind.
_OSASCRIPT_CLIPBOARD = [
    "osascript",
    "-e", "on run argv",
    "-e", "set pngData to (the clipboard as «class PNGf»)",
    "-e", "set outFile to (POSIX file (item 1 of argv))",
    "-e", "set fh to open for access outFile with write permission",
    "-e", "set eof fh to 0",
    "-e", "write pngData to fh",
    "-e", "close access fh",
    "-e", "end run",
]


# A backend: (tool, extra_tool_or_None, session_predicate, command-builder).
# The builder returns either an argv list, or a shell-string (run via the shell,
# needed when one tool feeds another, e.g. grim + slurp).
Builder = Callable[[str], Union[List[str], str]]
Backend = Tuple[str, Optional[str], Callable[[], bool], Builder]

_FULLSCREEN: List[Backend] = [
    ("screencapture", None, _on_macos, lambda d: ["screencapture", "-x", d]),
    ("grim", None, _on_wayland, lambda d: ["grim", d]),
    ("maim", None, _on_x11, lambda d: ["maim", d]),
    ("scrot", None, _on_x11, lambda d: ["scrot", "-o", d]),
    ("xfce4-screenshooter", None, _on_x11, lambda d: ["xfce4-screenshooter", "-f", "-s", d]),
    ("gnome-screenshot", None, _on_linux_desktop, lambda d: ["gnome-screenshot", "-f", d]),
    ("spectacle", None, _on_linux_desktop, lambda d: ["spectacle", "-b", "-n", "-o", d]),
    ("import", None, _on_x11, lambda d: ["import", "-window", "root", d]),
]

_REGION: List[Backend] = [
    ("screencapture", None, _on_macos, lambda d: ["screencapture", "-i", d]),
    ("grim", "slurp", _on_wayland, lambda d: f'grim -g "$(slurp)" {d!r}'),
    ("maim", None, _on_x11, lambda d: ["maim", "-s", d]),
    ("scrot", None, _on_x11, lambda d: ["scrot", "-s", "-o", d]),
    ("xfce4-screenshooter", None, _on_x11, lambda d: ["xfce4-screenshooter", "-r", "-s", d]),
    ("gnome-screenshot", None, _on_linux_desktop, lambda d: ["gnome-screenshot", "-a", "-f", d]),
    ("spectacle", None, _on_linux_desktop, lambda d: ["spectacle", "-r", "-b", "-n", "-o", d]),
    ("import", None, _on_x11, lambda d: ["import", d]),
]

# A clipboard backend: (tool, session_predicate, argv-builder, writes_to_stdout).
# stdout backends stream the PNG to stdout (captured into the dest file); the
# rest write the dest file themselves.
ClipboardBackend = Tuple[str, Callable[[], bool], Builder, bool]
_CLIPBOARD: List[ClipboardBackend] = [
    ("pngpaste", _on_macos, lambda d: ["pngpaste", d], False),
    ("osascript", _on_macos, lambda d: [*_OSASCRIPT_CLIPBOARD, d], False),
    ("wl-paste", _on_wayland, lambda d: ["wl-paste", "--type", "image/png"], True),
    ("xclip", _on_x11, lambda d: ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"], True),
]


def _valid_image(dest: str) -> bool:
    p = Path(dest)
    return p.exists() and p.stat().st_size > 0


def _run_screenshot(backends: List[Backend], dest: str, what: str) -> str:
    considered = []
    for tool, extra, session_ok, builder in backends:
        if not session_ok():
            continue
        considered.append(tool)
        if not _has(tool):
            continue
        if extra and not _has(extra):
            continue
        cmd = builder(dest)
        shell = isinstance(cmd, str)
        try:
            proc = subprocess.run(cmd, shell=shell)
        except OSError as exc:
            raise CaptureError(f"{what}: failed to run {tool}: {exc}")
        if proc.returncode != 0:
            raise CaptureError(f"{what} cancelled or failed ({tool} exited {proc.returncode}).")
        if not _valid_image(dest):
            raise CaptureError(f"{what}: {tool} produced no image.")
        return tool
    raise CaptureError(
        f"no {what} tool available (install one of: {', '.join(considered)})."
    )


def capture_fullscreen(dest: str) -> str:
    return _run_screenshot(_FULLSCREEN, dest, "screenshot")


def capture_region(dest: str) -> str:
    return _run_screenshot(_REGION, dest, "region screenshot")


def capture_clipboard(dest: str) -> str:
    ran_any = False
    considered = []
    for tool, session_ok, builder, to_stdout in _CLIPBOARD:
        if not session_ok():
            continue
        considered.append(tool)
        if not _has(tool):
            continue
        ran_any = True
        cmd = builder(dest)
        if to_stdout:
            with open(dest, "wb") as fh:
                proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.DEVNULL)
        else:
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode == 0 and _valid_image(dest):
            return tool
        try:
            Path(dest).unlink()
        except OSError:
            pass
    if ran_any:
        raise CaptureError("no image found in the clipboard.")
    raise CaptureError(
        f"no clipboard tool available (install one of: {', '.join(considered)})."
    )
