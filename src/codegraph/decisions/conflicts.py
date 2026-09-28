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

TEMPORAL_WINDOW_DAYS = 3
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
    """Nearby accepted decisions that still contradict on the same file.

    Tightened to cut false positives:
    - same file_path (not merely same folder)
    - within 3 days
    - low text similarity
    - must share an opposite-term pair (otherwise confidence too low)
    """
    out: list[Conflict] = []
    accepted = [d for d in decisions if d.status == DecisionStatus.ACCEPTED]
    for i, a in enumerate(accepted):
        for b in accepted[i + 1 :]:
            if a.uid == b.uid:
                continue
            if not a.file_path or a.file_path != b.file_path:
                continue
            delta = abs((a.timestamp - b.timestamp).total_seconds())
            if delta > TEMPORAL_WINDOW_DAYS * 86400:
                continue
            sim = SequenceMatcher(None, _text(a), _text(b)).ratio()
            if sim >= TEMPORAL_SIMILARITY:
                continue
            ta, tb = _text(a), _text(b)
            matched: list[str] = []
            for group in OPPOSITE_PAIRS:
                ha = [w for w in group if w in ta]
                hb = [w for w in group if w in tb]
                if ha and hb and set(ha) != set(hb):
                    matched = sorted(set(ha) | set(hb))
                    break
            if not matched:
                # No opposites: only keep very close, very different, same file
                if delta > 3 * 86400:
                    continue
            days = delta / 86400
            if matched and days <= 3:
                confidence = 0.8
            elif matched:
                confidence = 0.3
            else:
                confidence = 0.5 if days <= 3 else 0.3
            if confidence < 0.5:
                continue
            out.append(
                Conflict(
                    type="temporal",
                    decision_a=a,
                    decision_b=b,
                    location=_location(a),
                    matched_words=matched,
                    explanation=(
                        f"nearby in time ({days:.1f}d) but low similarity ({sim:.2f})"
                        + (f" with opposites {matched}" if matched else "")
                    ),
                    confidence=confidence,
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
