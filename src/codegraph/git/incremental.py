"""Incremental indexing helpers (record last indexed HEAD)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_REL = Path(".codegraph") / "last_index.json"


def state_path(root: Path) -> Path:
    """Return the incremental state file path."""
    return root / STATE_REL


def load_last_head(root: Path) -> str | None:
    """Return the last indexed HEAD sha, if any."""
    path = state_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Cannot read index state: %s", exc)
        return None
    value = data.get("head")
    return str(value) if value else None


def save_last_head(root: Path, head_sha: str) -> None:
    """Persist the HEAD sha that was just indexed."""
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"head": head_sha, "tool": "codegraph"}, indent=2),
        encoding="utf-8",
    )


def commits_after(root: Path, history, depth: int | None = 100) -> list:
    """Return commits newer than the last indexed HEAD (oldest first).

    Args:
        root: Repository root.
        history: GitHistory instance.
        depth: Max commits to consider.

    Returns:
        CommitInfo list needing ingest. Empty when up to date.
    """
    last = load_last_head(root)
    commits = list(history.iter_commits(depth=depth))
    if not last:
        return list(reversed(commits))
    pending = []
    for commit in commits:  # newest → oldest
        if commit.sha == last:
            break
        pending.append(commit)
    return list(reversed(pending))
