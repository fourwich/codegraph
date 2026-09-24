"""Optional process-pool parsing for large working trees."""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from codegraph.models import CodeNode, Edge
from codegraph.parser.registry import get_parser_for_path, is_supported_source

logger = logging.getLogger(__name__)


def _parse_one(
    args: tuple[str, str, str, str]
) -> tuple[list[CodeNode], list[tuple[str, str, int, str]]]:
    """Parse a single file in a worker process.

    Args:
        args: (rel_path, text, commit_sha, valid_from_iso)

    Returns:
        Nodes and call-site tuples for that file.
    """
    rel, text, commit_sha, valid_from_iso = args
    parser = get_parser_for_path(Path(rel))
    if parser is None:
        return [], []
    valid_from = datetime.fromisoformat(valid_from_iso) if valid_from_iso else None
    nodes = parser.parse_text(rel, text, commit_sha=commit_sha, valid_from=valid_from)
    return nodes, list(parser._calls)


def _edges_from(
    nodes: list[CodeNode], calls: list[tuple[str, str, int, str]]
) -> list[Edge]:
    """Build hierarchy + call edges from aggregated parse results."""
    helper = get_parser_for_path(Path("dummy.py"))
    if helper is None:
        return []
    helper._calls = calls
    return helper.extract_edges(nodes)


def parse_files_parallel(
    items: list[tuple[str, str]],
    *,
    commit_sha: str = "",
    valid_from: datetime | None = None,
    jobs: int = 0,
) -> tuple[list[CodeNode], list[Edge]]:
    """Parse many (rel_path, text) pairs, optionally in parallel.

    Args:
        items: File payloads to parse.
        commit_sha: Commit stamp for node uids.
        valid_from: Validity start for produced nodes.
        jobs: Worker count; 0 means CPU count - 1.

    Returns:
        Aggregated nodes and edges.
    """
    if not items:
        return [], []
    workers = jobs if jobs > 0 else max(1, (__import__("os").cpu_count() or 2) - 1)
    vf = valid_from.isoformat() if valid_from else ""
    payloads = [
        (rel, text, commit_sha, vf) for rel, text in items if is_supported_source(Path(rel))
    ]
    if not payloads:
        return [], []

    nodes: list[CodeNode] = []
    calls: list[tuple[str, str, int, str]] = []

    if workers == 1 or len(payloads) < 4:
        for payload in payloads:
            n, c = _parse_one(payload)
            nodes.extend(n)
            calls.extend(c)
    else:
        payloads.sort(key=lambda p: len(p[1]), reverse=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_parse_one, payload) for payload in payloads]
            for fut in as_completed(futures):
                try:
                    n, c = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Parallel parse failed: %s", exc)
                    continue
                nodes.extend(n)
                calls.extend(c)

    return nodes, _edges_from(nodes, calls)
