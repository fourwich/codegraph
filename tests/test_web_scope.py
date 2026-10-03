"""The web API must never widen a scope behind the caller's back."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from codegraph.commands import serve
from codegraph.models import CodeNode, Decision, DecisionSource, DecisionTier
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decision_links,
    insert_decisions,
    insert_nodes,
)
from codegraph.web import app as app_module

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def _node(uid: str, path: str, when: datetime) -> CodeNode:
    return CodeNode(
        uid=uid,
        kind="function",
        name=uid,
        file_path=path,
        line_start=1,
        line_end=10,
        language="python",
        valid_from=when,
    )


def _decision(uid: str, path: str, when: datetime) -> Decision:
    return Decision(
        uid=uid,
        content=f"decision {uid}",
        reason="because it matters",
        status="accepted",
        source=DecisionSource.ADR,
        source_ref=f"ADR {uid}",
        timestamp=when,
        file_path=path,
        tier=DecisionTier.DECISION,
    )


def _seed(root: Path) -> None:
    conn = connect(db_path_for_root(root))
    try:
        init_schema(conn)
        insert_nodes(
            conn,
            [
                _node("src_fn", "src/app.py", EARLIER),
                _node("lib_fn", "lib/util.py", NOW),
            ],
        )
        # "governed" is recorded in docs/adr but binds to src/app.py.
        insert_decisions(
            conn,
            [
                _decision("governed", "docs/adr/001.md", NOW),
                _decision("lib_dec", "lib/util.py", NOW),
            ],
        )
        insert_decision_links(conn, [("governed", "src_fn", "src/app.py", 1)])
    finally:
        conn.close()


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    _seed(tmp_path)
    monkeypatch.setattr(app_module, "_sqlite_path", lambda: db_path_for_root(tmp_path))
    return TestClient(app_module.create_app())


def test_graph_scope_does_not_fall_back_to_global(tmp_path: Path, monkeypatch) -> None:
    """A scope with no decisions reports none instead of showing unrelated ones."""
    client = _client(tmp_path, monkeypatch)

    body = client.get("/api/graph", params={"scope": "tests"}).json()

    assert body["decisions"] == []
    assert body["stats"]["decisions"] == 0
    assert body["stats"]["nodes"] == 0


def test_graph_scope_includes_governed_decisions(tmp_path: Path, monkeypatch) -> None:
    """An ADR recorded in docs/adr is in scope for the code it governs."""
    client = _client(tmp_path, monkeypatch)

    src = client.get("/api/graph", params={"scope": "src"}).json()
    lib = client.get("/api/graph", params={"scope": "lib"}).json()

    assert {d["uid"] for d in src["decisions"]} == {"governed"}
    assert {d["uid"] for d in lib["decisions"]} == {"lib_dec"}
    assert src["stats"]["nodes"] == 1
    assert lib["stats"]["nodes"] == 1


def test_graph_scope_is_a_path_boundary(tmp_path: Path, monkeypatch) -> None:
    """`src` must not match `src2`."""
    conn = connect(db_path_for_root(tmp_path))
    try:
        init_schema(conn)
        insert_nodes(
            conn,
            [_node("other", "src2/app.py", NOW), _node("real", "src/app.py", NOW)],
        )
    finally:
        conn.close()
    monkeypatch.setattr(app_module, "_sqlite_path", lambda: db_path_for_root(tmp_path))

    body = TestClient(app_module.create_app()).get(
        "/api/graph", params={"scope": "src"}
    ).json()

    assert body["stats"]["nodes"] == 1


def test_why_matches_the_cli_resolution(tmp_path: Path, monkeypatch) -> None:
    """The API must find a governed decision bound to the covering symbol."""
    client = _client(tmp_path, monkeypatch)

    body = client.get("/api/why", params={"file": "src/app.py", "line": 5}).json()

    assert body["binding"] == "line"
    assert [d["uid"] for d in body["decisions"]] == ["governed"]
    assert body["node"]["uid"] == "src_fn"


def test_why_labels_the_directory_fallback(tmp_path: Path, monkeypatch) -> None:
    """A directory-level answer is still an answer, but it must say so."""
    client = _client(tmp_path, monkeypatch)

    body = client.get("/api/why", params={"file": "lib/other.py", "line": 5}).json()

    assert body["binding"] == "dir"
    assert [d["uid"] for d in body["decisions"]] == ["lib_dec"]


def test_dir_fallback_never_reaches_the_whole_graph(tmp_path: Path, monkeypatch) -> None:
    """A root-level file must not inherit every decision in the repository."""
    conn = connect(db_path_for_root(tmp_path))
    try:
        init_schema(conn)
        insert_decisions(
            conn,
            [
                _decision("deep", "src/pkg/deep.py", NOW),
                _decision("root", "README.md", NOW),
            ],
        )
    finally:
        conn.close()
    monkeypatch.setattr(app_module, "_sqlite_path", lambda: db_path_for_root(tmp_path))

    body = TestClient(app_module.create_app()).get(
        "/api/why", params={"file": "CHANGELOG.md", "line": 5}
    ).json()

    assert [d["uid"] for d in body["decisions"]] == ["root"]


def test_timeline_respects_scope(tmp_path: Path, monkeypatch) -> None:
    """Slider ticks must come from the scoped files only."""
    client = _client(tmp_path, monkeypatch)

    assert client.get("/api/timeline", params={"scope": "src"}).json()["ticks"] == [
        EARLIER.date().isoformat()
    ]
    assert client.get("/api/timeline", params={"scope": "lib"}).json()["ticks"] == [
        NOW.date().isoformat()
    ]
    assert len(client.get("/api/timeline", params={"scope": "."}).json()["ticks"]) == 2


def test_timeline_stays_empty_without_an_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        app_module, "_sqlite_path", lambda: tmp_path / "missing" / "graph.db"
    )
    client = TestClient(app_module.create_app())
    assert client.get("/api/timeline").json()["ticks"] == []


def test_browser_opens_only_after_the_server_is_listening(monkeypatch) -> None:
    """Opening before the port is bound shows the user a connection error."""
    opened: list[str] = []
    monkeypatch.setattr(serve.webbrowser, "open", lambda url: opened.append(url))

    class NotStarted:
        started = False

    serve.open_when_ready(NotStarted(), "http://127.0.0.1:9/", timeout=0.2)
    assert opened == []

    class Started:
        started = True

    serve.open_when_ready(Started(), "http://127.0.0.1:9/", timeout=0.2)
    assert opened == ["http://127.0.0.1:9/"]


def test_browser_helper_is_started_in_a_background_thread(monkeypatch) -> None:
    """`serve` must not block before uvicorn runs."""
    threads: list[threading.Thread] = []
    real_thread = threading.Thread

    def fake_thread(*args, **kwargs):
        thread = real_thread(*args, **kwargs)
        threads.append(thread)
        return thread

    monkeypatch.setattr(serve.threading, "Thread", fake_thread)
    monkeypatch.setattr(serve.webbrowser, "open", lambda url: None)

    class FakeServer:
        started = True

        def __init__(self, config):  # noqa: D107
            self.config = config

        def run(self) -> None:
            return None

    import uvicorn

    monkeypatch.setattr(uvicorn, "Server", FakeServer)
    monkeypatch.setattr(uvicorn, "Config", lambda *a, **k: object())

    serve.serve_command(port=8123, open_browser=True)

    assert threads and threads[0].daemon


def test_static_ui_has_no_dead_kind_filter() -> None:
    """Parsers never emit kind 'method', so the checkbox must not exist."""
    html = (Path(app_module.STATIC_DIR) / "index.html").read_text(encoding="utf-8")
    assert 'value="method"' not in html
    assert 'max="100"' not in html


def test_slider_uses_index_not_percent() -> None:
    """The slider value is a tick index, so the maths must not divide by 100."""
    js = (Path(app_module.STATIC_DIR) / "app.js").read_text(encoding="utf-8")
    assert "/ 100" not in js
    assert 'slider.max = String(max)' in js
