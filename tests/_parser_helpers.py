"""Helpers shared by parser tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codegraph.models import CodeNode, Edge  # noqa: E402


def symbol(uid: str) -> str:
    """Return the bare symbol name from a node uid (`path::kind::name@line::sha`)."""
    return uid.split("::")[2].split("@")[0]


def uses_pairs(edges: list[Edge]) -> set[tuple[str, str]]:
    """Symbol-level (caller, callee) pairs for every uses edge."""
    return {(symbol(e.from_uid), symbol(e.to_uid)) for e in edges if e.kind == "uses"}


def by_name(nodes: list[CodeNode], name: str) -> CodeNode:
    """Return the first node with this name."""
    return next(n for n in nodes if n.name == name)
