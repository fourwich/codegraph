"""Dgraph client wrapper with parameterized queries."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from pydgraph import DgraphClient as PyDgraphClient
from pydgraph import DgraphClientStub, Operation

from codegraph.graph.mutations import build_decision_json, build_edge_json, build_node_json
from codegraph.graph.schema import get_schema
from codegraph.models import CodeNode, Decision, Edge

logger = logging.getLogger(__name__)
load_dotenv()

Q_NODE_AT = """
query node_at($path: string, $line: int) {
  nodes(func: eq(file_path, $path))
    @filter(le(line_start, $line) AND ge(line_end, $line)) {
    uid
    node_uid
    kind
    name
    file_path
    line_start
    line_end
    language
    parent_uid
  }
}
"""

# Decisions that justify a node at file:line (reverse edge lookup).
Q_DECISIONS_FOR = """
query decisions_for($path: string, $line: int) {
  nodes(func: eq(file_path, $path))
    @filter(le(line_start, $line) AND ge(line_end, $line)) {
    uid
    node_uid
    ~justifies {
      uid
      content
      reason
      alternatives
      status
      source
      source_ref
      timestamp
      author
      constraints
      confidence
    }
  }
}
"""

Q_GRAPH_AT = """
query graph_at($when: string, $scope: string) {
  nodes(func: has(valid_from))
    @filter(
      le(valid_from, $when)
      AND (NOT has(valid_to) OR ge(valid_to, $when))
    ) {
    uid
    node_uid
    kind
    name
    file_path
    line_start
    line_end
    valid_from
    valid_to
  }
}
"""

Q_COUNT_USES = "query { q(func: has(uses)) { count(uid) } }"
Q_COUNT_DECISIONS = "query { q(func: has(content)) { count(uid) } }"

Q_FIND_NODE = "query { q as var(func: eq(node_uid, $key)) }"
Q_FIND_DECISION = "query { q as var(func: eq(decision_uid, $key)) }"
Q_LINK_EDGE = (
    "query { a as var(func: eq(node_uid, $from_uid)) "
    "b as var(func: eq(node_uid, $to_uid)) }"
)
Q_LINK_JUSTIFIES = (
    "query { d as var(func: eq(decision_uid, $du)) "
    "t as var(func: eq(node_uid, $tu)) }"
)


class DgraphConnectionError(Exception):
    """Raised when Dgraph is unreachable or rejects a request."""


class DgraphClient:
    """Thin wrapper around pydgraph for CodeNode / Edge / Decision."""

    def __init__(self, alpha: str | None = None) -> None:
        """Open a connection to Dgraph alpha.

        Args:
            alpha: host:port of alpha. Defaults to $DGRAPH_ALPHA or localhost:9080.
        """
        self._alpha = alpha or os.environ.get("DGRAPH_ALPHA", "localhost:9080")
        try:
            self._stub = DgraphClientStub(self._alpha)
            self._client = PyDgraphClient(self._stub)
        except Exception as exc:  # noqa: BLE001
            raise DgraphConnectionError(
                f"Cannot connect to Dgraph ({self._alpha}): {exc}"
            ) from exc

    def ping(self) -> bool:
        """Return True when Dgraph answers a trivial alter."""
        try:
            self._client.alter(Operation())
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Dgraph ping failed: %s", exc)
            return False

    def init_schema(self) -> None:
        """Apply schema to the cluster."""
        try:
            self._client.alter(Operation(schema=get_schema()))
        except Exception as exc:  # noqa: BLE001
            raise DgraphConnectionError(f"Failed to apply schema: {exc}") from exc

    def drop_all(self) -> None:
        """Drop all data and schema."""
        try:
            self._client.alter(Operation(drop_all=True))
        except Exception as exc:  # noqa: BLE001
            raise DgraphConnectionError(f"drop_all failed: {exc}") from exc

    def upsert_node(self, node: CodeNode) -> None:
        """Insert or update one CodeNode keyed by node_uid."""
        payload = build_node_json(node)
        key = payload["node_uid"]
        set_json = json.dumps([{"uid": "uid(q)", **payload}]).encode("utf-8")
        blank_json = json.dumps([{"uid": f"_:{key}", **payload}]).encode("utf-8")
        self._upsert(
            query=Q_FIND_NODE,
            vars_={"$key": key},
            insert_if_missing=(set_json, blank_json),
            insert_always=None,
        )

    def upsert_edge(self, edge: Edge) -> None:
        """Link two existing nodes with a typed edge."""
        payload = build_edge_json(edge, edge.from_uid, edge.to_uid)
        predicate = payload["predicate"]
        set_json = json.dumps(
            [{"uid": "uid(a)", predicate: [{"uid": "uid(b)"}]}]
        ).encode("utf-8")
        self._upsert(
            query=Q_LINK_EDGE,
            vars_={"$from_uid": edge.from_uid, "$to_uid": edge.to_uid},
            insert_if_missing=None,
            insert_always=set_json,
        )

    def upsert_decision(self, decision: Decision) -> None:
        """Insert or update one Decision and optional justifies edge."""
        target_uid = None
        if decision.file_path and decision.line is not None:
            target_uid = self._find_node_uid(decision.file_path, decision.line)
        payload = build_decision_json(decision, target_uid)
        payload.pop("justifies_uid", None)
        key = payload["decision_uid"]
        set_json = json.dumps([{"uid": "uid(q)", **payload}]).encode("utf-8")
        blank_json = json.dumps([{"uid": f"_:{key}", **payload}]).encode("utf-8")
        self._upsert(
            query=Q_FIND_DECISION,
            vars_={"$key": key},
            insert_if_missing=(set_json, blank_json),
            insert_always=None,
        )
        if target_uid:
            self._link_decision(key, target_uid)

    def query_node_at(self, file_path: str, line: int) -> dict[str, Any] | None:
        """Return the innermost CodeNode covering file:line."""
        result = self._query(Q_NODE_AT, {"$path": file_path, "$line": str(line)})
        nodes = result.get("nodes") or []
        if not nodes:
            return None
        nodes.sort(key=lambda n: int(n.get("line_end") or 0) - int(n.get("line_start") or 0))
        return nodes[0]

    def query_decisions_for(self, file_path: str, line: int) -> list[dict[str, Any]]:
        """Return decisions linked to the code at file:line."""
        result = self._query(Q_DECISIONS_FOR, {"$path": file_path, "$line": str(line)})
        found: list[dict[str, Any]] = []
        for node in result.get("nodes") or []:
            for decision in node.get("~justifies") or []:
                found.append(decision)
        return found

    def query_graph_at(self, at_date: str, scope: str) -> dict[str, Any]:
        """Return graph snapshot valid at at_date, filtered by file_path scope."""
        result = self._query(Q_GRAPH_AT, {"$when": at_date, "$scope": scope})
        nodes = result.get("nodes") or []
        if scope and scope not in {".", ""}:
            prefix = scope.replace("\\", "/").rstrip("/")
            nodes = [n for n in nodes if str(n.get("file_path", "")).startswith(prefix)]
        return {
            "nodes": nodes,
            "edge_count": self._count_uses(),
            "decision_count": self._count_decisions(),
        }

    def close(self) -> None:
        """Close the gRPC stub."""
        try:
            self._stub.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Error closing Dgraph stub: %s", exc)

    def _upsert(
        self,
        query: str,
        vars_: dict[str, str],
        insert_if_missing: tuple[bytes, bytes] | None,
        insert_always: bytes | None,
    ) -> None:
        """Run one upsert request (query + mutations)."""
        txn = self._client.txn()
        try:
            mutations = []
            if insert_if_missing is not None:
                update_json, create_json = insert_if_missing
                mutations.append(
                    txn.create_mutation(set_json=update_json, cond="@if(eq(len(q), 1))")
                )
                mutations.append(
                    txn.create_mutation(set_json=create_json, cond="@if(eq(len(q), 0))")
                )
            if insert_always is not None:
                mutations.append(txn.create_mutation(set_json=insert_always))
            request = txn.create_request(query=query, vars=vars_, mutations=mutations, commit_now=True)
            txn.do_request(request)
        except Exception as exc:  # noqa: BLE001
            raise DgraphConnectionError(f"Dgraph upsert failed: {exc}") from exc
        finally:
            txn.discard()

    def _query(self, query: str, vars_: dict[str, str]) -> dict[str, Any]:
        """Run a parameterized query and return JSON dict."""
        txn = self._client.txn()
        try:
            res = txn.query(query, vars=vars_)
            return res.json or {}
        except Exception as exc:  # noqa: BLE001
            raise DgraphConnectionError(f"Dgraph query failed: {exc}") from exc
        finally:
            txn.discard()

    def _find_node_uid(self, file_path: str, line: int) -> str | None:
        """Resolve business node uid covering the location."""
        node = self.query_node_at(file_path, line)
        return node.get("node_uid") if node else None

    def _link_decision(self, decision_uid: str, target_uid: str) -> None:
        """Create justifies edge from Decision to CodeNode."""
        set_json = json.dumps(
            [{"uid": "uid(d)", "justifies": [{"uid": "uid(t)"}]}]
        ).encode("utf-8")
        self._upsert(
            query=Q_LINK_JUSTIFIES,
            vars_={"$du": decision_uid, "$tu": target_uid},
            insert_if_missing=None,
            insert_always=set_json,
        )

    def _count_uses(self) -> int:
        """Count nodes that have outgoing uses edges."""
        res = self._query(Q_COUNT_USES, {})
        blocks = res.get("q") or []
        return int(blocks[0].get("count") or 0) if blocks else 0

    def _count_decisions(self) -> int:
        """Count Decision-like nodes by content predicate."""
        res = self._query(Q_COUNT_DECISIONS, {})
        blocks = res.get("q") or []
        return int(blocks[0].get("count") or 0) if blocks else 0
