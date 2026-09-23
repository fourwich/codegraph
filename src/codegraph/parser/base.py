"""Parser 抽象基类：统一多语言 AST 抽取接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from codegraph.models import CodeNode, Edge


class BaseParser(ABC):
    """语言解析器基类。"""

    language: str = "unknown"

    def __init__(self) -> None:
        # 记录调用点：(caller_name, callee_name, line, file_path)
        self._calls: list[tuple[str, str, int, str]] = []

    @abstractmethod
    def parse_file(self, path: Path) -> list[CodeNode]:
        """解析源文件，返回 CodeNode 列表。

        Args:
            path: 源文件路径。

        Returns:
            抽取到的代码节点列表；解析失败可返回空列表。
        """

    def extract_edges(self, nodes: list[CodeNode]) -> list[Edge]:
        """从节点层级与调用记录中抽取关系边。

        Args:
            nodes: 已解析的节点列表。

        Returns:
            contains / defined_by / uses 边。
        """
        edges: list[Edge] = []
        edges.extend(self._hierarchy_edges(nodes))
        edges.extend(self._call_edges(nodes))
        return edges

    def _hierarchy_edges(self, nodes: list[CodeNode]) -> list[Edge]:
        """由 parent_uid 生成 contains / defined_by 边。"""
        by_uid = {n.uid: n for n in nodes}
        edges: list[Edge] = []
        for node in nodes:
            if node.parent_uid and node.parent_uid in by_uid:
                parent = by_uid[node.parent_uid]
                edges.append(
                    Edge(
                        from_uid=parent.uid,
                        to_uid=node.uid,
                        kind="contains",
                        file_path=node.file_path,
                        line=node.line_start,
                    )
                )
                edges.append(
                    Edge(
                        from_uid=node.uid,
                        to_uid=parent.uid,
                        kind="defined_by",
                        file_path=node.file_path,
                        line=node.line_start,
                    )
                )
        return edges

    def _call_edges(self, nodes: list[CodeNode]) -> list[Edge]:
        """把调用点匹配到已知节点，生成 uses 边。"""
        by_name: dict[str, list[CodeNode]] = {}
        for node in nodes:
            by_name.setdefault(node.name, []).append(node)

        # uid -> 节点，用于定位 caller
        ordered = sorted(nodes, key=lambda n: (n.line_start, n.line_end))
        edges: list[Edge] = []
        seen: set[tuple[str, str, int]] = set()

        for caller_name, callee_name, line, file_path in self._calls:
            caller = self._find_caller(ordered, caller_name, line, file_path)
            targets = by_name.get(callee_name, [])
            if caller is None or not targets:
                continue
            for target in targets:
                key = (caller.uid, target.uid, line)
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    Edge(
                        from_uid=caller.uid,
                        to_uid=target.uid,
                        kind="uses",
                        file_path=file_path,
                        line=line,
                    )
                )
        return edges

    @staticmethod
    def _find_caller(
        nodes: list[CodeNode], caller_name: str, line: int, file_path: str
    ) -> CodeNode | None:
        """找到包含调用行的同名 caller 节点。"""
        candidates = [
            n
            for n in nodes
            if n.name == caller_name
            and n.file_path == file_path
            and n.contains_line(line)
        ]
        if not candidates:
            return None
        # 取范围最小的（最内层函数/方法）
        return min(candidates, key=lambda n: n.line_end - n.line_start)
