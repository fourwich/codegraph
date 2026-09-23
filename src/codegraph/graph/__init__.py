"""Dgraph backend package."""

from codegraph.graph.client import DgraphClient, DgraphConnectionError

__all__ = ["DgraphClient", "DgraphConnectionError"]
