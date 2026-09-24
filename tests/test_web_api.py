"""API tests for the CodeGraph FastAPI app (no browser)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from codegraph.web.app import create_app


def test_health() -> None:
    """Health endpoint returns ok."""
    client = TestClient(create_app())
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_graph_endpoint() -> None:
    """Graph endpoint returns node/decision/stats keys."""
    client = TestClient(create_app())
    res = client.get("/api/graph?at=2026-09-23&scope=src")
    assert res.status_code == 200
    body = res.json()
    assert "nodes" in body
    assert "decisions" in body
    assert "stats" in body


def test_why_endpoint_shape() -> None:
    """Why endpoint returns file/line/decisions keys."""
    client = TestClient(create_app())
    res = client.get("/api/why?file=src/codegraph/cli.py&line=24")
    assert res.status_code == 200
    body = res.json()
    assert body["file"].endswith("cli.py")
    assert body["line"] == 24
    assert "decisions" in body


def test_decisions_and_timeline() -> None:
    """Decisions and timeline endpoints respond."""
    client = TestClient(create_app())
    d = client.get("/api/decisions")
    t = client.get("/api/timeline?scope=src")
    assert d.status_code == 200
    assert t.status_code == 200
    assert "decisions" in d.json()
    assert "ticks" in t.json()


def test_index_html_served() -> None:
    """Root path serves the visualizer HTML."""
    client = TestClient(create_app())
    res = client.get("/")
    assert res.status_code == 200
    assert "CodeGraph" in res.text
