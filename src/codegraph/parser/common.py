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
    return raw[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")


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
