"""`why` accepts a symbol name, and a miss suggests what does exist.

`path:line` is precise but callers rarely have it: reading unfamiliar code, or asking an
agent to explain `insert_nodes`, means the symbol is known and the line is not. These
cover the resolution, the fallbacks, and the error that replaces a bare rejection.
"""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.commands.why import LocationError, _near_miss_hint, parse_location
from codegraph.models import CodeNode
from codegraph.storage import (
    connect,
    db_path_for_root,
    find_nodes_by_name,
    init_schema,
    insert_nodes,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _node(uid: str, name: str, path: str, start: int, end: int) -> CodeNode:
    return CodeNode(
        uid=uid,
        kind="function",
        name=name,
        file_path=path,
        line_start=start,
        line_end=end,
        language="python",
        valid_from=NOW,
    )


def _db(tmp_path):
    conn = connect(db_path_for_root(tmp_path))
    init_schema(conn)
    insert_nodes(
        conn,
        [
            _node("u1", "insert_nodes", "src/storage.py", 199, 223),
            _node("u2", "insert_edges", "src/storage.py", 230, 260),
            _node("u3", "load_nodes", "src/storage.py", 300, 320),
            _node("u4", "insert_nodes", "tests/test_storage.py", 10, 20),
        ],
    )
    return conn


def test_find_nodes_by_name_returns_every_definition(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        nodes = find_nodes_by_name(conn, "insert_nodes")
    finally:
        conn.close()
    assert {n.file_path for n in nodes} == {"src/storage.py", "tests/test_storage.py"}


def test_find_nodes_by_name_is_exact(tmp_path) -> None:
    """A prefix must not match: the caller cannot tell a near hit from the real one."""
    conn = _db(tmp_path)
    try:
        assert find_nodes_by_name(conn, "insert") == []
    finally:
        conn.close()


def test_find_nodes_by_name_unknown_is_empty(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        assert find_nodes_by_name(conn, "nothing_here") == []
    finally:
        conn.close()


def test_parse_location_still_takes_path_and_line(tmp_path, monkeypatch) -> None:
    _db(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert parse_location("src/storage.py:200") == ("src/storage.py", 200)


def test_parse_location_resolves_a_symbol(tmp_path, monkeypatch) -> None:
    _db(tmp_path)
    monkeypatch.chdir(tmp_path)
    path, line = parse_location("load_nodes")
    assert path == "src/storage.py"
    # The symbol starts at 300; the resolved line must land inside it.
    assert 300 <= line <= 320


def test_parse_location_rejects_an_unknown_symbol(tmp_path, monkeypatch) -> None:
    _db(tmp_path)
    monkeypatch.chdir(tmp_path)
    try:
        parse_location("nope_not_here")
    except LocationError as exc:
        assert "path:line" in str(exc)
    else:
        raise AssertionError("expected LocationError")


def test_parse_location_rejects_an_empty_value() -> None:
    try:
        parse_location("   ")
    except LocationError as exc:
        assert "cannot be empty" in str(exc)
    else:
        raise AssertionError("expected LocationError")


def test_near_miss_hint_prefers_a_prefix_match(tmp_path, monkeypatch) -> None:
    _db(tmp_path)
    monkeypatch.chdir(tmp_path)
    hint = _near_miss_hint("insert")
    assert hint.split(", ")[0].startswith("insert")


def test_near_miss_hint_is_empty_without_a_database(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert _near_miss_hint("anything") == ""


def test_near_miss_hint_ignores_tiny_queries(tmp_path, monkeypatch) -> None:
    """Two characters match too much to be a useful suggestion."""
    _db(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert _near_miss_hint("in") == ""
