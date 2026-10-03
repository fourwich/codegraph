"""C++ tree-sitter parser."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser

from codegraph.models import CodeNode
from codegraph.parser.base import BaseParser
from codegraph.parser.common import (
    decl_name,
    declarator_name,
    declares_a_function,
    make_node,
    rel_path,
    simple_callee,
)

logger = logging.getLogger(__name__)
_LANG = Language(tscpp.language())

KIND_MAP = {
    "function_definition": "function",
    "class_specifier": "class",
    "struct_specifier": "class",
}


class CppParser(BaseParser):
    """Parse C++ sources for functions, classes, and calls."""

    language = "cpp"

    def parse_file(self, path: Path) -> list[CodeNode]:
        """Parse a C++ file from disk."""
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
        """Parse C++ source text."""
        rel = rel_path_.replace("\\", "/")
        self._calls.clear()
        raw = source.encode("utf-8")
        tree = Parser(_LANG).parse(raw)
        out: list[CodeNode] = []
        self._walk(tree.root_node, raw, rel, out, None, "", commit_sha, valid_from)
        return out

    def _walk(self, node, raw, rel, out, parent_uid, current_fn, commit_sha, valid_from):
        kind = KIND_MAP.get(node.type)
        name: str | None = None
        if node.type == "function_definition":
            name = declarator_name(node, raw)
        elif node.type in {"declaration", "field_declaration"}:
            # A prototype declares a function; `int x;` does not.
            if declares_a_function(node):
                kind = "function"
                name = declarator_name(node, raw)
        else:
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
