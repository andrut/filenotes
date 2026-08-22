"""Rendering tests for the three ls-notes display modes."""

from datetime import datetime, timedelta
from pathlib import Path

from filenotes import lsnotes
from filenotes.core import compact_age
from filenotes.writer import write_note


def _seed(tmp_path, ages=((0, "newest note"),)):
    """Write one note per (age_in_days, message) pair."""
    now = datetime.now()
    for i, (days, message) in enumerate(ages):
        target = tmp_path / f"run{i}.dat"
        target.touch()
        write_note(
            [target.name],
            message,
            base=tmp_path,
            stamp_commit=False,
            when=now - timedelta(days=days),
        )


# --------------------------------------------------------------------------- #
# compact_age
# --------------------------------------------------------------------------- #
def test_compact_age_units():
    now = 1_000_000_000.0
    assert compact_age(now - 5, now) == "5s"
    assert compact_age(now - 90, now) == "1m"
    assert compact_age(now - 3600, now) == "1h"
    assert compact_age(now - 86400, now) == "1d"
    assert compact_age(now - 7 * 86400, now) == "1w"
    assert compact_age(now - 30 * 86400, now) == "1mo"
    assert compact_age(now - 365 * 86400, now) == "1y"


def test_compact_age_rounds_down():
    now = 1_000_000_000.0
    # 1h32m is still "1h"; only a full 2 hours reads "2h".
    assert compact_age(now - (3600 + 32 * 60), now) == "1h"
    assert compact_age(now - 2 * 3600, now) == "2h"
    # Just shy of the next unit stays in the smaller one.
    assert compact_age(now - (86400 - 1), now) == "23h"
    assert compact_age(now - (7 * 86400 - 1), now) == "6d"


def test_compact_age_clamps_future_and_now():
    now = 1_000_000_000.0
    assert compact_age(now, now) == "0s"
    assert compact_age(now + 500, now) == "0s"  # clock skew must not go negative


# --------------------------------------------------------------------------- #
# display modes
# --------------------------------------------------------------------------- #
def test_super_short_uses_compact_age(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, ages=((3, "three days old"),))

    assert lsnotes.main(["-ss"]) == 0
    out = capsys.readouterr().out.strip()

    assert out == "run0.dat 3d three days old"


def test_super_short_long_form_matches(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, ages=((1, "yesterday"),))

    lsnotes.main(["-ss"])
    via_ss = capsys.readouterr().out
    lsnotes.main(["--super-short"])
    assert capsys.readouterr().out == via_ss


def test_short_keeps_full_timestamp(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, ages=((3, "three days old"),))

    lsnotes.main(["-s"])
    out = capsys.readouterr().out.strip()

    # -s still shows the absolute stamp, not an age.
    assert "three days old" in out
    assert ":" in out and "3d" not in out


def test_long_mode_unaffected(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, ages=((0, "body text"),))

    lsnotes.main([])
    out = capsys.readouterr().out

    # Filename on its own line, body indented beneath it.
    assert "run0.dat\n" in out
    assert "  body text" in out


def test_super_short_one_line_per_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, ages=((5, "older"), (0, "newer")))

    lsnotes.main(["-ss"])
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

    assert len(lines) == 2
    assert all(len(ln.split(" ", 2)) == 3 for ln in lines)


def test_super_short_shows_latest_entry_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "run.dat"
    target.touch()
    now = datetime.now()
    write_note(["run.dat"], "first", base=tmp_path, stamp_commit=False,
               when=now - timedelta(days=9))
    write_note(["run.dat"], "second", base=tmp_path, stamp_commit=False,
               when=now - timedelta(days=2))

    lsnotes.main(["-ss"])
    out = capsys.readouterr().out.strip()

    assert out == "run.dat 2d second"


def test_super_short_collapses_images(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "run.dat"
    target.touch()
    (tmp_path / "p.png").write_bytes(b"IMG")
    write_note(["run.dat"], "with image", images=[tmp_path / "p.png"],
               base=tmp_path, stamp_commit=False)

    lsnotes.main(["-ss"])
    out = capsys.readouterr().out.strip()

    # The image markdown must not spill into the one-liner.
    assert out.endswith("with image [img]")
    assert "notes-assets" not in out


def test_super_short_unparseable_timestamp(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # A hand-edited header that read_entries can't parse into a datetime.
    Path("odd.dat.notes.md").write_text(
        "2026-13-45 99:99:99\n\nmangled header\n", encoding="utf-8"
    )

    lsnotes.main(["-ss"])
    out = capsys.readouterr().out.strip()

    assert out == "odd.dat ? mangled header"
