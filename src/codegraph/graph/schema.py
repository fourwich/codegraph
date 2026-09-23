"""Dgraph DQL schema for CodeNode and Decision types."""

from __future__ import annotations

SCHEMA = """
node_uid: string @index(exact) .
kind: string @index(exact) .
name: string @index(term) .
file_path: string @index(exact) .
line_start: int .
line_end: int .
language: string .
valid_from: datetime @index(hour) .
valid_to: datetime @index(hour) .
commit_sha: string .
parent_uid: string .
uses: [uid] @reverse .
defined_by: [uid] @reverse .
contains: [uid] @reverse .
decided_by: [uid] @reverse .

type CodeNode {
  node_uid
  kind
  name
  file_path
  line_start
  line_end
  language
  valid_from
  valid_to
  commit_sha
  parent_uid
  uses
  defined_by
  contains
  decided_by
}

decision_uid: string @index(exact) .
content: string @index(fulltext) .
reason: string .
alternatives: [string] .
status: string @index(exact) .
source: string @index(exact) .
source_ref: string .
timestamp: datetime @index(hour) .
author: string .
constraints: [string] .
confidence: float .
justifies: [uid] @reverse .
supersedes: [uid] @reverse .

type Decision {
  decision_uid
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
  justifies
  supersedes
}
"""

DROP_ALL_QUERY = "drop {}"


def get_schema() -> str:
    """Return the Dgraph schema string for alter()."""
    return SCHEMA


def get_drop_all_query() -> str:
    """Return the Dgraph drop-all payload."""
    return DROP_ALL_QUERY
