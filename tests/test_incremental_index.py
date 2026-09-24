"""Tests for incremental HEAD tracking."""

from __future__ import annotations

from pathlib import Path

from codegraph.git.history import GitHistory
from codegraph.git.incremental import commits_after, load_last_head, save_last_head


def test_incremental_state_roundtrip(tmp_path: Path) -> None:
    """save_last_head / load_last_head persist a sha."""
    assert load_last_head(tmp_path) is None
    save_last_head(tmp_path, "abc123")
    assert load_last_head(tmp_path) == "abc123"


def test_commits_after_filters(tmp_path: Path) -> None:
    """commits_after stops at the recorded HEAD."""
    git = __import__("git")
    from git import Actor

    repo = git.Repo.init(str(tmp_path))
    shas = []
    for i in range(3):
        (tmp_path / f"f{i}.py").write_text(f"def f{i}():\n    return {i}\n", encoding="utf-8")
        repo.index.add([f"f{i}.py"])
        commit = repo.index.commit(
            f"feat: add f{i} because demo",
            author=Actor("a", "a@example.com"),
            committer=Actor("a", "a@example.com"),
        )
        shas.append(commit.hexsha)

    history = GitHistory(tmp_path)
    # First call: all commits (oldest first)
    pending = commits_after(tmp_path, history, depth=20)
    assert len(pending) == 3
    save_last_head(tmp_path, shas[-1])
    assert commits_after(tmp_path, history, depth=20) == []
