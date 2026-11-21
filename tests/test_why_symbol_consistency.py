"""A symbol query must return the same answer a path query does.

Both forms exist so the caller can use whichever identifier they have. If they disagree
about the same line, the symbol form is worse than useless: it reports a plausible
`binding: none` for a line that has a record, and nothing in the output says the lookup
read the wrong database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.commands.why import parse_location
from codegraph.models import CodeNode, Decision, DecisionSource, DecisionStatus, DecisionTier
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decisions,
    insert_nodes,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _repo(tmp_path):
    conn = connect(db_path_for_root(tmp_path))
    init_schema(conn)
    insert_nodes(
        conn,
        [
            CodeNode(
                uid="n1",
                kind="function",
                name="make_response",
                file_path="src/app.py",
                line_start=100,
                line_end=140,
                language="python",
                valid_from=NOW,
            )
        ],
    )
    insert_decisions(
        conn,
        [
            Decision(
                uid="d1",
                content="Raise TypeError for bad response types",
                reason="silently coercing would hide a caller bug",
                status=DecisionStatus.ACCEPTED,
                source=DecisionSource.ADR,
                source_ref="ADR 002",
                timestamp=NOW,
                file_path="src/app.py",
                line=100,
                tier=DecisionTier.DECISION,
            )
        ],
    )
    conn.close()


def test_symbol_resolves_to_the_definition_start(tmp_path, monkeypatch) -> None:
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert parse_location("make_response") == ("src/app.py", 100)


def test_path_form_is_unchanged(tmp_path, monkeypatch) -> None:
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert parse_location("src/app.py:100") == ("src/app.py", 100)


def test_symbol_and_path_agree(tmp_path, monkeypatch) -> None:
    """Both forms must produce the same (path, line) for the same definition."""
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    by_symbol = parse_location("make_response")
    by_path = parse_location("src/app.py:100")
    assert by_symbol == by_path


def test_symbol_query_records_its_database(tmp_path, monkeypatch) -> None:
    """The decision lookup reads `_QUERY_DB`; a symbol query must set it.

    Without this the later lookup falls through to the current directory and reports
    no record, which looks like a repository with no rationale rather than a lookup
    pointed at the wrong file.
    """
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    import codegraph.commands.why as why_module

    why_module._QUERY_DB = None
    parse_location("make_response")
    assert why_module._QUERY_DB == db_path_for_root(tmp_path)


def test_root_option_points_at_another_repository(tmp_path, monkeypatch) -> None:
    """A symbol has no path to carry its repository, so `--root` supplies it."""
    other = tmp_path / "elsewhere"
    other.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)
    monkeypatch.chdir(other)

    assert parse_location("make_response", root=repo) == ("src/app.py", 100)
