"""Abstract parser base: shared AST extraction interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from codegraph.models import CodeNode, Edge


class BaseParser(ABC):
    """Base class for language parsers."""

    language: str = "unknown"

    def __init__(self) -> None:
        # Call sites: (caller_name, callee_name, line, file_path)
        self._calls: list[tuple[str, str, int, str]] = []

    @abstractmethod
    def parse_file(self, path: Path) -> list[CodeNode]:
        """Parse a source file and return CodeNode records.

        Args:
            path: Source file path.

        Returns:
            Extracted code nodes; empty list when parsing fails.
        """

    def parse_text(
        self,
        rel_path: str,
        source: str,
        commit_sha: str = "",
        valid_from: datetime | None = None,
    ) -> list[CodeNode]:
        """Parse source text (default: subclasses override).

        Args:
            rel_path: Repository-relative path.
            source: File contents.
            commit_sha: Optional commit stamp.
            valid_from: Optional validity start.

        Returns:
            Extracted code nodes.
        """
        raise NotImplementedError

    def extract_edges(self, nodes: list[CodeNode]) -> list[Edge]:
        """Derive relationship edges from hierarchy and call records.

        Args:
            nodes: Already parsed nodes.

        Returns:
            contains / defined_by / uses edges.
        """
        edges: list[Edge] = []
        edges.extend(self._hierarchy_edges(nodes))
        edges.extend(self._call_edges(nodes))
        return edges

    def _hierarchy_edges(self, nodes: list[CodeNode]) -> list[Edge]:
        """Build contains / defined_by edges from parent_uid links."""
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
        """Match call sites to known nodes and emit uses edges."""
        by_name: dict[str, list[CodeNode]] = {}
        for node in nodes:
            by_name.setdefault(node.name, []).append(node)

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
        """Find the innermost same-name caller that contains the call line."""
        candidates = [
            n
            for n in nodes
            if n.name == caller_name and n.file_path == file_path and n.contains_line(line)
        ]
        if not candidates:
            return None
        # Prefer the tightest range (innermost function/method)
        return min(candidates, key=lambda n: n.line_end - n.line_start)
