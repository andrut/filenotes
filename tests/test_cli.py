from pathlib import Path

from filenotes import cli
from filenotes.core import read_entries


def test_dispatch_add(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("exp.npy").touch()
    rc = cli.main(["add", "exp.npy", "-m", "via notes add"])
    assert rc == 0
    assert read_entries(Path("exp.npy.notes.md"))[0].text == "via notes add"


def test_dispatch_cat(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    Path("exp.npy").touch()
    cli.main(["add", "exp.npy", "-m", "hi"])
    capsys.readouterr()
    rc = cli.main(["cat"])
    assert rc == 0
    assert "## exp.npy" in capsys.readouterr().out


def test_unknown_command(capsys):
    rc = cli.main(["bogus"])
    assert rc == 2
    assert "unknown command" in capsys.readouterr().err


def test_no_args_shows_help(capsys):
    rc = cli.main([])
    assert rc == 1
    assert "usage: notes" in capsys.readouterr().err


def test_help_flag(capsys):
    rc = cli.main(["--help"])
    assert rc == 0
    assert "commands:" in capsys.readouterr().out
