"""Git-history and working-tree parsing must produce the same edge semantics.

The git path used to resolve calls per file while the working-tree path resolved
them across the whole batch, so the same repository produced a different graph
depending on whether it happened to be a Git checkout.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from _parser_helpers import uses_pairs

from codegraph.commands.index import ingest_commit
from codegraph.git.history import CommitInfo
from codegraph.parser.parallel import parse_files_parallel

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)

CALLER = "def caller():\n    return target()\n"
CALLEE = "def target():\n    return 1\n"


def test_working_tree_resolves_calls_across_files() -> None:
    nodes, edges = parse_files_parallel(
        [("caller.py", CALLER), ("callee.py", CALLEE)],
        commit_sha="WORKTREE",
        valid_from=NOW,
        jobs=1,
    )
    assert len(nodes) == 2
    assert uses_pairs(edges) == {("caller", "target")}


class _StubHistory:
    """Serves a fixed file text per path."""

    def __init__(self, root: Path, files: dict[str, str]) -> None:
        self.root = root
        self._files = files

    def get_file_at_commit(self, commit_sha: str, file_path: str) -> str:
        return self._files.get(file_path, "")


def test_git_history_resolves_calls_across_files_the_same_way(tmp_path: Path) -> None:
    """A call into a file that was ingested in an earlier commit still resolves."""
    history = _StubHistory(tmp_path, {"callee.py": CALLEE, "caller.py": CALLER})
    live: dict = {}
    all_nodes: list = []
    all_edges: list = []

    first = CommitInfo(
        sha="a" * 40, author="a", timestamp=NOW, message="feat: target",
        changed_files=["callee.py"],
    )
    second = CommitInfo(
        sha="b" * 40, author="a", timestamp=NOW, message="feat: caller",
        changed_files=["caller.py"],
    )

    ingest_commit(history, first, live, all_nodes, all_edges)
    ingest_commit(history, second, live, all_nodes, all_edges)

    assert uses_pairs(all_edges) == {("caller", "target")}


def test_git_and_working_tree_agree_on_the_same_files(tmp_path: Path) -> None:
    """Both paths produce the same symbol-level call pairs."""
    history = _StubHistory(tmp_path, {"callee.py": CALLEE, "caller.py": CALLER})
    commit = CommitInfo(
        sha="c" * 40, author="a", timestamp=NOW, message="feat: both",
        changed_files=["caller.py", "callee.py"],
    )
    live: dict = {}
    git_nodes: list = []
    git_edges: list = []
    ingest_commit(history, commit, live, git_nodes, git_edges)

    _, tree_edges = parse_files_parallel(
        [("caller.py", CALLER), ("callee.py", CALLEE)],
        commit_sha="WORKTREE",
        valid_from=NOW,
        jobs=1,
    )

    assert uses_pairs(git_edges) == uses_pairs(tree_edges) == {("caller", "target")}
    assert {n.name for n in git_nodes} == {"caller", "target"}
