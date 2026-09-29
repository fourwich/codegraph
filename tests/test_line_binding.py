"""Tests for line-level decision binding via git diffs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from codegraph.git.diff import get_changed_lines, _parse_patch_lines
from codegraph.models import CodeNode, Decision, DecisionSource, DecisionStatus
from codegraph.commands.index import bind_decisions_to_lines
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decision_links,
    insert_decisions,
    insert_nodes,
    query_decisions_for_line_links,
)


def test_parse_patch_lines_added() -> None:
    patch = (
        "@@ -1,2 +1,4 @@\n"
        " keep\n"
        "+new1\n"
        "+new2\n"
        " keep2\n"
        "+new3\n"
    )
    lines = _parse_patch_lines(patch)
    assert 2 in lines  # new1
    assert 3 in lines  # new2
    assert 5 in lines or 4 in lines


def test_get_changed_lines_on_temp_git(tmp_path: Path) -> None:
    import git
    from git import Actor

    repo = git.Repo.init(str(tmp_path))
    f = tmp_path / "app.py"
    f.write_text("def a():\n    return 1\n", encoding="utf-8")
    repo.index.add(["app.py"])
    c1 = repo.index.commit("feat: add a because demo", author=Actor("a", "a@e.com"), committer=Actor("a", "a@e.com"))
    f.write_text("def a():\n    return 2\n\ndef b():\n    return 3\n", encoding="utf-8")
    repo.index.add(["app.py"])
    c2 = repo.index.commit("feat: add b since needed", author=Actor("a", "a@e.com"), committer=Actor("a", "a@e.com"))

    changed = get_changed_lines(tmp_path, c2.hexsha)
    assert "app.py" in changed
    assert any(n >= 2 for n in changed["app.py"])


def test_bind_and_query_line_links(tmp_path: Path) -> None:
    node = CodeNode(
        uid="n1",
        kind="function",
        name="a",
        file_path="src/x.py",
        line_start=1,
        line_end=5,
        language="python",
    )
    decision = Decision(
        uid="d1",
        content="Use X because Y",
        reason="because Y",
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT,
        source_ref="commit deadbeef",
        timestamp=datetime.now(timezone.utc),
        file_path="src/x.py",
        line=3,
    )
    links = bind_decisions_to_lines(tmp_path, [decision], [node])
    # no git repo -> falls back to decision.file/line
    assert links and links[0][0] == "d1"
    assert links[0][3] == 3

    db = db_path_for_root(tmp_path)
    conn = connect(db)
    try:
        init_schema(conn)
        insert_nodes(conn, [node])
        insert_decisions(conn, [decision])
        insert_decision_links(conn, links)
        found = query_decisions_for_line_links(conn, "src/x.py", 3)
        assert found and found[0].uid == "d1"
    finally:
        conn.close()

def test_find_nodes_containing_lines(tmp_path: Path) -> None:
    from codegraph.storage import find_nodes_containing_lines, insert_nodes

    node = CodeNode(
        uid="n9",
        kind="function",
        name="z",
        file_path="src/z.py",
        line_start=10,
        line_end=20,
        language="python",
    )
    conn = connect(db_path_for_root(tmp_path))
    try:
        init_schema(conn)
        insert_nodes(conn, [node])
        uids = find_nodes_containing_lines(conn, "src/z.py", [12, 99])
        assert uids == ["n9"]
    finally:
        conn.close()
