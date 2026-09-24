"""Git history access via GitPython."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommitInfo:
    """Lightweight commit metadata."""

    sha: str
    author: str
    timestamp: datetime
    message: str
    changed_files: list[str] = field(default_factory=list)


class GitHistory:
    """Read commits and file snapshots from a local Git repository."""

    def __init__(self, repo_path: Path) -> None:
        """Open the repository at repo_path.

        Args:
            repo_path: Working tree or .git parent directory.

        Raises:
            ValueError: When the path is not a Git repository.
        """
        from git import InvalidGitRepositoryError, Repo

        self._path = repo_path.expanduser().resolve()
        try:
            # Prefer the directory itself; fall back to parents only if it is inside a worktree.
            self._repo = Repo(str(self._path))
        except InvalidGitRepositoryError:
            try:
                self._repo = Repo(str(self._path), search_parent_directories=True)
                root = Path(self._repo.working_dir).resolve()
                if self._path != root and root not in self._path.parents:
                    raise ValueError(f"Not a git repository: {repo_path}")
            except InvalidGitRepositoryError as exc:
                raise ValueError(f"Not a git repository: {repo_path}") from exc

    @property
    def root(self) -> Path:
        """Return the repository working tree root."""
        return Path(self._repo.working_dir)

    def iter_commits(
        self, since: str | None = None, depth: int | None = None
    ) -> Iterator[CommitInfo]:
        """Yield commits from newest to oldest.

        Args:
            since: Optional ISO date lower bound (inclusive).
            depth: Optional max number of commits to yield.

        Yields:
            CommitInfo records.
        """
        kwargs: dict = {"max_count": depth} if depth else {}
        try:
            commits = list(self._repo.iter_commits("HEAD", **kwargs))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to list commits: %s", exc)
            return

        for commit in commits:
            try:
                info = self._to_info(commit)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skip commit %s: %s", getattr(commit, "hexsha", "?"), exc)
                continue
            if since and info.timestamp.date().isoformat() < since:
                continue
            yield info

    def get_file_at_commit(self, commit_sha: str, file_path: str) -> str:
        """Return file text at a commit.

        Args:
            commit_sha: Commit hexsha.
            file_path: Path relative to the repo root.

        Returns:
            File contents as text. Empty string when missing.
        """
        rel = file_path.replace("\\", "/")
        try:
            blob = self._repo.commit(commit_sha).tree / rel
            data = blob.data_stream.read()
            return data.decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            logger.debug("File %s not in %s: %s", rel, commit_sha, exc)
            return ""

    def get_commits_touching(self, file_path: str) -> list[CommitInfo]:
        """Return commits that modified a path (newest first)."""
        rel = file_path.replace("\\", "/")
        try:
            commits = list(self._repo.iter_commits("HEAD", paths=rel))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to list commits for %s: %s", rel, exc)
            return []
        out: list[CommitInfo] = []
        for commit in commits:
            try:
                out.append(self._to_info(commit))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skip commit for %s: %s", rel, exc)
        return out

    def list_files_at_commit(self, commit_sha: str) -> list[str]:
        """List blob paths under the tree at a commit."""
        try:
            tree = self._repo.commit(commit_sha).tree
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cannot read tree for %s: %s", commit_sha, exc)
            return []
        paths: list[str] = []
        for blob in tree.traverse():
            if getattr(blob, "type", None) == "blob":
                paths.append(str(getattr(blob, "path", "")))
        return paths

    def _to_info(self, commit) -> CommitInfo:
        """Convert a GitPython commit into CommitInfo."""
        timestamp = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
        changed: list[str] = []
        try:
            if commit.parents:
                diffs = commit.parents[0].diff(commit, create_patch=False)
                for diff in diffs:
                    path = diff.b_path or diff.a_path
                    if path:
                        changed.append(path)
            else:
                changed = [item.path for item in commit.tree.traverse() if item.type == "blob"]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Changed files for %s: %s", commit.hexsha, exc)

        return CommitInfo(
            sha=commit.hexsha,
            author=str(commit.author),
            timestamp=timestamp,
            message=commit.message or "",
            changed_files=changed,
        )
