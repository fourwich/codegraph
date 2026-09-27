"""Parse unified diffs to find changed line numbers per commit."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _parse_patch_lines(patch: str) -> list[int]:
    """Return new-file line numbers touched in a unified diff patch."""
    lines: list[int] = []
    new_ln = 0
    in_hunk = False
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            m = HUNK_RE.match(raw)
            if not m:
                in_hunk = False
                continue
            new_ln = int(m.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            lines.append(new_ln)
            new_ln += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        elif raw.startswith("\\"):
            continue
        else:
            new_ln += 1
    return lines


def get_changed_lines(repo_path: Path, commit_sha: str) -> dict[str, list[int]]:
    """Return {file_path: [changed line numbers]} for one commit.

    Uses GitPython to read the unified diff of commit vs its first parent
    (or the full tree for a root commit).
    """
    from git import InvalidGitRepositoryError, Repo

    root = repo_path.expanduser().resolve()
    try:
        repo = Repo(str(root), search_parent_directories=True)
    except InvalidGitRepositoryError:
        logger.warning("Not a git repo: %s", root)
        return {}

    try:
        commit = repo.commit(commit_sha)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cannot read commit %s: %s", commit_sha, exc)
        return {}

    out: dict[str, list[int]] = {}
    try:
        if commit.parents:
            diffs = commit.parents[0].diff(commit, create_patch=True, unified=3)
        else:
            diffs = commit.diff(NULL_TREE(repo), create_patch=True, unified=3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Diff failed for %s: %s", commit_sha, exc)
        return {}

    for d in diffs:
        path = d.b_path or d.a_path
        if not path:
            continue
        rel = str(path).replace("\\", "/")
        patch = ""
        try:
            raw_patch = d.diff
            if isinstance(raw_patch, bytes):
                patch = raw_patch.decode("utf-8", errors="replace")
            else:
                patch = str(raw_patch or "")
        except Exception:  # noqa: BLE001
            patch = ""
        if not patch:
            continue
        touched = sorted(set(_parse_patch_lines(patch)))
        if touched:
            out[rel] = touched
    return out


def NULL_TREE(repo):
    """Empty tree object used as parent for root commits."""
    return repo.tree("4b825dc642cb6eb9a060e54bf8d69288fbee4904")
