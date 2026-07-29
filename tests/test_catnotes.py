from pathlib import Path

from filenotes import catnotes, note as note_cli


def _seed(tmp_path):
    (tmp_path / "b.npy").touch()
    (tmp_path / "a.npy").touch()
    sub = tmp_path / "runs"
    sub.mkdir()
    (sub / "run.csv").touch()
    note_cli.main([".", "-m", "folder log"])
    note_cli.main(["b.npy", "-m", "note b"])
    note_cli.main(["a.npy", "-m", "note a"])
    note_cli.main(["runs/run.csv", "-m", "sub note"])


def test_cat_non_recursive_alphabetical(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    capsys.readouterr()  # drop the "Appended note to …" seed output

    rc = catnotes.main([])
    assert rc == 0
    out = capsys.readouterr().out

    # Folder note first, then files alphabetically; subfolder excluded.
    assert out.index("## (folder)") < out.index("## a.npy") < out.index("## b.npy")
    assert "run.csv" not in out
    assert "folder log" in out and "note a" in out


def test_cat_recursive_includes_subfolders(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    capsys.readouterr()  # drop the "Appended note to …" seed output

    rc = catnotes.main(["-r"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "## runs/run.csv" in out
    # Root entries still precede the subfolder entry.
    assert out.index("## b.npy") < out.index("## runs/run.csv")


def test_cat_recursive_rewrites_image_links(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "runs"
    sub.mkdir()
    (sub / "run.csv").touch()
    (sub / "plot.png").write_bytes(b"IMG")
    note_cli.main(["runs/run.csv", "-m", "sub run", "-i", "runs/plot.png"])
    capsys.readouterr()

    catnotes.main(["-r"])
    out = capsys.readouterr().out
    # The subfolder note's image link now resolves from the root.
    assert "runs/notes-assets/" in out
    # And --raw leaves it relative to the note file.
    catnotes.main(["-r", "--raw"])
    raw = capsys.readouterr().out
    assert "runs/notes-assets/" not in raw
    assert "](notes-assets/" in raw


def test_cat_recursive_leaves_embedded_images_untouched(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "runs"
    sub.mkdir()
    (sub / "run.csv").touch()
    (sub / "plot.png").write_bytes(b"\x89PNG\r\nDATA")
    note_cli.main(["runs/run.csv", "-m", "embedded", "-i", "runs/plot.png", "-E"])
    capsys.readouterr()

    catnotes.main(["-r"])
    out = capsys.readouterr().out
    # A data: URI must survive concatenation verbatim — no path rewriting.
    assert "](data:image/png;base64," in out
    assert "runs/notes-assets/" not in out


def test_cat_no_notes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = catnotes.main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no notes found" in captured.err
