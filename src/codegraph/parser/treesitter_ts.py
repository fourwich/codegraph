"""TypeScript / TSX tree-sitter parser."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from tree_sitter import Language, Node, Parser

import tree_sitter_typescript as tstypescript

from codegraph.models import CodeNode, make_uid, normalize_location_path
from codegraph.parser.base import BaseParser

logger = logging.getLogger(__name__)

_TS_LANGUAGE = Language(tstypescript.language_typescript())
_TSX_LANGUAGE = Language(tstypescript.language_tsx())

_KIND_MAP = {
    "function_declaration": "function",
    "class_declaration": "class",
    "variable_declaration": "variable",
    "method_definition": "function",
}


class TypeScriptParser(BaseParser):
    """Parse .ts / .tsx for declarations and call relations."""

    language = "typescript"

    def parse_file(self, path: Path) -> list[CodeNode]:
        """Parse a TypeScript source file from disk."""
        try:
            rel = normalize_location_path(str(path.resolve().relative_to(Path.cwd())))
        except ValueError:
            rel = normalize_location_path(str(path))
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Read failed, skip %s: %s", path, exc)
            return []
        return self.parse_text(rel, source)

    def parse_text(
        self,
        rel_path: str,
        source: str,
        commit_sha: str = "",
        valid_from: datetime | None = None,
    ) -> list[CodeNode]:
        """Parse TypeScript source text into CodeNode records."""
        rel = normalize_location_path(rel_path)
        self._calls.clear()
        raw = source.encode("utf-8")
        suffix = Path(rel_path).suffix.lower()
        lang = _TSX_LANGUAGE if suffix == ".tsx" else _TS_LANGUAGE
        tree = Parser(lang).parse(raw)
        out: list[CodeNode] = []
        self._walk(
            tree.root_node,
            raw,
            rel,
            out,
            parent_uid=None,
            current_fn="",
            commit_sha=commit_sha,
            valid_from=valid_from,
        )
        return out

    def _walk(
        self,
        node: Node,
        raw: bytes,
        rel: str,
        out: list[CodeNode],
        parent_uid: str | None,
        current_fn: str,
        commit_sha: str = "",
        valid_from: datetime | None = None,
    ) -> None:
        """Depth-first walk collecting declarations and calls."""
        kind = _KIND_MAP.get(node.type)
        name = self._decl_name(node, raw)
        next_parent = parent_uid
        next_fn = current_fn

        if kind and name:
            code_node = self._make_node(
                node, rel, kind, name, parent_uid, commit_sha, valid_from
            )
            out.append(code_node)
            if kind in {"class", "function"}:
                next_parent = code_node.uid
            if kind == "function":
                next_fn = name

        if node.type == "call_expression":
            self._record_call(node, raw, rel, current_fn if current_fn else name or "")

        for child in node.children:
            self._walk(
                child,
                raw,
                rel,
                out,
                next_parent,
                next_fn,
                commit_sha=commit_sha,
                valid_from=valid_from,
            )

    def _make_node(
        self,
        node: Node,
        rel: str,
        kind: str,
        name: str,
        parent_uid: str | None,
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
            language=self.language,
            parent_uid=parent_uid,
            commit_sha=commit_sha,
            valid_from=valid_from or datetime.fromtimestamp(0),
            valid_to=None,
        )

    @staticmethod
    def _decl_name(node: Node, raw: bytes) -> str | None:
        """Extract declaration name; variable_declaration digs into declarator."""
        if node.type == "variable_declaration":
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node is not None:
                        return raw[name_node.start_byte : name_node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
            return None

        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        return raw[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")

    def _record_call(self, node: Node, raw: bytes, rel: str, caller_name: str) -> None:
        """Record a call_expression with its callee name."""
        fn = node.child_by_field_name("function")
        if fn is None:
            return
        callee = self._callee_name(fn, raw)
        if not callee:
            return
        line = node.start_point[0] + 1
        self._calls.append((caller_name, callee, line, rel))

    @staticmethod
    def _callee_name(fn_node: Node, raw: bytes) -> str | None:
        """Extract a simple callee name (identifier / member property)."""
        if fn_node.type == "identifier":
            return raw[fn_node.start_byte : fn_node.end_byte].decode("utf-8", errors="replace")
        if fn_node.type == "member_expression":
            prop = fn_node.child_by_field_name("property")
            if prop is not None:
                return raw[prop.start_byte : prop.end_byte].decode("utf-8", errors="replace")
        return None
