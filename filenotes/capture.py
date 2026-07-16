"""Linux screen and clipboard capture backends for the ``note`` command.

Each capability (fullscreen, region select, clipboard image) has an ordered
list of backends. The first backend whose external tool is installed and whose
display session matches is used, so this works across machines with different
screenshot stacks. Currently Linux-only (X11 and Wayland).
"""

from __future__ import annotations

import os
import shutil
import subprocess
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


# A backend: (tool, extra_tool_or_None, session_predicate, command-builder).
# The builder returns either an argv list, or a shell-string (run via the shell,
# needed when one tool feeds another, e.g. grim + slurp).
Builder = Callable[[str], Union[List[str], str]]
Backend = Tuple[str, Optional[str], Callable[[], bool], Builder]

_FULLSCREEN: List[Backend] = [
    ("grim", None, _on_wayland, lambda d: ["grim", d]),
    ("maim", None, _on_x11, lambda d: ["maim", d]),
    ("scrot", None, _on_x11, lambda d: ["scrot", "-o", d]),
    ("xfce4-screenshooter", None, _on_x11, lambda d: ["xfce4-screenshooter", "-f", "-s", d]),
    ("gnome-screenshot", None, lambda: True, lambda d: ["gnome-screenshot", "-f", d]),
    ("spectacle", None, lambda: True, lambda d: ["spectacle", "-b", "-n", "-o", d]),
    ("import", None, _on_x11, lambda d: ["import", "-window", "root", d]),
]

_REGION: List[Backend] = [
    ("grim", "slurp", _on_wayland, lambda d: f'grim -g "$(slurp)" {d!r}'),
    ("maim", None, _on_x11, lambda d: ["maim", "-s", d]),
    ("scrot", None, _on_x11, lambda d: ["scrot", "-s", "-o", d]),
    ("xfce4-screenshooter", None, _on_x11, lambda d: ["xfce4-screenshooter", "-r", "-s", d]),
    ("gnome-screenshot", None, lambda: True, lambda d: ["gnome-screenshot", "-a", "-f", d]),
    ("spectacle", None, lambda: True, lambda d: ["spectacle", "-r", "-b", "-n", "-o", d]),
    ("import", None, _on_x11, lambda d: ["import", d]),
]

# Clipboard backends write the image to stdout; captured to the dest file.
_CLIPBOARD: List[Tuple[str, Callable[[], bool], List[str]]] = [
    ("wl-paste", _on_wayland, ["wl-paste", "--type", "image/png"]),
    ("xclip", _on_x11, ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"]),
]


def _valid_image(dest: str) -> bool:
    p = Path(dest)
    return p.exists() and p.stat().st_size > 0


def _run_screenshot(backends: List[Backend], dest: str, what: str) -> str:
    considered = []
    for tool, extra, session_ok, builder in backends:
        considered.append(tool)
        if not _has(tool) or not session_ok():
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
    for tool, session_ok, cmd in _CLIPBOARD:
        if not _has(tool) or not session_ok():
            continue
        ran_any = True
        with open(dest, "wb") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.DEVNULL)
        if proc.returncode == 0 and _valid_image(dest):
            return tool
        try:
            Path(dest).unlink()
        except OSError:
            pass
    if ran_any:
        raise CaptureError("no image found in the clipboard.")
    raise CaptureError("no clipboard tool available (install xclip or wl-paste).")
