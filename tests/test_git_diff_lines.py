"""Tests for get_changed_lines on real temporary git repos."""

from __future__ import annotations

from pathlib import Path

from codegraph.git.diff import get_changed_lines


def _repo(tmp_path: Path):
    import git
    from git import Actor
    return git.Repo.init(str(tmp_path)), Actor("a", "a@e.com")


def test_get_changed_lines_simple_commit(tmp_path: Path) -> None:
    repo, actor = _repo(tmp_path)
    f = tmp_path / "app.py"
    f.write_text("a = 1\n", encoding="utf-8")
    repo.index.add(["app.py"])
    repo.index.commit("init", author=actor, committer=actor)
    f.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    repo.index.add(["app.py"])
    c = repo.index.commit("add lines", author=actor, committer=actor)
    changed = get_changed_lines(tmp_path, c.hexsha)
    assert "app.py" in changed
    assert 2 in changed["app.py"]
    assert 3 in changed["app.py"]


def test_get_changed_lines_skip_deletion(tmp_path: Path) -> None:
    repo, actor = _repo(tmp_path)
    f = tmp_path / "gone.py"
    f.write_text("x = 1\n", encoding="utf-8")
    repo.index.add(["gone.py"])
    repo.index.commit("init", author=actor, committer=actor)
    f.unlink()
    repo.index.remove(["gone.py"])
    c = repo.index.commit("delete file", author=actor, committer=actor)
    changed = get_changed_lines(tmp_path, c.hexsha)
    assert "gone.py" not in changed
