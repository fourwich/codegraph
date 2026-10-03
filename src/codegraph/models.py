"""Core data models for CodeGraph.

Structure comes from tree-sitter; decisions come from Git history, ADRs and
CHANGELOG files. Nothing is fabricated: if a repository records no rationale,
CodeGraph reports that instead of inventing a decision.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DecisionStatus(str, Enum):
    """Lifecycle state of a decision."""

    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class DecisionSource(str, Enum):
    """Where a decision came from."""

    PR = "pr"
    ISSUE = "issue"
    ADR = "adr"
    COMMIT = "commit"
    COMMENT = "comment"


class DecisionTier(str, Enum):
    """How much of a decision a record actually is.

    Only ``DECISION`` records carry a rationale (a reason clause or a rejected
    alternative) and are shown by default. ``EVENT`` records are plain history —
    a commit subject, a changelog line — useful as context, never as an answer.
    """

    DECISION = "decision"
    EVENT = "event"


class CodeNode(BaseModel):
    """A code structure node: function, class, variable, or file."""

    uid: str = Field(description="Stable identifier including commit when versioned")
    kind: str = Field(description="function / class / variable / file / module")
    name: str = Field(description="Symbol name")
    file_path: str = Field(description="Path relative to the repo root")
    line_start: int = Field(ge=1, description="Start line")
    line_end: int = Field(ge=1, description="End line")
    language: str = Field(description="Source language")
    commit_sha: str = Field(default="", description="Commit that introduced the node")
    parent_uid: str | None = Field(default=None, description="Parent node uid; None if top-level")
    valid_from: datetime = Field(
        default_factory=lambda: datetime.fromtimestamp(0),
        description="When this node version became valid",
    )
    valid_to: datetime | None = Field(
        default=None,
        description="When this version stopped being valid; None means current",
    )

    def contains_line(self, line: int) -> bool:
        """Return True when line falls inside this node (inclusive)."""
        return self.line_start <= line <= self.line_end


class Edge(BaseModel):
    """A relationship between code nodes."""

    from_uid: str = Field(description="Source node uid")
    to_uid: str = Field(description="Target node uid")
    kind: str = Field(description="uses / defined_by / contains")
    file_path: str = Field(default="", description="File where the edge appears")
    line: int = Field(default=1, ge=1, description="Line where the edge appears")


class Decision(BaseModel):
    """A design decision: why code is written this way."""

    uid: str = Field(description="Stable identifier")
    content: str = Field(description="Decision summary")
    reason: str = Field(default="", description="Why")
    alternatives: list[str] = Field(default_factory=list, description="Rejected options")
    status: DecisionStatus = Field(default=DecisionStatus.ACCEPTED)
    source: DecisionSource = Field(default=DecisionSource.ADR)
    source_ref: str = Field(default="", description="Source reference, e.g. PR #48")
    timestamp: datetime = Field(description="Decision time")
    author: str = Field(default="", description="Author")
    file_path: str = Field(default="", description="Linked code location")
    line: int | None = Field(default=None, description="Linked line number")
    constraints: list[str] = Field(default_factory=list, description="Related constraints")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence 0-1")
    category: str = Field(default="design", description="design | dependency")
    tier: DecisionTier = Field(
        default=DecisionTier.DECISION,
        description="decision (has a rationale) | event (plain history)",
    )

    def matches_location(self, file_path: str, line: int) -> bool:
        """Return True when this decision is bound to a file:line."""
        return self.file_path == file_path and self.line == line

    def has_rationale(self) -> bool:
        """True when the record states a reason or a rejected alternative."""
        return bool((self.reason or "").strip()) or bool(self.alternatives)


def normalize_location_path(raw: str) -> str:
    """Normalize a user path to forward slashes for matching."""
    return raw.strip().replace("\\", "/").lstrip("./")


def select_decisions(
    decisions: list[Decision],
    *,
    include_events: bool = False,
    include_dependency: bool = False,
) -> list[Decision]:
    """Return the records a default query should show.

    Args:
        decisions: Candidate records.
        include_events: Also return event-tier records (plain history).
        include_dependency: Also return dependency-category decisions.

    Returns:
        Decision-tier, non-dependency records by default.
    """
    out: list[Decision] = []
    for decision in decisions:
        if decision.tier is not DecisionTier.DECISION:
            if include_events:
                out.append(decision)
            continue
        if decision.category == "dependency" and not include_dependency:
            continue
        out.append(decision)
    return out


def make_uid(file_path: str, kind: str, name: str, line_start: int, commit_sha: str = "") -> str:
    """Build a stable node uid, optionally versioned by commit."""
    path = normalize_location_path(file_path)
    base = f"{path}::{kind}::{name}@{line_start}"
    if commit_sha:
        return f"{base}::{commit_sha[:12]}"
    return base


class DecisionChange(BaseModel):
    """A decision delta between two snapshots."""

    kind: str = Field(description="added / removed / changed / superseded")
    decision: Decision
    old_status: str | None = Field(default=None)
    new_status: str | None = Field(default=None)

class Conflict(BaseModel):
    """A detected contradiction between two decisions."""

    type: str = Field(description="opposite / supersede / temporal")
    decision_a: Decision
    decision_b: Decision
    location: str = Field(default="")
    matched_words: list[str] = Field(default_factory=list)
    explanation: str = Field(default="")
    confidence: float = Field(default=1.0)
