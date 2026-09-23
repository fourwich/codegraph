"""Tests for depth limiting on git history (incremental-style)."""

from __future__ import annotations

from pathlib import Path

from codegraph.git.history import GitHistory


def test_depth_limits_commits(tmp_path: Path) -> None:
    """depth parameter stops walking early."""
    git = __import__("git")
    from git import Actor

    repo = git.Repo.init(str(tmp_path))
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text(f"def f{i}():\n    return {i}\n", encoding="utf-8")
        repo.index.add([f"f{i}.py"])
        repo.index.commit(
            f"feat: add f{i} because demo",
            author=Actor("a", "a@example.com"),
            committer=Actor("a", "a@example.com"),
        )
    history = GitHistory(tmp_path)
    assert len(list(history.iter_commits(depth=2))) == 2
    assert len(list(history.iter_commits(depth=10))) == 5
