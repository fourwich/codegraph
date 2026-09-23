"""TypeScript / TSX tree-sitter 解析器。"""

from __future__ import annotations

import logging
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
    """解析 .ts / .tsx，提取声明与调用关系。"""

    language = "typescript"

    def parse_file(self, path: Path) -> list[CodeNode]:
        """解析 TypeScript 源文件。"""
        try:
            rel = normalize_location_path(str(path.resolve().relative_to(Path.cwd())))
        except ValueError:
            rel = normalize_location_path(str(path))
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("读取失败，跳过 %s: %s", path, exc)
            return []

        self._calls.clear()
        raw = source.encode("utf-8")
        lang = _TSX_LANGUAGE if path.suffix.lower() == ".tsx" else _TS_LANGUAGE
        tree = Parser(lang).parse(raw)
        out: list[CodeNode] = []
        self._walk(tree.root_node, raw, rel, out, parent_uid=None, current_fn="")
        return out

    def _walk(
        self,
        node: Node,
        raw: bytes,
        rel: str,
        out: list[CodeNode],
        parent_uid: str | None,
        current_fn: str,
    ) -> None:
        """深度优先遍历，抽取声明与调用。"""
        kind = _KIND_MAP.get(node.type)
        name = self._decl_name(node, raw)
        next_parent = parent_uid
        next_fn = current_fn

        if kind and name:
            code_node = self._make_node(node, rel, kind, name, parent_uid)
            out.append(code_node)
            if kind in {"class", "function"}:
                next_parent = code_node.uid
            if kind == "function":
                next_fn = name

        if node.type == "call_expression":
            self._record_call(node, raw, rel, current_fn if current_fn else name or "")

        for child in node.children:
            self._walk(child, raw, rel, out, next_parent, next_fn)

    def _make_node(
        self,
        node: Node,
        rel: str,
        kind: str,
        name: str,
        parent_uid: str | None,
    ) -> CodeNode:
        """构造 CodeNode。"""
        return CodeNode(
            uid=make_uid(rel, kind, name, node.start_point[0] + 1),
            kind=kind,
            name=name,
            file_path=rel,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language=self.language,
            parent_uid=parent_uid,
        )

    @staticmethod
    def _decl_name(node: Node, raw: bytes) -> str | None:
        """提取声明名；variable_declaration 下钻 declarator。"""
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
        """记录 call_expression 的 callee 名称。"""
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
        """提取 callee 简单名（identifier / member 属性名）。"""
        if fn_node.type == "identifier":
            return raw[fn_node.start_byte : fn_node.end_byte].decode("utf-8", errors="replace")
        if fn_node.type == "member_expression":
            prop = fn_node.child_by_field_name("property")
            if prop is not None:
                return raw[prop.start_byte : prop.end_byte].decode("utf-8", errors="replace")
        return None
