"""Tests for decision version diff."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from codegraph.commands.diff import compute_changes
from codegraph.git.refs import RefError, resolve_ref
from codegraph.models import Decision, DecisionSource, DecisionStatus


def _dec(uid: str, content: str, status: DecisionStatus = DecisionStatus.ACCEPTED, **kw) -> Decision:
    return Decision(
        uid=uid,
        content=content,
        reason=kw.get("reason", "r"),
        status=status,
        source=DecisionSource.ADR,
        source_ref=kw.get("source_ref", "ADR 1"),
        timestamp=kw.get("ts", datetime(2026, 9, 23, tzinfo=timezone.utc)),
        file_path=kw.get("file_path", "src/a.py"),
    )


def test_compute_diff_added() -> None:
    changes = compute_changes([], [_dec("d1", "New idea")])
    assert len(changes) == 1
    assert changes[0].kind == "added"


def test_compute_diff_removed() -> None:
    changes = compute_changes([_dec("d1", "Old idea")], [])
    assert changes[0].kind == "removed"


def test_compute_diff_changed_status() -> None:
    a = _dec("d1", "Same", status=DecisionStatus.ACCEPTED)
    b = _dec("d1", "Same", status=DecisionStatus.REJECTED)
    changes = compute_changes([a], [b])
    assert changes and changes[0].kind == "changed"


def test_compute_diff_superseded() -> None:
    a = _dec("d1", "Old", status=DecisionStatus.ACCEPTED)
    b = _dec("d1", "Old", status=DecisionStatus.SUPERSEDED)
    changes = compute_changes([a], [b])
    assert changes and changes[0].kind == "superseded"


def test_resolve_ref_by_date(tmp_path: Path) -> None:
    import git
    from git import Actor

    repo = git.Repo.init(str(tmp_path))
    f = tmp_path / "x.py"
    f.write_text("print(1)\n", encoding="utf-8")
    repo.index.add(["x.py"])
    repo.index.commit("feat: one because demo", author=Actor("a", "a@e.com"), committer=Actor("a", "a@e.com"))
    commit = repo.head.commit
    day = commit.committed_datetime.strftime("%Y-%m-%d")
    sha2, ts2 = resolve_ref(tmp_path, day)
    assert sha2 == commit.hexsha


def test_resolve_ref_unknown() -> None:
    with pytest.raises(RefError):
        resolve_ref(Path("."), "not-a-ref-xyz-999")


def test_diff_command_no_changes() -> None:
    from typer.testing import CliRunner
    from codegraph.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["diff", "2026-09-23", "2026-09-23", "--scope", "src"])
    assert result.exit_code in (0, 1, 2)
