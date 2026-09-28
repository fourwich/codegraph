"""Three-layer conflict detection for accepted decisions."""

from __future__ import annotations

from difflib import SequenceMatcher

from codegraph.models import Conflict, Decision, DecisionStatus

# Each entry is a group of mutually exclusive terms.
OPPOSITE_PAIRS: list[tuple[str, ...]] = [
    ("use", "avoid"),
    ("always", "never"),
    ("enable", "disable"),
    ("add", "remove"),
    ("keep", "drop"),
    ("sync", "async"),
    ("stateful", "stateless"),
    ("cache", "no-cache", "bypass cache"),
    ("retry", "no retry", "fail fast"),
    ("strict", "lenient"),
    ("eager", "lazy"),
]

TEMPORAL_WINDOW_DAYS = 7
TEMPORAL_SIMILARITY = 0.3


def _text(d: Decision) -> str:
    return f"{d.content} {d.reason} {' '.join(d.alternatives)} {' '.join(d.constraints)}".lower()


def _location(d: Decision) -> str:
    path = d.file_path or ""
    return path.rsplit("/", 1)[0] if "/" in path else (path or "(global)")


def _same_place(a: Decision, b: Decision) -> bool:
    """Same file or same location folder."""
    if a.file_path and b.file_path and a.file_path == b.file_path:
        return True
    return _location(a) == _location(b) and bool(_location(a))


def detect_word_opposites(decisions: list[Decision]) -> list[Conflict]:
    """Find opposite-term conflicts on the same file/location."""
    out: list[Conflict] = []
    accepted = [d for d in decisions if d.status == DecisionStatus.ACCEPTED]
    for i, a in enumerate(accepted):
        for b in accepted[i + 1 :]:
            if a.uid == b.uid or not _same_place(a, b):
                continue
            ta, tb = _text(a), _text(b)
            best: Conflict | None = None
            best_score = -1
            for group in OPPOSITE_PAIRS:
                hit_a = [w for w in group if w in ta]
                hit_b = [w for w in group if w in tb]
                if not hit_a or not hit_b or set(hit_a) == set(hit_b):
                    continue
                score = max(len(w) for w in list(hit_a) + list(hit_b))
                if score <= best_score:
                    continue
                best_score = score
                best = Conflict(
                    type="opposite",
                    decision_a=a,
                    decision_b=b,
                    location=_location(a),
                    matched_words=sorted(set(hit_a) | set(hit_b)),
                    explanation=f"opposite terms {sorted(hit_a, key=len)[-1]!r} vs {sorted(hit_b, key=len)[-1]!r}",
                )
            if best is not None:
                out.append(best)
    return out


def detect_supersede_conflicts(decisions: list[Decision]) -> list[Conflict]:
    """A supersedes B but B is still accepted."""
    out: list[Conflict] = []
    by_uid = {d.uid: d for d in decisions}
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
    """Nearby accepted decisions with low text similarity."""
    out: list[Conflict] = []
    accepted = [d for d in decisions if d.status == DecisionStatus.ACCEPTED]
    for i, a in enumerate(accepted):
        for b in accepted[i + 1 :]:
            if a.uid == b.uid or not _same_place(a, b):
                continue
            delta = abs((a.timestamp - b.timestamp).total_seconds())
            if delta > TEMPORAL_WINDOW_DAYS * 86400:
                continue
            sim = SequenceMatcher(None, _text(a), _text(b)).ratio()
            if sim < TEMPORAL_SIMILARITY:
                out.append(
                    Conflict(
                        type="temporal",
                        decision_a=a,
                        decision_b=b,
                        location=_location(a),
                        matched_words=[],
                        explanation=f"nearby in time ({delta/86400:.1f}d) but low similarity ({sim:.2f})",
                    )
                )
    return out


def detect_all(decisions: list[Decision]) -> list[Conflict]:
    """Run all detectors and keep one strongest report per decision pair."""
    raw = detect_word_opposites(decisions) + detect_supersede_conflicts(decisions) + detect_temporal_conflicts(decisions)
    rank = {"opposite": 0, "supersede": 1, "temporal": 2}
    best: dict[tuple[str, str], Conflict] = {}
    for c in raw:
        key = tuple(sorted([c.decision_a.uid, c.decision_b.uid]))
        prev = best.get(key)
        if prev is None or rank.get(c.type, 9) < rank.get(prev.type, 9):
            best[key] = c
    return sorted(best.values(), key=lambda c: (rank.get(c.type, 9), c.location))
