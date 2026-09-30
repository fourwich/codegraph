"""Node lifecycle: live-version lookup and single live version per symbol."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from codegraph.commands.index import _close_superseded_live_versions, ingest_commit
from codegraph.git.history import CommitInfo
from codegraph.models import CodeNode
from codegraph.storage import (
    connect,
    db_path_for_root,
    find_node_at_line,
    init_schema,
    insert_nodes,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _node(uid: str, line_start: int, line_end: int, valid_from: datetime,
          valid_to: datetime | None) -> CodeNode:
    return CodeNode(
        uid=uid,
        kind="function",
        name="f",
        file_path="src/x.py",
        line_start=line_start,
        line_end=line_end,
        language="python",
        commit_sha="c1",
        valid_from=valid_from,
        valid_to=valid_to,
    )


class _StubHistory:
    """Minimal GitHistory stand-in: serves fixed file text per commit."""

    def __init__(self, root: Path, text: str | dict[str, str]) -> None:
        self.root = root
        self._default = text if isinstance(text, str) else ""
        self._by_sha = text if isinstance(text, dict) else {}

    def get_file_at_commit(self, commit_sha: str, file_path: str) -> str:
        return self._by_sha.get(commit_sha, self._default)


def test_find_node_at_line_ignores_dead_nodes(tmp_path: Path) -> None:
    """A tombstoned node version must never answer a current query."""
    conn = connect(db_path_for_root(tmp_path))
    try:
        init_schema(conn)
        insert_nodes(
            conn,
            [
                _node(
                    "dead-tight",
                    4,
                    6,
                    NOW - timedelta(days=2),
                    NOW - timedelta(days=1),
                )
            ],
        )
        assert find_node_at_line(conn, "src/x.py", 5, at=NOW) is None

        insert_nodes(conn, [_node("live", 1, 10, NOW - timedelta(hours=1), None)])
        found = find_node_at_line(conn, "src/x.py", 5, at=NOW)
        assert found is not None
        assert found.uid == "live"
    finally:
        conn.close()


def test_no_duplicate_live_versions(tmp_path: Path) -> None:
    """Re-ingesting the same symbol must not fork two live versions."""
    history = _StubHistory(tmp_path, "def f():\n    return 1\n")
    commit = CommitInfo(
        sha="a" * 40,
        author="a",
        timestamp=NOW,
        message="feat: f",
        changed_files=["src/x.py"],
    )
    live: dict = {}
    all_nodes: list[CodeNode] = []
    all_edges: list = []

    ingest_commit(history, commit, live, all_nodes, all_edges)
    ingest_commit(history, commit, live, all_nodes, all_edges)

    versions = live[("src/x.py", "f")]
    assert len([n for n in versions if n.valid_to is None]) == 1
    assert len(all_nodes) == 1

    # A genuine range change closes the old version and opens exactly one new one.
    moved = _StubHistory(tmp_path, "def f():\n    x = 1\n    return x\n")
    later = CommitInfo(
        sha="b" * 40,
        author="a",
        timestamp=NOW + timedelta(hours=1),
        message="refactor: f",
        changed_files=["src/x.py"],
    )
    ingest_commit(moved, later, live, all_nodes, all_edges)

    versions = live[("src/x.py", "f")]
    assert len([n for n in versions if n.valid_to is None]) == 1
    assert len(versions) == 2
    assert versions[0].valid_to == later.timestamp


def test_reingesting_an_older_commit_does_not_fork_versions(tmp_path: Path) -> None:
    """Re-reading history after an amend/rebase must not invert the timeline."""
    older_sha, newer_sha = "a" * 40, "b" * 40
    history = _StubHistory(
        tmp_path,
        {older_sha: "def f():\n    return 1\n", newer_sha: "def f():\n    return 2\n"},
    )
    newer = CommitInfo(
        sha=newer_sha,
        author="a",
        timestamp=NOW + timedelta(hours=1),
        message="feat: f",
        changed_files=["src/x.py"],
    )
    live: dict = {}
    all_nodes: list[CodeNode] = []
    all_edges: list = []
    ingest_commit(history, newer, live, all_nodes, all_edges)
    assert len(all_nodes) == 1

    older = CommitInfo(
        sha=older_sha,
        author="a",
        timestamp=NOW,
        message="feat: f",
        changed_files=["src/x.py"],
    )
    ingest_commit(history, older, live, all_nodes, all_edges)

    versions = live[("src/x.py", "f")]
    assert len(all_nodes) == 1, "re-reading an older commit forked a version"
    assert len(versions) == 1
    assert versions[0].valid_to is None
    assert versions[0].commit_sha == newer_sha


def test_legacy_duplicate_live_versions_are_repaired() -> None:
    """A pre-existing DB with two live versions is normalised to one."""
    older = _node("v-old", 24, 28, NOW - timedelta(hours=1), None)
    newer = _node("v-new", 24, 28, NOW, None)
    dead = _node("v-dead", 1, 3, NOW - timedelta(days=2), NOW - timedelta(days=1))

    repaired = _close_superseded_live_versions([older, newer, dead])

    assert repaired == 1
    assert older.valid_to == NOW
    assert newer.valid_to is None
    assert dead.valid_to == NOW - timedelta(days=1)
