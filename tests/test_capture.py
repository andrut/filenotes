"""Backend-selection tests for capture.py.

These don't invoke real screenshot/clipboard tools; they drive the backend
selection logic by faking tool availability, the session, and subprocess.run,
so the same suite passes on Linux, macOS, and CI with no capture stack.
"""

import subprocess
from pathlib import Path

import pytest

from filenotes import capture


class FakeProc:
    def __init__(self, returncode=0):
        self.returncode = returncode


def _fake_env(monkeypatch, *, platform="darwin", have=(), display=None, wayland=None):
    """Pretend a given OS/session with only *have* tools installed."""
    monkeypatch.setattr(capture.sys, "platform", platform)
    monkeypatch.setattr(capture, "_has", lambda t: t in have)
    monkeypatch.setenv("DISPLAY", display) if display else monkeypatch.delenv(
        "DISPLAY", raising=False
    )
    monkeypatch.setenv("WAYLAND_DISPLAY", wayland) if wayland else monkeypatch.delenv(
        "WAYLAND_DISPLAY", raising=False
    )


def _capture_calls(monkeypatch, *, returncode=0, writes_image=True):
    """Record subprocess.run calls; optionally fake a produced image."""
    calls = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        if writes_image:
            # Figure out the destination and drop a non-empty file there.
            dest = kw["stdout"] if "stdout" in kw and hasattr(kw["stdout"], "write") else None
            if dest is not None:
                dest.write(b"\x89PNG\r\n")
            else:
                Path(cmd[-1]).write_bytes(b"\x89PNG\r\n")
        return FakeProc(returncode)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_macos_fullscreen_uses_screencapture(tmp_path, monkeypatch):
    _fake_env(monkeypatch, platform="darwin", have={"screencapture"})
    calls = _capture_calls(monkeypatch)
    dest = str(tmp_path / "shot.png")
    assert capture.capture_fullscreen(dest) == "screencapture"
    assert calls[0] == ["screencapture", "-x", dest]


def test_macos_region_uses_screencapture_interactive(tmp_path, monkeypatch):
    _fake_env(monkeypatch, platform="darwin", have={"screencapture"})
    calls = _capture_calls(monkeypatch)
    dest = str(tmp_path / "region.png")
    assert capture.capture_region(dest) == "screencapture"
    assert calls[0] == ["screencapture", "-i", dest]


def test_macos_clipboard_prefers_pngpaste(tmp_path, monkeypatch):
    _fake_env(monkeypatch, platform="darwin", have={"pngpaste", "osascript"})
    calls = _capture_calls(monkeypatch)
    dest = str(tmp_path / "clip.png")
    assert capture.capture_clipboard(dest) == "pngpaste"
    assert calls[0] == ["pngpaste", dest]


def test_macos_clipboard_falls_back_to_osascript(tmp_path, monkeypatch):
    _fake_env(monkeypatch, platform="darwin", have={"osascript"})  # no pngpaste
    calls = _capture_calls(monkeypatch)
    dest = str(tmp_path / "clip.png")
    assert capture.capture_clipboard(dest) == "osascript"
    assert calls[0][0] == "osascript"
    assert calls[0][-1] == dest


def test_macos_clipboard_empty_reports_no_image(tmp_path, monkeypatch):
    _fake_env(monkeypatch, platform="darwin", have={"osascript"})
    # Tool runs but produces nothing (empty clipboard) -> non-zero, no file.
    _capture_calls(monkeypatch, returncode=1, writes_image=False)
    with pytest.raises(capture.CaptureError, match="no image found in the clipboard"):
        capture.capture_clipboard(str(tmp_path / "clip.png"))


def test_linux_tools_not_offered_on_macos(tmp_path, monkeypatch):
    # On macOS with nothing installed, the error names macOS tools, not Linux ones.
    _fake_env(monkeypatch, platform="darwin", have=set())
    with pytest.raises(capture.CaptureError) as exc:
        capture.capture_fullscreen(str(tmp_path / "shot.png"))
    assert "screencapture" in str(exc.value)
    assert "grim" not in str(exc.value)
    assert "maim" not in str(exc.value)


def test_wayland_still_selects_grim(tmp_path, monkeypatch):
    # Regression: the Linux backends still work when the session matches.
    _fake_env(monkeypatch, platform="linux", have={"grim"}, wayland="wayland-0")
    calls = _capture_calls(monkeypatch)
    dest = str(tmp_path / "shot.png")
    assert capture.capture_fullscreen(dest) == "grim"
    assert calls[0] == ["grim", dest]
