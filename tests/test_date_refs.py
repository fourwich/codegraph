"""Date refs and time-travel queries must use the user's calendar, not UTC.

`git log --date=short` prints the commit's local date. A user reads that date and
passes it to `codegraph diff` / `graph --at`, so the tool has to interpret it in
the same zone. Comparing against the UTC date silently failed for part of every
day east of Greenwich: at 07:00 in UTC+8 a commit dated 2026-10-29 is still
2026-10-28 in UTC.

Commits are created through the real `git` binary because GitPython drops the
offset when it writes a commit date.
"""

from __future__ import annotations

import os
import subprocess
from datetime import date, datetime, timedelta, timezone

import pytest

from codegraph.commands.graph import filter_decisions_at, local_day_end
from codegraph.git.refs import RefError, resolve_ref
from codegraph.models import Decision, DecisionSource, DecisionStatus


def _tz(offset_hours: int) -> timezone:
    return timezone(timedelta(hours=offset_hours))


def _git(cwd, *args: str, env: dict[str, str] | None = None) -> str:
    base = {
        **os.environ,
        "GIT_AUTHOR_NAME": "a",
        "GIT_AUTHOR_EMAIL": "a@e.com",
        "GIT_COMMITTER_NAME": "a",
        "GIT_COMMITTER_EMAIL": "a@e.com",
    }
    if env:
        base.update(env)
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), env=base, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit_at(cwd, message: str, stamp: str) -> str:
    """Create a commit with an explicit committer date (git format)."""
    _git(cwd, "add", "-A")
    _git(
        cwd,
        "commit",
        "-q",
        "-m",
        message,
        env={"GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp},
    )
    return _git(cwd, "rev-parse", "HEAD")


def _repo_with_commit(tmp_path, stamp: str) -> str:
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    return _commit_at(tmp_path, "init", stamp)


def test_date_ref_matches_the_local_calendar_day(tmp_path) -> None:
    """A commit at 00:30 in UTC+8 is 2026-01-01 in UTC but 2026-01-02 locally."""
    sha = _repo_with_commit(tmp_path, "2026-01-02 00:30:00 +0800")

    assert resolve_ref(tmp_path, "2026-01-02", tz=_tz(8))[0] == sha
    with pytest.raises(RefError):
        resolve_ref(tmp_path, "2026-01-02", tz=timezone.utc)
    assert resolve_ref(tmp_path, "2026-01-01", tz=timezone.utc)[0] == sha


def test_date_ref_defaults_to_the_machine_zone(tmp_path) -> None:
    """Without an explicit zone the local calendar date resolves."""
    sha = _repo_with_commit(tmp_path, "2026-01-02 00:30:00 +0800")
    epoch = int(_git(tmp_path, "log", "-1", "--format=%ct"))
    local_day = datetime.fromtimestamp(epoch).date().isoformat()

    assert resolve_ref(tmp_path, local_day)[0] == sha


def test_date_ref_picks_the_last_commit_of_that_day(tmp_path) -> None:
    """Two commits on one local day resolve to the later one."""
    _repo_with_commit(tmp_path, "2026-01-02 09:00:00 +0800")
    (tmp_path / "a.py").write_text("x = 2\n", encoding="utf-8")
    latest = _commit_at(tmp_path, "later", "2026-01-02 18:00:00 +0800")

    assert resolve_ref(tmp_path, "2026-01-02", tz=_tz(8))[0] == latest


def test_graph_day_boundary_is_the_end_of_the_local_day() -> None:
    """`--at 2026-01-02` covers up to local midnight, not UTC's."""
    start = local_day_end(date(2026, 1, 2))

    assert start.tzinfo is not None
    assert start.year == 2026 and start.month == 1 and start.day == 2


def test_decisions_are_filtered_by_local_date() -> None:
    """A decision at 00:30 local on Jan 3 is not part of Jan 2."""
    decision = Decision(
        uid="d1",
        content="x",
        reason="because",
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT,
        source_ref="commit abc",
        timestamp=datetime(2026, 1, 2, 16, 30, tzinfo=timezone.utc),  # 00:30 +08
    )

    assert filter_decisions_at([decision], date(2026, 1, 3)) == [decision]
