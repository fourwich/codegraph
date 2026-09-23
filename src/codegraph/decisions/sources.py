"""Extract Decisions from commits, ADR files, and CHANGELOG."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from codegraph.decisions.extractor import (
    decision_from_adr_sections,
    decision_from_commit_subject,
    extract_decisions_from_text,
    parse_adr_markdown,
)
from codegraph.git.history import GitHistory
from codegraph.models import Decision, DecisionSource

logger = logging.getLogger(__name__)

CHANGELOG_SECTION = re.compile(
    r"^##\s+\[?(Changed|Removed|Deprecated|Breaking|Security)\]?",
    re.IGNORECASE | re.MULTILINE,
)
CHANGELOG_NEXT = re.compile(r"^##\s+", re.MULTILINE)


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
            found = extract_decisions_from_text(
                commit.message,
                source=DecisionSource.COMMIT,
                source_ref=ref,
                timestamp=commit.timestamp,
                author=commit.author,
                file_path=path,
            )
            subject = decision_from_commit_subject(
                commit.message,
                source_ref=ref,
                timestamp=commit.timestamp,
                author=commit.author,
                file_path=path,
            )
            if subject:
                found.append(subject)
            if llm is not None and not _has_rationale(commit.message):
                extra = llm.extract_decision(
                    commit.message,
                    ", ".join(commit.changed_files[:20]),
                    source_ref=ref,
                    author=commit.author,
                    file_path=path,
                )
                if extra:
                    found.append(extra)
            out.extend(found)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Decision extract failed for %s: %s", commit.sha, exc)
    return out


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


def extract_from_changelog(repo_path: Path) -> list[Decision]:
    """Extract decision-like bullets from CHANGELOG Changed/Removed sections."""
    path = repo_path / "CHANGELOG.md"
    if not path.is_file():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read CHANGELOG: %s", exc)
        return []

    out: list[Decision] = []
    matches = list(CHANGELOG_SECTION.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        nxt = CHANGELOG_NEXT.search(text, start)
        if nxt and nxt.start() < end:
            end = nxt.start()
        body = text[start:end]
        section = match.group(1)
        found = extract_decisions_from_text(
            f"{section}: {body}",
            source=DecisionSource.COMMENT,
            source_ref=f"CHANGELOG · {section}",
            timestamp=_file_time(path),
            file_path="CHANGELOG.md",
        )
        out.extend(found)
    return out


def extract_all(
    repo_path: Path,
    depth: int | None = 100,
    use_llm: bool = False,
    llm_model: str = "llama3.2",
) -> list[Decision]:
    """Extract decisions from all supported sources and de-duplicate by uid."""
    merged: dict[str, Decision] = {}
    for item in extract_from_commits(
        repo_path, depth=depth, use_llm=use_llm, llm_model=llm_model
    ):
        merged.setdefault(item.uid, item)
    for item in extract_from_adrs(repo_path):
        merged.setdefault(item.uid, item)
    for item in extract_from_changelog(repo_path):
        merged.setdefault(item.uid, item)
    return list(merged.values())


def _file_time(path: Path) -> datetime:
    """Best-effort mtime as UTC datetime."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.now(timezone.utc)
