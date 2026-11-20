"""`codegraph index <path>` then query that repo from anywhere.

`index` writes `.codegraph/graph.db` inside the target repository, but every query
command used to read `<cwd>/.codegraph/graph.db` only. A first-time user who ran
`codegraph index some/repo` from their home directory was then told "no record" for
everything — the query was looking in the wrong place.

`find_db` walks up like git does, and the location string's own repository wins over
cwd.
"""

from __future__ import annotations

from pathlib import Path

from codegraph.commands.why import _resolve_db, normalize_user_path
from codegraph.storage import db_path_for_root, find_db


def _make_repo(root: Path) -> Path:
    """Create a fake indexed repository and return its database path."""
    db = db_path_for_root(root)
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_bytes(b"")
    return db


def test_find_db_walks_up_from_a_subdirectory(tmp_path) -> None:
    _make_repo(tmp_path)
    deep = tmp_path / "src" / "pkg"
    deep.mkdir(parents=True)

    assert find_db(deep) == db_path_for_root(tmp_path)


def test_find_db_returns_none_when_no_ancestor_has_one(tmp_path) -> None:
    assert find_db(tmp_path) is None


def test_resolve_db_prefers_the_directory_that_has_one(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_repo(repo)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    # The query target is inside `repo`, so its database must win over cwd.
    resolved = _resolve_db(None, str(repo / "src" / "a.py"))

    assert resolved == db_path_for_root(repo)


def test_resolve_db_falls_back_to_cwd_when_nothing_is_indexed(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert _resolve_db(None, "") == db_path_for_root(tmp_path)


def test_absolute_path_is_relativised_against_its_own_repo(tmp_path, monkeypatch) -> None:
    """An absolute path outside cwd must still become a repo-relative string."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_repo(repo)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    normalised = normalize_user_path(str(repo / "src" / "a.py"))

    assert normalised == "src/a.py"


def test_relative_path_is_left_alone(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert normalize_user_path("src/a.py") == "src/a.py"
