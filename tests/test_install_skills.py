"""`codegraph install-skills` writes a valid skill, and only where asked.

The skill is the portable way to teach an assistant about `codegraph why`: a single
Markdown file with YAML frontmatter, which every assistant that reads a skills
directory understands. The command exists so that `pip install codegraphx` is enough
— no repository clone, no manual file placement.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.commands.skills import SKILL_BODY, SKILL_FILE, SKILL_NAME, skill_roots

runner = CliRunner()


def test_skill_file_has_valid_frontmatter() -> None:
    """The file must open with a `---` block carrying name and description."""
    assert SKILL_FILE.startswith("---\n")
    parts = SKILL_FILE.split("---\n")
    # Leading empty string from the opening marker, then frontmatter, then body.
    assert len(parts) >= 3, "frontmatter must be delimited by --- on its own line"
    frontmatter = parts[1]
    assert f"name: {SKILL_NAME}" in frontmatter
    assert "description:" in frontmatter


def test_skill_body_documents_the_honest_failure() -> None:
    """The instruction that matters most: an absent record is an answer."""
    assert "found: false" in SKILL_BODY
    assert "inventing a plausible reason" in SKILL_BODY or "fabricate" in SKILL_BODY


def test_skill_body_names_every_binding_level() -> None:
    """`binding` is how a reader judges a match; all five must be explained."""
    for level in ("line", "file", "commit", "dir", "none"):
        assert f"`{level}`" in SKILL_BODY


def test_roots_cover_the_published_conventions() -> None:
    roots = skill_roots()
    assert set(roots) == {"dsh", "claude", "cursor", "agents"}
    for root in roots.values():
        assert root.name == "skills"


def test_install_writes_only_the_requested_target(tmp_path, monkeypatch) -> None:
    """A targeted install must not touch the other assistant directories."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("DSH_HOME", raising=False)
    # `skill_roots` reads HOME through Path.home(), which honours USERPROFILE here.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    result = runner.invoke(app, ["install-skills", "--target", "dsh"])
    assert result.exit_code == 0, result.output

    written = tmp_path / ".dsh" / "skills" / SKILL_NAME / "SKILL.md"
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == SKILL_FILE


def test_install_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("DSH_HOME", raising=False)

    first = runner.invoke(app, ["install-skills", "--target", "dsh"])
    second = runner.invoke(app, ["install-skills", "--target", "dsh"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "already current" in second.output


def test_existing_different_file_is_kept_without_force(tmp_path, monkeypatch) -> None:
    """A hand-edited skill must not be silently replaced."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("DSH_HOME", raising=False)

    target = tmp_path / ".dsh" / "skills" / SKILL_NAME / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("---\nname: mine\ndescription: edited\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["install-skills", "--target", "dsh"])

    assert "differs" in result.output
    assert target.read_text(encoding="utf-8").startswith("---\nname: mine")


def test_force_overwrites(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("DSH_HOME", raising=False)

    target = tmp_path / ".dsh" / "skills" / SKILL_NAME / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("stale", encoding="utf-8")

    result = runner.invoke(app, ["install-skills", "--target", "dsh", "--force"])

    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8") == SKILL_FILE


def test_unknown_target_is_rejected() -> None:
    result = runner.invoke(app, ["install-skills", "--target", "not-an-assistant"])
    assert result.exit_code == 2
    assert "Unknown target" in result.output


def test_list_reports_without_writing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("DSH_HOME", raising=False)

    result = runner.invoke(app, ["install-skills", "--list"])

    assert result.exit_code == 0
    assert "not installed" in result.output
    assert not (tmp_path / ".dsh" / "skills").exists()


def test_skill_name_is_a_valid_directory() -> None:
    assert SKILL_NAME == "codegraph-why"
    assert "/" not in SKILL_NAME and "\\" not in SKILL_NAME
