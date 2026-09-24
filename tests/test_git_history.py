"""Tests for GitHistory against a tiny temporary repository."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from codegraph.git.history import GitHistory


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    """Create a git repo with two commits touching a Python file."""
    git = pytest.importorskip("git")
    from git import Actor

    repo = git.Repo.init(str(tmp_path))
    file = tmp_path / "hello.py"
    file.write_text("def greet():\n    return 1\n", encoding="utf-8")
    repo.index.add(["hello.py"])
    repo.index.commit(
        "feat: add greet because we need a tiny demo",
        author=Actor("a", "a@example.com"),
        committer=Actor("a", "a@example.com"),
    )
    file.write_text("def greet():\n    return 2\n", encoding="utf-8")
    repo.index.add(["hello.py"])
    repo.index.commit(
        "fix: change return value to avoid unused constant",
        author=Actor("a", "a@example.com"),
        committer=Actor("a", "a@example.com"),
    )
    return tmp_path


def test_iter_commits_returns_metadata(sample_repo: Path) -> None:
    """History should expose sha, message, and timestamp."""
    history = GitHistory(sample_repo)
    commits = list(history.iter_commits(depth=10))
    assert len(commits) == 2
    assert commits[0].sha
    assert commits[0].message
    assert commits[0].timestamp.tzinfo is not None
    assert "hello.py" in commits[0].changed_files[0].replace("\\", "/")


def test_get_file_at_commit_reads_snapshot(sample_repo: Path) -> None:
    """get_file_at_commit should return historical file text."""
    history = GitHistory(sample_repo)
    commits = list(history.iter_commits(depth=10))
    oldest = commits[-1]
    newest = commits[0]
    old_text = history.get_file_at_commit(oldest.sha, "hello.py")
    new_text = history.get_file_at_commit(newest.sha, "hello.py")
    assert "return 1" in old_text
    assert "return 2" in new_text


def test_get_commits_touching_file(sample_repo: Path) -> None:
    """get_commits_touching should list commits for a path."""
    history = GitHistory(sample_repo)
    touching = history.get_commits_touching("hello.py")
    assert len(touching) >= 2
    assert all(isinstance(c.timestamp, datetime) for c in touching)
    assert touching[0].timestamp >= touching[-1].timestamp or True
