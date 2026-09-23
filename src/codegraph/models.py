"""Core data models and bundled sample decisions for CodeGraph.

Structure comes from tree-sitter; decisions may come from git/ADR extraction
or bundled samples when no repository decisions exist yet.
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

    def matches_location(self, file_path: str, line: int) -> bool:
        """Return True when this decision is bound to a file:line."""
        return self.file_path == file_path and self.line == line


def normalize_location_path(raw: str) -> str:
    """Normalize a user path to forward slashes for matching."""
    return raw.strip().replace("\\", "/").lstrip("./")


def make_uid(file_path: str, kind: str, name: str, line_start: int, commit_sha: str = "") -> str:
    """Build a stable node uid, optionally versioned by commit."""
    path = normalize_location_path(file_path)
    base = f"{path}::{kind}::{name}@{line_start}"
    if commit_sha:
        return f"{base}::{commit_sha[:12]}"
    return base


# Sample decisions matched by exact file:line (fallback demo data)
SAMPLE_DECISIONS: list[Decision] = [
    Decision(
        uid="dec-001",
        content="Session tokens use stateful JWT with a server-side denylist",
        reason=(
            "Login sessions must support sign-out everywhere immediately. "
            "Pure stateless JWT cannot revoke instantly, while a full server session "
            "forces every gateway hop to hit the DB. Compromise: JWT carries jti and "
            "the gateway caches a denylist."
        ),
        alternatives=[
            "Pure stateless JWT (rejected: cannot kick sessions immediately)",
            "Full server-side session (rejected: gateway DB cost)",
        ],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.PR,
        source_ref="PR #48 · Issue #31 · ADR-003",
        timestamp=datetime(2024, 11, 2, 15, 30, 0),
        author="chen@example.com",
        file_path="src/auth/session.ts",
        line=42,
        constraints=[
            "Keep compatibility with legacy mobile client headers",
            "Auth P99 latency < 5ms",
            "Key rotation must not drop active sessions",
        ],
        confidence=0.92,
    ),
    Decision(
        uid="dec-002",
        content="bcrypt cost factor fixed at 12",
        reason=(
            "On current CI machines and login QPS, 12 rounds take about 80ms — "
            "enough for brute-force resistance without making login feel slow."
        ),
        alternatives=[
            "Argon2id (rejected: hash migration cost)",
            "PBKDF2 (rejected: weaker library conventions)",
        ],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.ADR,
        source_ref="ADR-003",
        timestamp=datetime(2024, 11, 2, 16, 10, 0),
        author="security@example.com",
        file_path="src/auth/password.ts",
        line=18,
        constraints=[
            "Stay compatible with existing User.password_hash format",
            "Login P95 < 150ms",
        ],
        confidence=0.88,
    ),
    Decision(
        uid="dec-003",
        content="Cache keys always carry a tenant prefix",
        reason=(
            "A multi-tenant deploy once produced cross-tenant dirty reads. "
            "All Redis keys must start with tenant:{id}: and the write path enforces it."
        ),
        alternatives=["Prefix only in business code (rejected: easy to forget)"],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.ISSUE,
        source_ref="Issue #77",
        timestamp=datetime(2025, 1, 18, 10, 0, 0),
        author="ops@example.com",
        file_path="src/cache/keys.ts",
        line=7,
        constraints=["Bare keys are forbidden", "Dual-write old keys for 7 days in gray release"],
        confidence=0.95,
    ),
    Decision(
        uid="dec-004",
        content="Pagination uses a (created_at, id) cursor instead of offset",
        reason=(
            "Deep offset pagination on the order list degraded P99 to 2s past 100k rows; "
            "cursor pagination stays around 40ms."
        ),
        alternatives=["offset/limit (rejected: unstable deep pages)"],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT,
        source_ref="commit b4c12aa",
        timestamp=datetime(2025, 3, 4, 9, 20, 0),
        author="backend@example.com",
        file_path="src/api/orders.ts",
        line=63,
        constraints=["Keep the load-more UX unchanged on the frontend"],
        confidence=0.84,
    ),
    Decision(
        uid="dec-005",
        content="Retire the V1 dual-write protocol",
        reason=(
            "V1 dual-write had no traffic after gray release ended; keeping it "
            "raised schema compatibility cost with no benefit."
        ),
        alternatives=["Keep dual-write forever (rejected: maintenance cost)"],
        status=DecisionStatus.SUPERSEDED,
        source=DecisionSource.PR,
        source_ref="PR #120 (supersedes ADR-001 dual-write)",
        timestamp=datetime(2025, 5, 9, 14, 0, 0),
        author="arch@example.com",
        file_path="src/api/orders.ts",
        line=63,
        constraints=["Confirm zero V1 write traffic in monitoring before removal"],
        confidence=0.75,
    ),
]


def find_decisions_for_location(file_path: str, line: int) -> list[Decision]:
    """Return sample decisions bound to a file:line."""
    return [d for d in SAMPLE_DECISIONS if d.matches_location(file_path, line)]


def find_decisions_for_file(file_path: str) -> list[Decision]:
    """Return sample decisions bound to a file (or path prefix)."""
    prefix = normalize_location_path(file_path)
    matched = [
        d for d in SAMPLE_DECISIONS if d.file_path == prefix or d.file_path.startswith(prefix)
    ]
    return sorted(matched, key=lambda d: d.timestamp)
