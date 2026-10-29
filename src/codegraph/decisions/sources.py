"""Extract Decisions from commits, ADR files, and CHANGELOG."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from codegraph.decisions.extractor import (
    decision_from_adr_sections,
    decision_from_commit_subject,
    decisions_from_commit_body,
    extract_decisions_from_text,
    parse_adr_markdown,
)
from codegraph.git.history import GitHistory
from codegraph.models import Decision, DecisionSource, DecisionTier

logger = logging.getLogger(__name__)

CHANGELOG_SECTION = re.compile(
    r"^##\s+\[?(Changed|Removed|Deprecated|Breaking|Security)\]?",
    re.IGNORECASE | re.MULTILINE,
)
CHANGELOG_NEXT = re.compile(r"^##\s+", re.MULTILINE)

# Python projects usually ship CHANGES.rst with reStructuredText headings, and
# reading only CHANGELOG.md made the tool blind to them: Flask's 537 release-note
# bullets produced one decision instead of the 26 that state a rationale.
CHANGELOG_NAMES = (
    "CHANGELOG.md",
    "CHANGELOG.rst",
    "CHANGELOG.txt",
    "CHANGES.md",
    "CHANGES.rst",
    "CHANGES.txt",
    "HISTORY.md",
    "HISTORY.rst",
    "NEWS.md",
    "NEWS.rst",
)
_BULLET = re.compile(r"^(?P<marker>[-*+])\s+(?P<text>\S.*)$")
_RST_UNDERLINE = re.compile(r"^(?P<title>\S.*)\n[-=~^\"'`#*+]{3,}\s*$", re.MULTILINE)
_MD_HEADING = re.compile(r"^(?P<hashes>#{1,4})\s+(?P<title>.+?)\s*#*$", re.MULTILINE)


def _changelog_path(repo_path: Path) -> Path | None:
    """Return the first conventional changelog file that exists.

    The comparison is case-insensitive on purpose: Express ships `History.md`
    and a case-sensitive lookup would find it on Windows but not on macOS or
    Linux, so the same repository produced different graphs per platform.
    """
    if not repo_path.is_dir():
        return None
    by_lower = {path.name.lower(): path for path in repo_path.iterdir() if path.is_file()}
    for name in CHANGELOG_NAMES:
        candidate = by_lower.get(name.lower())
        if candidate is not None:
            return candidate
    return None


def _sections(text: str) -> list[tuple[str, str]]:
    """Split a changelog into (heading, body) pairs for markdown or rst."""
    headings = [(m.start(), m.group("title")) for m in _RST_UNDERLINE.finditer(text)]
    headings += [(m.start(), m.group("title")) for m in _MD_HEADING.finditer(text)]
    if not headings:
        return [("Changelog", text)]
    headings.sort(key=lambda item: item[0])
    out: list[tuple[str, str]] = []
    for index, (start, title) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        out.append((title.strip()[:60], text[start:end]))
    return out


def _bullets(body: str) -> list[str]:
    """Return bullet texts, joining indented continuation lines."""
    bullets: list[str] = []
    current: list[str] = []
    for raw in body.splitlines():
        match = _BULLET.match(raw.strip())
        if match:
            if current:
                bullets.append(" ".join(current))
            current = [match.group("text").strip()]
        elif current and raw.startswith((" ", "\t")) and raw.strip():
            current.append(raw.strip())
        elif current and not raw.strip():
            bullets.append(" ".join(current))
            current = []
    if current:
        bullets.append(" ".join(current))
    return [b for b in bullets if len(b) > 8]


def extract_from_changelog(repo_path: Path) -> list[Decision]:
    """Extract decision-like bullets from a changelog, markdown or rst.

    Every bullet is a candidate and the tier classifier keeps only the ones that
    state a reason or a rejected alternative, so listing all of them raises recall
    without lowering precision.
    """
    path = _changelog_path(repo_path)
    if path is None:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read %s: %s", path.name, exc)
        return []

    out: list[Decision] = []
    for heading, body in _sections(text):
        for bullet in _bullets(body):
            out.extend(
                extract_decisions_from_text(
                    f"{heading}: {bullet}",
                    source=DecisionSource.COMMENT,
                    source_ref=f"{path.name} · {heading}",
                    timestamp=_file_time(path),
                    file_path=path.name,
                    confidence=0.6,
                )
            )
    return out


def extract_from_commits(
    repo_path: Path,
    depth: int | None = 100,
    use_llm: bool = False,
    llm_model: str = "llama3.2",
) -> list[Decision]:
    """Extract rationale-like decisions from commit messages."""
    try:
        history = GitHistory(repo_path)
    except ValueError as exc:
        logger.warning("%s", exc)
        return []

    out: list[Decision] = []
    llm = None
    if use_llm:
        from codegraph.decisions.llm_extractor import LLMExtractor

        llm = LLMExtractor(model=llm_model)
        if not llm.is_available():
            logger.warning("Ollama unavailable; continuing with rule-based extraction only")
            llm = None

    for commit in history.iter_commits(depth=depth):
        try:
            ref = f"commit {commit.sha}"
            path = commit.changed_files[0] if commit.changed_files else ""
            found: list[Decision] = []
            subject = decision_from_commit_subject(
                commit.message,
                source_ref=ref,
                timestamp=commit.timestamp,
                author=commit.author,
                file_path=path,
            )
            if subject:
                found.append(subject)
            found.extend(
                decisions_from_commit_body(
                    commit.message,
                    source_ref=ref,
                    timestamp=commit.timestamp,
                    author=commit.author,
                    file_path=path,
                )
            )
            if commit.message.lstrip().lower().startswith("merge pull request"):
                found.extend(
                    extract_decisions_from_text(
                        commit.message,
                        source=DecisionSource.PR,
                        source_ref=ref,
                        timestamp=commit.timestamp,
                        author=commit.author,
                        file_path=path,
                        confidence=0.65,
                    )
                )
            if llm is not None and not _has_rationale(commit.message):
                extra = llm.extract_decision(
                    commit.message,
                    ", ".join(commit.changed_files[:20]),
                    source_ref=ref,
                    author=commit.author,
                    file_path=path,
                )
                if extra:
                    extra.tier = _llm_tier(extra)
                    found.append(extra)
            out.extend(found)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Decision extract failed for %s: %s", commit.sha, exc)
    return out


def _llm_tier(decision: Decision) -> DecisionTier:
    """LLM output is only a decision when it states a reason."""
    from codegraph.decisions.extractor import classify_tier

    return classify_tier(decision.content, decision.reason, decision.alternatives)


def _has_rationale(message: str) -> bool:
    """True when the message already contains rationale keywords."""
    from codegraph.decisions.extractor import looks_like_decision

    return any(looks_like_decision(line) for line in (message or "").splitlines())


def extract_from_adrs(repo_path: Path) -> list[Decision]:
    """Extract decisions from docs/adr/*.md files."""
    adr_dir = repo_path / "docs" / "adr"
    if not adr_dir.is_dir():
        return []

    out: list[Decision] = []
    for path in sorted(adr_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Cannot read ADR %s: %s", path, exc)
            continue
        sections = parse_adr_markdown(text)
        try:
            rel = path.relative_to(repo_path).as_posix()
        except ValueError:
            rel = path.as_posix()
        decision = decision_from_adr_sections(
            sections,
            source_ref=f"ADR {path.stem}",
            timestamp=_file_time(path),
            file_path=rel,
        )
        if decision:
            out.append(decision)
    return out




def _dedupe_key(decision: Decision) -> tuple[str, str]:
    """Key used to collapse the same content extracted by several rules."""
    normalized = " ".join((decision.content or "").split()).lower()
    return (decision.source_ref, normalized)


def _prefer(a: Decision, b: Decision) -> Decision:
    """Keep the richer of two records for the same source and content."""
    if (a.tier is DecisionTier.DECISION) != (b.tier is DecisionTier.DECISION):
        return a if a.tier is DecisionTier.DECISION else b
    return a if a.confidence >= b.confidence else b


def extract_all(
    repo_path: Path,
    depth: int | None = 100,
    use_llm: bool = False,
    llm_model: str = "llama3.2",
) -> list[Decision]:
    """Extract records from all supported sources.

    Records are de-duplicated twice: by uid, and by (source_ref, content) so the
    same sentence cannot enter twice through different rules.
    """
    merged: dict[str, Decision] = {}
    by_key: dict[tuple[str, str], Decision] = {}
    for source_items in (
        extract_from_commits(repo_path, depth=depth, use_llm=use_llm, llm_model=llm_model),
        extract_from_adrs(repo_path),
        extract_from_changelog(repo_path),
    ):
        for item in source_items:
            merged.setdefault(item.uid, item)
            key = _dedupe_key(item)
            existing = by_key.get(key)
            by_key[key] = item if existing is None else _prefer(existing, item)

    keep = {id(d) for d in by_key.values()}
    return [d for d in merged.values() if id(d) in keep]


def _file_time(path: Path) -> datetime:
    """Best-effort mtime as UTC datetime."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.now(timezone.utc)
