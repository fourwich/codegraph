"""Rule-based decision extraction (no LLM)."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime

from codegraph.models import (
    Decision,
    DecisionSource,
    DecisionStatus,
    DecisionTier,
    make_uid,
)

# Keywords that signal a design rationale in prose. Deliberately narrow: a word
# like "since"/"must be"/"to support" matches ordinary English and used to turn
# release notes into "decisions".
DECISION_KEYWORDS: tuple[str, ...] = (
    "because",
    "tradeoff",
    "trade-off",
    "instead of",
    "rather than",
    "chose",
    "we chose",
    "we picked",
    "we decided",
    "decided",
    "so that",
    "in order to",
    "switched to",
    "migrated to",
    "for performance",
    "for security",
    "for simplicity",
    "for compatibility",
    "for reliability",
    "this avoids",
    "this prevents",
    "avoids",
    "prevents",
    "due to",
    "because of",
    "as a result of",
    "opted for",
    "in favor of",
    "to reduce",
    "to avoid",
    "to prevent",
    "to simplify",
    "to fix",
    "to resolve",
    "resolves",
)

# Clause markers that introduce the *reason* half of a decision.
_REASON_MARKERS: tuple[str, ...] = (
    " because ",
    " so that ",
    " in order to ",
    " due to ",
    " because of ",
    " as a result of ",
    " to fix ",
    " to avoid ",
    " to prevent ",
    " to reduce ",
    " to simplify ",
    " for performance ",
    " for security ",
    " for simplicity ",
    " for compatibility ",
    " for reliability ",
)

# Clause markers that introduce a *rejected alternative*.
_ALT_MARKERS: tuple[str, ...] = (
    " instead of ",
    " rather than ",
    " in favor of ",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_BULLET_PREFIX = re.compile(r"^\s*[-*+]\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_\-]*")

CONVENTIONAL_COMMIT = re.compile(
    r"^(?P<type>feat|fix|refactor|perf|docs|ci|chore|test|build)(\([^)]+\))?:\s*(?P<subject>.+)$",
    re.IGNORECASE,
)

BULLET_RE = re.compile(r"^\s*[-*+]\s+(?P<text>.+)$", re.MULTILINE)


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-like fragments, dropping list markers."""
    parts = [_BULLET_PREFIX.sub("", p).strip() for p in _SENTENCE_SPLIT.split(text)]
    return [p for p in parts if p]


def split_commit_parts(message: str) -> tuple[str, list[str]]:
    """Split a commit message into (subject, body_bullets_or_paragraphs)."""
    lines = (message or "").splitlines()
    subject = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]).strip()
    bullets = [m.group("text").strip() for m in BULLET_RE.finditer(body) if m.group("text").strip()]
    if bullets:
        return subject, bullets
    if body:
        return subject, [p for p in split_sentences(body) if p]
    return subject, []


def looks_like_decision(sentence: str) -> bool:
    """Return True when a sentence contains decision rationale keywords."""
    lower = sentence.lower()
    return any(k in lower for k in DECISION_KEYWORDS)


def split_content_reason(sentence: str) -> tuple[str, str]:
    """Split a rationale sentence into (content, reason)."""
    text = " ".join(sentence.strip().split())
    lower = text.lower()
    for marker in _REASON_MARKERS:
        idx = lower.find(marker)
        if idx > 0:
            left = text[:idx].strip().rstrip(",;:")
            right = text[idx:].strip()
            if left:
                return left[:220], right[:500]
    return text[:220], ""


def split_decision_parts(sentence: str) -> tuple[str, str, list[str]]:
    """Split one sentence into (content, reason, alternatives).

    "use node:buffer instead of safe-buffer" yields content "use node:buffer"
    and alternatives ["safe-buffer"]; a "because ..." clause becomes the reason.
    A clause is only read as an alternative when the sentence looks complete —
    a fragment cut mid-phrase ("... upsert instead of calling") would otherwise
    produce a meaningless alternative.
    """
    text = " ".join((sentence or "").strip().split())
    alternatives: list[str] = []
    complete = text.endswith((".", ")", "`", "!", "?"))
    lower = text.lower()
    for marker in _ALT_MARKERS:
        idx = lower.find(marker)
        if idx > 0 and complete:
            alternative = text[idx + len(marker) :].strip().rstrip(".")
            if len(alternative.split()) >= 1:
                alternatives.append(alternative[:180])
            text = text[:idx].strip().rstrip(",;:")
            break
    content, reason = split_content_reason(text)
    return content, reason, alternatives


def classify_tier(content: str, reason: str, alternatives: list[str]) -> DecisionTier:
    """A record is a decision only when it states why or what it rejected."""
    if (reason or "").strip() or alternatives:
        return DecisionTier.DECISION
    return DecisionTier.EVENT


def content_fingerprint(text: str) -> str:
    """Return a stable 8-hex-char fingerprint of decision content.

    `hash()` is salted per process, so it cannot be used in a persisted uid;
    blake2b gives the same value in every process and on every machine.
    """
    normalized = " ".join((text or "").split()).lower()
    return hashlib.blake2b(normalized.encode("utf-8"), digest_size=4).hexdigest()


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
    confidence: float = 0.55,
    category: str = "design",
    tier: DecisionTier | None = None,
) -> Decision:
    """Build a Decision from one sentence.

    Args:
        tier: Force a tier; when omitted it is derived from the sentence
            (reason or rejected alternative => decision, otherwise event).
    """
    content, reason, alternatives = split_decision_parts(sentence)
    if len(content) > 220:
        content = content[:217] + "..."
    uid = make_uid(file_path or source_ref, "decision", uid_prefix, max(line or 1, 1))
    uid = f"{uid}::{content_fingerprint(content)}"
    return Decision(
        uid=uid,
        content=content,
        reason=reason,
        alternatives=alternatives,
        status=DecisionStatus.ACCEPTED,
        source=source,
        source_ref=source_ref,
        timestamp=timestamp,
        author=author,
        file_path=file_path,
        line=line,
        constraints=[],
        confidence=confidence,
        category=category,
        tier=tier or classify_tier(content, reason, alternatives),
    )


def decision_from_commit_subject(
    message: str,
    *,
    source_ref: str,
    timestamp: datetime,
    author: str = "",
    file_path: str = "",
) -> Decision | None:
    """Build one record from a commit subject line.

    Every commit subject becomes a record. It is a *decision* only when the
    subject itself states a reason or a rejected alternative — or when it is a
    dependency bump that says why (for example "to fix CVE-2026-12590").
    """
    subject, _body = split_commit_parts(message)
    if not subject:
        return None
    match = CONVENTIONAL_COMMIT.match(subject)
    subject_text = match.group("subject").strip() if match else subject.strip()
    if not subject_text:
        return None

    dep = is_dependency_commit(subject) or is_dependency_commit(subject_text)
    content, reason, alternatives = split_decision_parts(subject_text)
    tier = classify_tier(content, reason, alternatives)
    if tier is DecisionTier.DECISION:
        confidence = 0.65 if dep else 0.6
    else:
        confidence = 0.5
    return decision_from_sentence(
        subject_text,
        source=DecisionSource.COMMIT,
        source_ref=source_ref,
        timestamp=timestamp,
        author=author,
        file_path=file_path,
        uid_prefix="commit-subject",
        confidence=confidence,
        category="dependency" if dep else "design",
        tier=tier,
    )


def decisions_from_commit_body(
    message: str,
    *,
    source_ref: str,
    timestamp: datetime,
    author: str = "",
    file_path: str = "",
) -> list[Decision]:
    """Extract records from commit body bullets / paragraphs.

    A bullet becomes a decision only when it carries a reason or a rejected
    alternative; otherwise it is kept as a low-confidence event.
    """
    _subject, parts = split_commit_parts(message)
    out: list[Decision] = []
    for part in parts:
        if not looks_like_decision(part):
            continue
        content, reason, alternatives = split_decision_parts(part)
        tier = classify_tier(content, reason, alternatives)
        out.append(
            decision_from_sentence(
                part,
                source=DecisionSource.COMMIT,
                source_ref=source_ref,
                timestamp=timestamp,
                author=author,
                file_path=file_path,
                uid_prefix="commit-body",
                confidence=0.7 if tier is DecisionTier.DECISION else 0.55,
                tier=tier,
            )
        )
    return out


def extract_decisions_from_text(
    text: str,
    *,
    source: DecisionSource,
    source_ref: str,
    timestamp: datetime,
    author: str = "",
    file_path: str = "",
    confidence: float = 0.55,
    category: str = "design",
    tier: DecisionTier | None = None,
) -> list[Decision]:
    """Extract decision-like sentences from free text.

    Args:
        tier: Force the tier for every hit; when omitted each sentence is
            classified on its own (reason/alternative => decision).
    """
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
                confidence=confidence,
                category=category,
                tier=tier,
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
        tier=DecisionTier.DECISION,
    )


DEPENDENCY_RE = re.compile(
    r"^(build\(deps|chore\(deps|deps(\([^)]*\))?:|bump |update .* to v?\d|dependabot)",
    re.IGNORECASE,
)

# "bump qs from 6.5.2 to 6.5.3" / "bump body-parser to ^2.3.0"
DEPENDENCY_BUMP_RE = re.compile(
    r"\bbump[s]?\b[^.]*\b(from|to)\b", re.IGNORECASE
)


def is_dependency_commit(text: str) -> bool:
    """Return True when a commit subject looks like a dependency bump."""
    value = (text or "").strip()
    return bool(DEPENDENCY_RE.match(value) or DEPENDENCY_BUMP_RE.search(value))
