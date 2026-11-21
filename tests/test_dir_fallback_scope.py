"""A root-level file has no directory topic, so it gets no directory fallback.

`why LICENSE:1` used to return four decisions about a changelog entry with
`binding: dir`, which reads exactly like a real match. The repository root is not a
subject area: its "decisions" are every root-level record, unrelated to whatever
file was asked about.
"""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.models import Decision, DecisionSource, DecisionStatus, DecisionTier
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decisions,
    query_decisions_for_dir,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _decision(uid: str, path: str) -> Decision:
    return Decision(
        uid=uid,
        content=f"Decision recorded in {path}",
        reason="because the tests need a reason",
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT,
        source_ref="commit abc",
        timestamp=NOW,
        file_path=path,
        tier=DecisionTier.DECISION,
    )


def _db(tmp_path):
    conn = connect(db_path_for_root(tmp_path))
    init_schema(conn)
    insert_decisions(
        conn,
        [
            _decision("d-changelog", "CHANGELOG.md"),
            _decision("d-readme", "README.md"),
            _decision("d-nested", "src/app/core.py"),
            _decision("d-sibling", "src/app/util.py"),
        ],
    )
    return conn


def test_root_level_file_has_no_directory_fallback(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        assert query_decisions_for_dir(conn, "LICENSE") == []
    finally:
        conn.close()


def test_another_root_level_file_is_not_a_topic(tmp_path) -> None:
    """A changelog decision must not answer for `LICENSE` just because both are at the root."""
    conn = _db(tmp_path)
    try:
        found = query_decisions_for_dir(conn, "LICENSE")
        assert all(d.file_path != "CHANGELOG.md" for d in found)
    finally:
        conn.close()


def test_nested_directory_still_falls_back(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        found = query_decisions_for_dir(conn, "src/app/main.py")
        paths = {d.file_path for d in found}
        assert "src/app/core.py" in paths or "src/app/util.py" in paths
    finally:
        conn.close()


def test_nested_directory_excludes_unrelated_trees(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        found = query_decisions_for_dir(conn, "src/app/main.py")
        assert all(d.file_path != "CHANGELOG.md" for d in found)
    finally:
        conn.close()
