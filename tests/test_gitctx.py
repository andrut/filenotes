import subprocess

from filenotes.gitctx import GitContext, git_context


def test_stamp_formatting():
    assert GitContext("a1b2c3d", "main", False).stamp() == "— `main` @ `a1b2c3d`"
    assert GitContext("a1b2c3d", "main", True).stamp() == "— `main` @ `a1b2c3d` (dirty)"
    assert GitContext("a1b2c3d", "HEAD", False).stamp() == "— `detached` @ `a1b2c3d`"


def test_context_clean(git_repo):
    ctx = git_context(git_repo)
    assert ctx is not None
    assert ctx.branch == "main"
    assert ctx.dirty is False
    assert len(ctx.sha) >= 4


def test_dirty_only_from_tracked_changes(git_repo):
    # An untracked file (like our note files) must NOT mark the tree dirty.
    (git_repo / "scratch.notes.md").write_text("x")
    assert git_context(git_repo).dirty is False

    # A tracked-file modification does.
    (git_repo / "model.py").write_text("print(2)\n")
    assert git_context(git_repo).dirty is True


def test_detached_head(git_repo):
    sha = subprocess.run(
        ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(git_repo), "checkout", "-q", sha],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    assert git_context(git_repo).branch == "HEAD"


def test_non_repo_returns_none(tmp_path):
    assert git_context(tmp_path) is None
