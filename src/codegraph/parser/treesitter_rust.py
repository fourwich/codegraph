"""Rust tree-sitter parser."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import tree_sitter_rust as tsrust
from tree_sitter import Language, Parser

from codegraph.models import CodeNode
from codegraph.parser.base import BaseParser
from codegraph.parser.common import decl_name, make_node, rel_path, simple_callee

logger = logging.getLogger(__name__)
_LANG = Language(tsrust.language())

KIND_MAP = {
    "function_item": "function",
    "struct_item": "class",
    "impl_item": "class",
    "enum_item": "class",
    "trait_item": "class",
    "function_signature_item": "function",
}


class RustParser(BaseParser):
    """Parse Rust sources for fns, types, and calls."""

    language = "rust"

    def parse_file(self, path: Path) -> list[CodeNode]:
        """Parse a Rust file from disk."""
        rel = rel_path(path)
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Read failed, skip %s: %s", path, exc)
            return []
        return self.parse_text(rel, source)

    def parse_text(
        self,
        rel_path_: str,
        source: str,
        commit_sha: str = "",
        valid_from: datetime | None = None,
    ) -> list[CodeNode]:
        """Parse Rust source text."""
        rel = rel_path_.replace("\\", "/")
        self._calls.clear()
        raw = source.encode("utf-8")
        tree = Parser(_LANG).parse(raw)
        out: list[CodeNode] = []
        self._walk(tree.root_node, raw, rel, out, None, "", commit_sha, valid_from)
        return out

    def _walk(self, node, raw, rel, out, parent_uid, current_fn, commit_sha, valid_from):
        kind = KIND_MAP.get(node.type)
        name = decl_name(node, raw)
        next_parent, next_fn = parent_uid, current_fn
        if kind and name:
            code_node = make_node(
                node, rel, kind, name, parent_uid, self.language, commit_sha, valid_from
            )
            out.append(code_node)
            if kind in {"class", "function"}:
                next_parent = code_node.uid
            if kind == "function":
                next_fn = name
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            callee = simple_callee(fn, raw) if fn is not None else None
            if callee:
                self._calls.append(
                    (current_fn or name or "", callee, node.start_point[0] + 1, rel)
                )
        for child in node.children:
            self._walk(child, raw, rel, out, next_parent, next_fn, commit_sha, valid_from)
