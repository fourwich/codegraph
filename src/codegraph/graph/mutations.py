"""Builders that turn pydantic models into Dgraph mutation JSON."""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.models import CodeNode, Decision, Edge

# Map Edge.kind to Dgraph predicate names.
EDGE_PREDICATES = {
    "uses": "uses",
    "defined_by": "defined_by",
    "contains": "contains",
}


def _now_iso() -> str:
    """Return current UTC timestamp in ISO-8601."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_node_json(node: CodeNode) -> dict:
    """Convert a CodeNode into Dgraph mutation JSON.

    Args:
        node: Parsed code node.

    Returns:
        JSON object describing one CodeNode set block.
    """
    return {
        "node_uid": node.uid,
        "kind": node.kind,
        "name": node.name,
        "file_path": node.file_path,
        "line_start": int(node.line_start),
        "line_end": int(node.line_end),
        "language": node.language,
        "valid_from": _now_iso(),
        "commit_sha": node.commit_sha or "",
        "parent_uid": node.parent_uid or "",
    }


def build_edge_json(edge: Edge, from_uid: str, to_uid: str) -> dict:
    """Convert an Edge into Dgraph mutation JSON.

    Args:
        edge: Relationship edge.
        from_uid: Business uid of the source node.
        to_uid: Business uid of the target node.

    Returns:
        JSON object describing one edge mutation.
    """
    predicate = EDGE_PREDICATES.get(edge.kind, "uses")
    return {
        "from_uid": from_uid,
        "to_uid": to_uid,
        "predicate": predicate,
        "file_path": edge.file_path,
        "line": int(edge.line),
    }


def build_decision_json(decision: Decision, target_uid: str | None) -> dict:
    """Convert a Decision into Dgraph mutation JSON.

    Args:
        decision: Decision record.
        target_uid: Business uid of the CodeNode this decision justifies.

    Returns:
        JSON object describing one Decision set block.
    """
    payload = {
        "decision_uid": decision.uid,
        "content": decision.content,
        "reason": decision.reason or "",
        "alternatives": list(decision.alternatives),
        "status": decision.status.value,
        "source": decision.source.value,
        "source_ref": decision.source_ref or "",
        "timestamp": decision.timestamp.replace(microsecond=0).isoformat(),
        "author": decision.author or "",
        "constraints": list(decision.constraints),
        "confidence": float(decision.confidence),
    }
    if target_uid:
        payload["justifies_uid"] = target_uid
    return payload
