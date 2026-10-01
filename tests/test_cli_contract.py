"""CLI output contracts: machine-readable stdout, absolute path input."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.commands.why import parse_location

runner = CliRunner()


def test_index_json_stdout_is_only_json(tmp_path: Path) -> None:
    """`index --json` must not mix progress output into stdout."""
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    result = runner.invoke(app, ["index", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)  # raises if anything else is on stdout
    assert payload["nodes"] == 1


def test_why_accepts_an_absolute_path(tmp_path: Path, monkeypatch) -> None:
    """Editors pass absolute paths; the query must still resolve."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "app.py"
    target.write_text("def f():\n    return 1\n", encoding="utf-8")

    assert parse_location(f"{target}:12")[0] == "src/app.py"

    relative = parse_location("src/app.py:12")
    assert relative == ("src/app.py", 12)


def test_error_message_uses_a_real_path() -> None:
    """The example in the error must be a path that can exist."""
    result = runner.invoke(app, ["why", "badformat"])
    assert result.exit_code == 2
    assert "session.ts" not in result.stdout
