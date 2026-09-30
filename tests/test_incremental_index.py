"""Tests for incremental HEAD tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from codegraph.git.history import GitHistory
from codegraph.git.incremental import commits_after, load_last_head, save_last_head
from codegraph.storage import connect, db_path_for_root


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


# --- E10 regression: a second index must not destroy the stored graph ---------


def _make_repo(root: Path) -> Path:
    """Create a small Git repo with two commits touching src/app.py."""
    import git
    from git import Actor

    repo = git.Repo.init(str(root))
    (root / "src").mkdir()
    app = root / "src" / "app.py"
    app.write_text(
        "def helper():\n    return 1\n\ndef a():\n    return helper()\n",
        encoding="utf-8",
    )
    repo.index.add(["src/app.py"])
    repo.index.commit(
        "feat: add a because demo",
        author=Actor("a", "a@example.com"),
        committer=Actor("a", "a@example.com"),
    )
    app.write_text(
        "def helper():\n    return 1\n\ndef a():\n    return helper() + 1\n",
        encoding="utf-8",
    )
    repo.index.add(["src/app.py"])
    repo.index.commit(
        "feat: add b since needed",
        author=Actor("a", "a@example.com"),
        committer=Actor("a", "a@example.com"),
    )
    return root


def _run_index(root: Path) -> None:
    from typer.testing import CliRunner

    from codegraph.cli import app

    result = CliRunner().invoke(app, ["index", str(root), "--depth", "20"])
    assert result.exit_code == 0, result.output


def _graph_state(root: Path) -> dict:
    """Snapshot the persisted graph rows (order-independent)."""
    conn = connect(db_path_for_root(root))
    try:
        nodes = conn.execute(
            "SELECT uid, line_start, line_end, valid_from, valid_to, commit_sha "
            "FROM nodes ORDER BY uid"
        ).fetchall()
        edges = conn.execute(
            "SELECT from_uid, to_uid, kind, file_path, line FROM edges "
            "ORDER BY from_uid, to_uid, kind"
        ).fetchall()
        decisions = conn.execute("SELECT uid, content FROM decisions ORDER BY uid").fetchall()
        links = conn.execute(
            "SELECT decision_uid, node_uid, file_path, line FROM decision_code_links "
            "ORDER BY decision_uid, file_path, line"
        ).fetchall()
        return {
            "nodes": [tuple(r) for r in nodes],
            "edges": [tuple(r) for r in edges],
            "decisions": [tuple(r) for r in decisions],
            "links": [tuple(r) for r in links],
            "shas": {r[0] for r in nodes},
        }
    finally:
        conn.close()


def test_second_index_preserves_nodes(tmp_path: Path) -> None:
    """Running index twice keeps the same Git-derived graph."""
    root = _make_repo(tmp_path)
    _run_index(root)
    first = _graph_state(root)

    assert first["nodes"], "first index produced no nodes"
    assert first["edges"], "first index produced no edges"
    assert "WORKTREE" not in first["shas"], "history was replaced by a worktree snapshot"

    _run_index(root)
    second = _graph_state(root)

    assert second == first


def test_graph_at_after_reindex_is_stable(tmp_path: Path) -> None:
    """`graph --at` must return the same snapshot after a second index."""
    from codegraph.commands.graph import load_snapshot_sqlite

    root = _make_repo(tmp_path)
    _run_index(root)
    at = datetime.now(timezone.utc).date()
    before = load_snapshot_sqlite(root, at, "src")[:3]

    _run_index(root)
    after = load_snapshot_sqlite(root, at, "src")[:3]

    assert before == after
    assert before[0] > 0
    assert len(_graph_state(root)["shas"]) >= 1


def test_truncated_graph_is_rebuilt(tmp_path: Path) -> None:
    """A graph truncated behind our back is detected and rebuilt."""
    root = _make_repo(tmp_path)
    _run_index(root)
    expected = len(_graph_state(root)["nodes"])
    assert expected > 1

    conn = connect(db_path_for_root(root))
    try:
        conn.execute(
            "DELETE FROM nodes WHERE uid IN (SELECT uid FROM nodes LIMIT ?)",
            (expected - 1,),
        )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 1
    finally:
        conn.close()

    _run_index(root)
    assert len(_graph_state(root)["nodes"]) == expected

