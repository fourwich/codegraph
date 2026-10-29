"""`codegraph decisions` must work without a --file.

Watching the whole decision timeline is the natural first use; requiring --file
turned the command's own help output into the only thing a new user saw.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.models import Decision, DecisionSource, DecisionStatus, DecisionTier
from codegraph.storage import connect, db_path_for_root, init_schema, insert_decisions

runner = CliRunner()


def _seed(tmp_path: Path) -> None:
    conn = connect(db_path_for_root(tmp_path))
    try:
        init_schema(conn)
        insert_decisions(
            conn,
            [
                Decision(
                    uid="d-a",
                    content="Use SQLite because it is embedded",
                    reason="Because no server is needed",
                    status=DecisionStatus.ACCEPTED,
                    source=DecisionSource.ADR,
                    source_ref="ADR 001",
                    timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    file_path="docs/adr/001.md",
                    tier=DecisionTier.DECISION,
                ),
                Decision(
                    uid="d-b",
                    content="Prefer streaming because files are large",
                    reason="Because buffers would not fit in memory",
                    status=DecisionStatus.ACCEPTED,
                    source=DecisionSource.COMMIT,
                    source_ref="commit abc",
                    timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
                    file_path="src/app.py",
                    tier=DecisionTier.DECISION,
                ),
            ],
        )
    finally:
        conn.close()


def test_decisions_without_file_lists_everything(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["decisions", "--timeline"])

    assert result.exit_code == 0
    assert "all files" in result.output
    assert "SQLite" in result.output
    assert "streaming" in result.output


def test_decisions_with_file_stays_scoped(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["decisions", "--file", "src/app.py", "--timeline"])

    assert result.exit_code == 0
    assert "streaming" in result.output
    assert "SQLite" not in result.output


def test_decisions_without_records_says_so(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["decisions", "--file", "src/missing.py"])

    assert result.exit_code == 1
    assert "No decision record found" in result.output
