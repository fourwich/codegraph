"""Three-layer conflict detection for accepted decisions.

Matching is word-boundary based and topic-gated. An earlier version matched raw
substrings, so ``use`` fired inside ``because`` and ``sync`` inside ``async``,
and any two decisions in the same folder could be reported as contradictory.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from codegraph.models import Conflict, Decision, DecisionStatus

# Each entry is a group of mutually exclusive terms. Generic verbs such as
# "use"/"avoid" are deliberately absent: they appear in almost every decision
# and produce contradictions out of unrelated documents.
OPPOSITE_PAIRS: list[tuple[str, ...]] = [
    ("always", "never"),
    ("enable", "disable"),
    ("stateful", "stateless"),
    ("sync", "async"),
    ("blocking", "non-blocking"),
    ("mutable", "immutable"),
    ("allow", "deny"),
    ("include", "exclude"),
    ("strict", "lenient"),
    ("eager", "lazy"),
    ("retry", "fail fast"),
    ("add", "remove"),
    ("keep", "drop"),
]

TEMPORAL_WINDOW_DAYS = 3
TOPIC_SIMILARITY = 0.25  # token overlap needed for same-folder decisions
RESTATEMENT_SIMILARITY = 0.8  # above this, one decision restates the other

# Terms specific enough to stand on their own. The weaker ones (add/remove,
# keep/drop, enable/disable …) also need the two decisions to share vocabulary,
# otherwise every changelog pair in one folder contradicts every other.
STRONG_TERMS = {
    "stateful", "stateless", "sync", "async", "blocking", "non-blocking",
    "mutable", "immutable", "strict", "lenient", "eager", "lazy", "fail fast",
}

_WORD_RE = re.compile(r"[a-z][a-z0-9_]{2,}")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "not", "but",
    "are", "was", "were", "must", "should", "can", "will", "has", "have", "its",
    "use", "uses", "used", "using", "prefer", "prefers", "decide", "decided",
    "our", "their", "than", "then", "also", "more", "most", "all", "any",
}


def _term_pattern(term: str) -> re.Pattern[str]:
    """Build a word-boundary pattern for a single term or phrase."""
    parts = [re.escape(part) for part in term.split()]
    return re.compile(r"\b" + r"\s+".join(parts) + r"\b", re.IGNORECASE)


_PATTERNS: dict[str, re.Pattern[str]] = {
    term: _term_pattern(term) for group in OPPOSITE_PAIRS for term in group
}


def _text(d: Decision) -> str:
    body = f"{d.content} {d.reason} {' '.join(d.alternatives)} {' '.join(d.constraints)}"
    return body.lower()


def _location(d: Decision) -> str:
    path = d.file_path or ""
    return path.rsplit("/", 1)[0] if "/" in path else (path or "(global)")


def _stem(word: str) -> str:
    """Very small stemmer: enough to match session/sessions, token/tokens."""
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokens(d: Decision) -> set[str]:
    words = {_stem(w) for w in _WORD_RE.findall(_text(d))}
    return {w for w in words if w not in _STOPWORDS}


def _overlap(a: Decision, b: Decision) -> float:
    """Overlap coefficient of two decisions' vocabulary."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _similarity(a: Decision, b: Decision) -> float:
    return SequenceMatcher(None, _text(a), _text(b)).ratio()


def _hit_terms(decision: Decision) -> set[str]:
    """Terms from OPPOSITE_PAIRS that occur as words in this decision."""
    text = _text(decision)
    return {term for term, pattern in _PATTERNS.items() if pattern.search(text)}


def _same_place(a: Decision, b: Decision) -> bool:
    """Same file, or the same folder at all."""
    if a.file_path and a.file_path == b.file_path:
        return True
    return _location(a) == _location(b) and bool(_location(a))


def _comparable(a: Decision, b: Decision, matched: list[str]) -> bool:
    """Decide whether an opposite-term hit is trustworthy enough to report."""
    if set(matched) & STRONG_TERMS:
        return True
    return _overlap(a, b) >= TOPIC_SIMILARITY


def _opposite_hits(a: Decision, b: Decision) -> list[str]:
    """Return the opposite terms that put a and b on different sides."""
    hits_a, hits_b = _hit_terms(a), _hit_terms(b)
    matched: list[str] = []
    for group in OPPOSITE_PAIRS:
        side_a = {t for t in group if t in hits_a}
        side_b = {t for t in group if t in hits_b}
        if side_a and side_b and side_a != side_b:
            matched.extend(sorted(side_a | side_b))
    return sorted(set(matched))


def detect_word_opposites(decisions: list[Decision]) -> list[Conflict]:
    """Find opposite-term conflicts on the same file or on the same topic."""
    out: list[Conflict] = []
    accepted = [d for d in decisions if d.status == DecisionStatus.ACCEPTED]
    for i, a in enumerate(accepted):
        for b in accepted[i + 1 :]:
            if a.uid == b.uid or not _same_place(a, b):
                continue
            if _similarity(a, b) >= RESTATEMENT_SIMILARITY:
                continue  # the same decision written twice
            matched = _opposite_hits(a, b)
            if not matched or not _comparable(a, b, matched):
                continue
            out.append(
                Conflict(
                    type="opposite",
                    decision_a=a,
                    decision_b=b,
                    location=_location(a),
                    matched_words=matched,
                    explanation=f"opposite terms {matched}",
                )
            )
    return out


def detect_supersede_conflicts(decisions: list[Decision]) -> list[Conflict]:
    """A supersedes B but B is still accepted."""
    out: list[Conflict] = []
    for a in decisions:
        blob = f"{a.content} {a.reason} {a.source_ref}".lower()
        if "supersede" not in blob and "取代" not in blob:
            continue
        for b in decisions:
            if a.uid == b.uid:
                continue
            if b.status != DecisionStatus.ACCEPTED:
                continue
            if b.uid in blob or b.content[:20].lower() in blob:
                out.append(
                    Conflict(
                        type="supersede",
                        decision_a=a,
                        decision_b=b,
                        location=_location(b),
                        matched_words=["supersede"],
                        explanation="claimed supersede but target still accepted",
                    )
                )
    return out


def detect_temporal_conflicts(decisions: list[Decision]) -> list[Conflict]:
    """A decision reversed shortly afterwards in the same file.

    Opposite terms are required: two unrelated decisions that merely happen to
    be close in time are not a contradiction.
    """
    out: list[Conflict] = []
    accepted = [d for d in decisions if d.status == DecisionStatus.ACCEPTED]
    for i, a in enumerate(accepted):
        for b in accepted[i + 1 :]:
            if a.uid == b.uid or not a.file_path or a.file_path != b.file_path:
                continue
            delta = abs((a.timestamp - b.timestamp).total_seconds())
            if delta > TEMPORAL_WINDOW_DAYS * 86400:
                continue
            matched = _opposite_hits(a, b)
            if not matched:
                continue
            sim = _similarity(a, b)
            if sim >= RESTATEMENT_SIMILARITY:
                continue
            days = delta / 86400
            out.append(
                Conflict(
                    type="temporal",
                    decision_a=a,
                    decision_b=b,
                    location=_location(a),
                    matched_words=matched,
                    explanation=(
                        f"reversed within {days:.1f}d (similarity {sim:.2f}) "
                        f"with opposites {matched}"
                    ),
                    confidence=0.8,
                )
            )
    return out


def detect_all(decisions: list[Decision]) -> list[Conflict]:
    """Run all detectors and keep the most specific report per decision pair."""
    raw = (
        detect_word_opposites(decisions)
        + detect_supersede_conflicts(decisions)
        + detect_temporal_conflicts(decisions)
    )
    rank = {"supersede": 0, "temporal": 1, "opposite": 2}
    best: dict[tuple[str, str], Conflict] = {}
    for conflict in raw:
        first, second = sorted([conflict.decision_a.uid, conflict.decision_b.uid])
        key = (first, second)
        prev = best.get(key)
        if prev is None or rank.get(conflict.type, 9) < rank.get(prev.type, 9):
            best[key] = conflict
    return sorted(best.values(), key=lambda c: (rank.get(c.type, 9), c.location))
