"""Call edges must prefer the callee defined beside the call site."""

from __future__ import annotations

from codegraph.parser.treesitter_py import PythonParser


def _pairs(parser, nodes):
    return {
        (e.from_uid.split("::")[2].split("@")[0], e.to_uid.split("::")[2].split("@")[0])
        for e in parser.extract_edges(nodes)
        if e.kind == "uses"
    }


def test_call_prefers_the_callee_in_the_same_file() -> None:
    """`helper()` resolves to the local `helper`, not to every `helper` in scope."""
    from codegraph.parser.treesitter_py import PythonParser as P

    parser = P()
    local = parser.parse_text(
        "app.py", "def helper():\n    return 1\n\ndef run():\n    return helper()\n"
    )
    remote = P().parse_text("other.py", "def helper():\n    return 2\n")

    pairs = _pairs(parser, local)
    # Scope holds a foreign helper with the same name.
    edges = [e for e in parser.extract_edges(local, scope=remote) if e.kind == "uses"]

    assert pairs == {("run", "helper")}
    assert len(edges) == 1
    assert edges[0].to_uid.split("::")[0] == "app.py"


def test_call_falls_back_to_cross_file_targets() -> None:
    """With no local definition, the remote candidate is still linked."""
    parser = PythonParser()
    caller = parser.parse_text("app.py", "def run():\n    return helper()\n")
    remote = PythonParser().parse_text("util.py", "def helper():\n    return 2\n")

    edges = [e for e in parser.extract_edges(caller, scope=remote) if e.kind == "uses"]

    assert len(edges) == 1
    assert edges[0].to_uid.split("::")[0] == "util.py"


def test_local_match_does_not_leak_other_same_name_edges() -> None:
    """Three files define `build`; only the local one is linked."""
    parser = PythonParser()
    local = parser.parse_text(
        "app.py", "def build():\n    return 1\n\ndef run():\n    return build()\n"
    )
    scope = PythonParser().parse_text("a.py", "def build():\n    return 2\n")
    scope += PythonParser().parse_text("b.py", "def build():\n    return 3\n")

    edges = [e for e in parser.extract_edges(local, scope=scope) if e.kind == "uses"]

    assert len(edges) == 1
    assert edges[0].to_uid.startswith("app.py::")
