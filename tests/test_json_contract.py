"""The `--json` outputs are an editor contract, so their shape is pinned.

`why --json` feeds the VSCode extension; `graph --json` and `decisions --json` are
for scripts. One shared serializer (`decision_to_dict`) keeps them from drifting,
and these tests assert the documented keys instead of whatever pydantic happens to
emit today.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codegraph.cli import app

runner = CliRunner()

DECISION_KEYS = {
    "uid",
    "content",
    "reason",
    "alternatives",
    "status",
    "source",
    "source_ref",
    "timestamp",
    "author",
    "file_path",
    "line",
    "constraints",
    "confidence",
    "category",
    "tier",
}

NODE_KEYS = {
    "uid",
    "kind",
    "name",
    "file_path",
    "line_start",
    "line_end",
    "language",
    "commit_sha",
}


def _json(output: str) -> dict:
    """Parse the JSON document, allowing progress lines captured by CliRunner."""
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end > start, output[:400]
    return json.loads(output[start : end + 1])


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "a",
        "GIT_AUTHOR_EMAIL": "a@e.com",
        "GIT_COMMITTER_NAME": "a",
        "GIT_COMMITTER_EMAIL": "a@e.com",
    }
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture()
def indexed_repo(tmp_path: Path, monkeypatch) -> Path:
    """A tiny git repo with one rationale-bearing commit, indexed."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "app.py").write_text(
        "def helper():\n    return 1\n\ndef run():\n    return helper()\n", encoding="utf-8"
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "feat: add helper because it removes duplication")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["index", ".", "--depth", "5", "--json"])
    assert result.exit_code == 0, result.output
    return tmp_path


def test_index_json_shape(indexed_repo: Path) -> None:
    result = runner.invoke(app, ["index", ".", "--depth", "5", "--json"])

    payload = _json(result.output)
    assert set(payload) == {"root", "commits", "nodes", "edges", "decisions"}
    assert payload["nodes"] >= 2


def test_why_json_shape(indexed_repo: Path) -> None:
    result = runner.invoke(app, ["why", "app.py:1", "--json"])

    payload = _json(result.output)
    assert set(payload) == {"file", "line", "node", "decisions", "binding", "related"}
    assert set(payload["node"]) == NODE_KEYS
    assert payload["node"]["name"] == "helper"
    assert payload["decisions"], "the commit body records a decision"
    assert set(payload["decisions"][0]) == DECISION_KEYS
    assert payload["related"] == []


def test_why_json_is_empty_but_valid_without_a_record(indexed_repo: Path) -> None:
    result = runner.invoke(app, ["why", "sub/other.py:1", "--json"])

    payload = _json(result.output)
    assert result.exit_code == 1
    assert payload["decisions"] == []
    assert isinstance(payload["related"], list)


def test_graph_json_shape(indexed_repo: Path) -> None:
    from datetime import date

    result = runner.invoke(
        app, ["graph", "--at", date.today().isoformat(), "--scope", ".", "--json"]
    )

    payload = _json(result.output)
    assert set(payload) == {
        "date",
        "scope",
        "nodes",
        "edges",
        "decisions",
        "summary",
        "decision_records",
    }
    assert payload["nodes"] >= 2
    assert isinstance(payload["summary"], list)


def test_decisions_json_shape(indexed_repo: Path) -> None:
    result = runner.invoke(app, ["decisions", "--json"])

    payload = _json(result.output)
    assert set(payload) == {"file", "count", "decisions"}
    assert payload["file"] is None
    assert payload["count"] == len(payload["decisions"])
    assert payload["decisions"]
    assert set(payload["decisions"][0]) == DECISION_KEYS


def test_decisions_json_can_be_empty(indexed_repo: Path) -> None:
    result = runner.invoke(app, ["decisions", "--file", "missing.py", "--json"])

    payload = _json(result.output)
    assert result.exit_code == 1
    assert payload["decisions"] == []
    assert payload["count"] == 0
