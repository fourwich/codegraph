"""Resolve git refs (tag / sha / date) to commits."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class RefError(ValueError):
    """Raised when a ref cannot be resolved."""


def resolve_ref(repo_path: Path, ref: str) -> tuple[str, datetime]:
    """Resolve a tag, commit sha, or YYYY-MM-DD date to (sha, timestamp)."""
    from git import InvalidGitRepositoryError, Repo

    value = (ref or "").strip()
    if not value:
        raise RefError("Empty ref")

    root = repo_path.expanduser().resolve()
    try:
        repo = Repo(str(root), search_parent_directories=True)
    except InvalidGitRepositoryError as exc:
        raise RefError(f"Not a git repository: {root}") from exc

    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            day = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise RefError(f"Invalid date '{value}'. Use YYYY-MM-DD") from exc
        best = None
        best_dt = None
        for commit in repo.iter_commits("HEAD"):
            ts = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
            if ts.date() == day:
                if best_dt is None or ts >= best_dt:
                    best = commit.hexsha
                    best_dt = ts
        if best is None:
            raise RefError(f"No commit found on {value}")
        return best, best_dt

    try:
        commit = repo.commit(value)
    except Exception as exc:
        tags = [t.name for t in repo.tags]
        hint = f" Available tags: {', '.join(tags[:12])}" if tags else ""
        raise RefError(f"Cannot resolve ref '{value}'.{hint}") from exc

    ts = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
    return commit.hexsha, ts
