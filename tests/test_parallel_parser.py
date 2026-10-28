"""Tests for parallel working-tree parsing."""

from __future__ import annotations

from concurrent.futures import Future
from datetime import datetime, timezone

from codegraph.parser import parallel
from codegraph.parser.parallel import parse_files_parallel

NOW = datetime.now(timezone.utc)


def _items(count: int) -> list[tuple[str, str]]:
    return [(f"m{i}.py", f"def f{i}():\n    return {i}\n") for i in range(count)]


def test_parse_files_parallel_single_worker() -> None:
    """Single-worker path still returns nodes and edges."""
    items = [
        ("a.py", "def f():\n    return 1\n"),
        ("b.py", "def g():\n    return f()\n"),
    ]
    nodes, edges = parse_files_parallel(
        items,
        commit_sha="abc",
        valid_from=NOW,
        jobs=1,
    )
    names = {n.name for n in nodes}
    assert "f" in names
    assert "g" in names
    assert any(e.kind in {"uses", "contains", "defined_by"} for e in edges)


def test_parse_files_parallel_uses_the_process_pool(monkeypatch) -> None:
    """jobs>1 with 4+ files must take the ProcessPoolExecutor branch.

    The branch was never covered: every existing test passed `jobs=1`, so the
    pool could have been broken without anyone noticing. A fake executor keeps
    the test deterministic while still asserting the branch is taken and its
    results are aggregated.
    """
    used: list[int] = []

    class InlinePool:
        def __init__(self, max_workers: int) -> None:
            used.append(max_workers)
            self._max = max_workers

        def __enter__(self) -> InlinePool:
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

        def submit(self, fn, payload):  # noqa: ANN001, ANN201
            future: Future = Future()
            future.set_result(fn(payload))
            return future

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", InlinePool)
    nodes, _edges = parse_files_parallel(
        _items(4), commit_sha="abc", valid_from=NOW, jobs=2
    )

    assert used == [2]
    assert {n.name for n in nodes} == {f"f{i}" for i in range(4)}


def test_parse_files_parallel_aggregates_calls_across_workers() -> None:
    """A call in one file resolves a definition parsed in another file.

    This runs through the real code path (single worker when the pool is not
    worth starting), and asserts the cross-file `uses` edge that the git path
    also produces.
    """
    items = [
        ("caller.py", "def caller():\n    return target()\n"),
        ("callee.py", "def target():\n    return 1\n"),
    ]
    nodes, edges = parse_files_parallel(
        items, commit_sha="WORKTREE", valid_from=NOW, jobs=1
    )
    pairs = {
        (e.from_uid.split("::")[2].split("@")[0], e.to_uid.split("::")[2].split("@")[0])
        for e in edges
        if e.kind == "uses"
    }
    assert pairs == {("caller", "target")}


def test_parse_files_parallel_skips_unsupported_sources() -> None:
    """Files outside the supported extensions contribute nothing, not a crash."""
    items = [
        ("notes.txt", "def f(): pass\n"),
        ("real.py", "def real():\n    return 1\n"),
    ]
    nodes, _edges = parse_files_parallel(items, commit_sha="abc", valid_from=NOW, jobs=1)
    assert [n.name for n in nodes] == ["real"]
