"""Rule-based decision extraction (no LLM)."""

from __future__ import annotations

import re
from datetime import datetime

from codegraph.models import Decision, DecisionSource, DecisionStatus, make_uid

# Keywords that signal a design rationale in prose
DECISION_KEYWORDS: tuple[str, ...] = (
    "because",
    "since",
    "reason",
    "avoid",
    "tradeoff",
    "trade-off",
    "instead of",
    "chose",
    "decided",
    "so that",
    "in order to",
    "rather than",
)

CONVENTIONAL_COMMIT = re.compile(
    r"^(?P<type>feat|fix|refactor|perf|docs|ci|chore|test)(\([^)]+\))?:\s*(?P<subject>.+)$",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_\-]*")


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-like fragments."""
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()]
    return parts


def looks_like_decision(sentence: str) -> bool:
    """Return True when a sentence contains decision rationale keywords."""
    lower = sentence.lower()
    return any(k in lower for k in DECISION_KEYWORDS)


def split_content_reason(sentence: str) -> tuple[str, str]:
    """Split a rationale sentence into (content, reason).

    Uses because/since/so that/in order to as the reason delimiter.
    """
    text = " ".join(sentence.strip().split())
    lower = text.lower()
    for marker in (" because ", " since ", " so that ", " in order to ", " rather than "):
        idx = lower.find(marker)
        if idx > 0:
            left = text[:idx].strip().rstrip(",;:")
            right = text[idx:].strip()
            if left:
                return left[:220], right[:500]
    return text[:220], ""


def decision_from_sentence(
    sentence: str,
    *,
    source: DecisionSource,
    source_ref: str,
    timestamp: datetime,
    author: str = "",
    file_path: str = "",
    line: int | None = None,
    uid_prefix: str = "dec",
) -> Decision:
    """Build a Decision from one rationale sentence."""
    content, reason = split_content_reason(sentence)
    if len(content) > 220:
        content = content[:217] + "..."
    uid = make_uid(file_path or source_ref, "decision", uid_prefix, max(line or 1, 1))
    # Keep uid unique enough for multi-source extraction
    uid = f"{uid}::{hash(content) & 0xFFFF:04x}"
    return Decision(
        uid=uid,
        content=content,
        reason=reason,
        alternatives=[],
        status=DecisionStatus.ACCEPTED,
        source=source,
        source_ref=source_ref,
        timestamp=timestamp,
        author=author,
        file_path=file_path,
        line=line,
        constraints=[],
        confidence=0.55,
    )


def decision_from_commit_subject(
    message: str,
    *,
    source_ref: str,
    timestamp: datetime,
    author: str = "",
    file_path: str = "",
) -> Decision | None:
    """Build a weak Decision from a conventional commit subject line."""
    first = (message or "").strip().splitlines()[0] if (message or "").strip() else ""
    match = CONVENTIONAL_COMMIT.match(first)
    if not match:
        return None
    subject = match.group("subject").strip()
    if not subject:
        return None
    return decision_from_sentence(
        subject,
        source=DecisionSource.COMMIT,
        source_ref=source_ref,
        timestamp=timestamp,
        author=author,
        file_path=file_path,
        uid_prefix="commit-subject",
    )


def extract_decisions_from_text(
    text: str,
    *,
    source: DecisionSource,
    source_ref: str,
    timestamp: datetime,
    author: str = "",
    file_path: str = "",
) -> list[Decision]:
    """Extract decision-like sentences from free text."""
    found: list[Decision] = []
    for sentence in split_sentences(text):
        if not looks_like_decision(sentence):
            continue
        found.append(
            decision_from_sentence(
                sentence,
                source=source,
                source_ref=source_ref,
                timestamp=timestamp,
                author=author,
                file_path=file_path,
                uid_prefix=source.value,
            )
        )
    return found


def parse_adr_markdown(text: str) -> dict[str, str]:
    """Parse a simple ADR markdown file into sections."""
    sections: dict[str, str] = {}
    current = "title"
    buf: list[str] = []
    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.*)$", line.strip())
        if heading:
            if buf:
                sections[current] = "\n".join(buf).strip()
                buf = []
            title = heading.group(1).strip().lower()
            current = _normalize_heading(title)
            continue
        buf.append(line)
    if buf:
        sections[current] = "\n".join(buf).strip()
    return sections


def _normalize_heading(title: str) -> str:
    """Map ADR heading variants to canonical keys."""
    if "status" in title:
        return "status"
    if "context" in title:
        return "context"
    if "decision" in title or "chosen" in title:
        return "decision"
    if "consequence" in title:
        return "consequences"
    if "alternative" in title or "option" in title:
        return "alternatives"
    if "title" in title or title.startswith("adr"):
        return "title"
    return title or "body"


def decision_from_adr_sections(
    sections: dict[str, str],
    *,
    source_ref: str,
    timestamp: datetime,
    file_path: str,
) -> Decision | None:
    """Build one Decision from parsed ADR sections."""
    content = sections.get("decision") or sections.get("title") or ""
    if not content.strip():
        return None
    content = split_sentences(content)[0][:220]
    status_raw = (sections.get("status") or "accepted").strip().lower()
    status = DecisionStatus.ACCEPTED
    if "reject" in status_raw:
        status = DecisionStatus.REJECTED
    elif "super" in status_raw or "replac" in status_raw:
        status = DecisionStatus.SUPERSEDED

    alternatives: list[str] = []
    alt_text = sections.get("alternatives") or ""
    for sentence in split_sentences(alt_text)[:5]:
        alternatives.append(sentence[:180])

    constraints: list[str] = []
    for sentence in split_sentences(sections.get("consequences") or "")[:5]:
        constraints.append(sentence[:180])

    uid = make_uid(file_path, "decision", "adr", 1)
    return Decision(
        uid=uid,
        content=content,
        reason=(sections.get("context") or sections.get("decision") or "")[:500],
        alternatives=alternatives,
        status=status,
        source=DecisionSource.ADR,
        source_ref=source_ref,
        timestamp=timestamp,
        author="",
        file_path=file_path,
        line=None,
        constraints=constraints,
        confidence=0.8,
    )
