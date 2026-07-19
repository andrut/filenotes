import subprocess

import pytest


@pytest.fixture(autouse=True)
def _isolate_history(monkeypatch, tmp_path_factory):
    """Point the MRU history at a throwaway file so tests never touch the
    user's real ~/.local/state store. Kept out of any test's cwd."""
    store = tmp_path_factory.mktemp("history") / "recent-dirs.json"
    monkeypatch.setenv("FILENOTES_HISTORY", str(store))


def _git(path, *args):
    subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@pytest.fixture
def git_repo(tmp_path):
    """A temporary git repo with one committed file (clean tree)."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "checkout", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "model.py").write_text("print(1)\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init")
    return tmp_path
