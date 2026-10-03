"""Shared helpers for tree-sitter language parsers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tree_sitter import Node

from codegraph.models import CodeNode, make_uid, normalize_location_path


def rel_path(path: Path) -> str:
    """Return a repo-relative forward-slash path."""
    try:
        return normalize_location_path(str(path.resolve().relative_to(Path.cwd())))
    except ValueError:
        return normalize_location_path(str(path))


def decl_name(node: Node, raw: bytes) -> str | None:
    """Extract the name field from a declaration node."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    return _text(name_node, raw)


def _text(node: Node, raw: bytes) -> str:
    """Decode the source slice covered by an AST node."""
    return raw[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


# Identifiers that can hold a declaration's name in the grammars we support.
_NAME_TYPES = frozenset(
    {
        "identifier",
        "field_identifier",
        "type_identifier",
        "namespace_identifier",
        "operator_name",
        "destructor_name",
    }
)

_FUNCTION_DECLARATOR_TYPES = frozenset(
    {"function_declarator", "function_definition", "method_declaration"}
)


def declarator_name(node: Node, raw: bytes, depth: int = 0) -> str | None:
    """Resolve a C/C++ style declarator chain to the declared name.

    `int Calculator::compute(int)` nests a qualified identifier inside a
    function declarator, and an in-class method nests a `field_identifier`;
    looking only for a `name` field misses both.
    """
    if depth > 8:
        return None
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _text(name_node, raw)
    for field in ("declarator", "type"):
        child = node.child_by_field_name(field)
        if child is not None:
            found = declarator_name(child, raw, depth + 1)
            if found:
                return found
    for child in node.children:
        if child.type in _NAME_TYPES:
            return _text(child, raw)
    return None


def declares_a_function(node: Node) -> bool:
    """True when a declaration's declarator chain declares a function.

    Covers `int helper(int);` (a `declaration`), `int spin(int n);` inside a
    class (a `field_declaration`) and rejects `int limit = 3;`.
    """
    current = node
    for _ in range(8):
        if current.type in _FUNCTION_DECLARATOR_TYPES:
            return True
        nxt = current.child_by_field_name("declarator")
        if nxt is None:
            return False
        current = nxt
    return False


def type_name(node: Node, raw: bytes, depth: int = 0) -> str | None:
    """Return the bare type name from a type node, unwrapping pointers/generics.

    Used for Go receivers (`*Calculator`) and Rust `impl` blocks.
    """
    if depth > 6:
        return None
    if node.type in _NAME_TYPES:
        return _text(node, raw)
    for field in ("type", "name"):
        child = node.child_by_field_name(field)
        if child is not None:
            found = type_name(child, raw, depth + 1)
            if found:
                return found
    for child in node.children:
        if child.type == "type_identifier":
            return _text(child, raw)
    return None


def simple_callee(fn_node: Node, raw: bytes) -> str | None:
    """Extract a simple callee name from a call function expression."""
    if fn_node.type in {"identifier", "name", "field_identifier", "type_identifier"}:
        return raw[fn_node.start_byte : fn_node.end_byte].decode("utf-8", errors="replace")
    for field in ("property", "attribute", "field", "name"):
        child = fn_node.child_by_field_name(field)
        if child is not None:
            return raw[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
    return None


def make_node(
    node: Node,
    rel: str,
    kind: str,
    name: str,
    parent_uid: str | None,
    language: str,
    commit_sha: str = "",
    valid_from: datetime | None = None,
) -> CodeNode:
    """Build a CodeNode from an AST node."""
    return CodeNode(
        uid=make_uid(rel, kind, name, node.start_point[0] + 1, commit_sha),
        kind=kind,
        name=name,
        file_path=rel,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        language=language,
        parent_uid=parent_uid,
        commit_sha=commit_sha,
        valid_from=valid_from or datetime.fromtimestamp(0),
        valid_to=None,
    )
