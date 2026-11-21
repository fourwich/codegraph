"""Install the agent skill that teaches `codegraph why` to coding assistants.

The skill is a Markdown file with YAML frontmatter. Every agent that reads a skills
directory understands that format, and each one uses a different root, so this
command writes the same file to whichever roots the caller asks for.

Nothing here is specific to one assistant: the file content is plain instructions and
the directory conventions are the published ones.

    codegraph install-skills              # every detected root
    codegraph install-skills --list       # show roots without writing
    codegraph install-skills --target dsh # one root
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

console = Console()

# The skill text. Kept as a module constant rather than a data file so the wheel
# stays a single package and `pip install` is enough to ship it.
SKILL_NAME = "codegraph-why"

SKILL_BODY = """\
# codegraph-why

Answer "why is this line written this way?" from the records the project itself
wrote down, instead of guessing from the code.

## When to use this

- Before editing code you did not write.
- When a value or structure looks arbitrary (`retryLimit = 3`, a 200ms timeout, an
  unusual ordering).
- When the user asks "why does this do X" about code, rather than "what does it do".

## Setup

The CLI must be installed once:

```bash
pip install codegraphx
```

Then index the repository you are working in. This is the only step that takes
time (a few seconds per hundred commits):

```bash
codegraph index . --depth 50
```

`--depth` is how far back the git history is read. Deeper finds older decisions and
takes longer. The database lands in `.codegraph/graph.db` inside the repository.

## Asking why

```bash
codegraph why <path>:<line>
```

Real output:

```
┌──── Matched CodeNode ────────────────────────────────┐
│  kind: function   name: insert_nodes                 │
│  range: storage.py:199-223  language: python         │
└──────────────────────────────────────────────────────┘

Query storage.py:200 → 1 matched line-level decision(s)

  Decision #1: Use SQLite (stdlib `sqlite3`) as the store
    [Reason]  CodeGraph needs a local store for CodeNodes and Edges
              during the MVP. Judges and developers must run the CLI
              without operating a database server.
    [Alternatives] · Dgraph first (rejected for MVP: requires Docker)
    [Source]  adr · ADR 001-use-sqlite-default
```

Add `--json` for machine-readable output.

## Reading the answer

**`binding`** tells you how the record was matched:

| binding | meaning |
|---|---|
| `line` | a record bound to this exact line — the strongest answer |
| `file` | nothing bound to the line; these records concern the file |
| `commit` | matched through the commit that touched the line |
| `dir` | concerns the surrounding directory — weakest, use with care |
| `none` | no record |

**`found: false` is a real answer.** CodeGraph only shows a decision card when the
record states a reason or a rejected alternative. A project that never wrote down
its rationale produces no cards — that is the honest result, not a tool failure.
Say so, rather than inventing a plausible reason.

## Related commands

```bash
codegraph decisions --file <path> --timeline   # how a file's decisions evolved
codegraph conflicts --scope <path>             # decisions that contradict each other
codegraph graph --at 2026-09-28 --scope src    # the code graph as of a past date
```

## Limits worth stating to the user

- **Coverage is partial.** Measured on seven real repositories, 12–40% of sampled
  lines returned a line-level card. A changelog entry links to one line, not to
  every line it influenced.
- **A root-level file gets no directory fallback.** The root is not a subject area,
  so `why LICENSE:1` correctly reports no record.
- **A shallow clone carries only recent history**, so older decisions are absent.
- **Seven languages:** Python, TypeScript, JavaScript, Java, Go, Rust, C++.

When the answer is no record, report that plainly. The value of this tool is that
it does not fabricate an explanation.
"""

SKILL_FILE = f"""\
---
name: {SKILL_NAME}
description: >-
  Explain why a line of code exists, from the repository's own decision records
  (ADRs, changelogs, commit messages). Use before changing unfamiliar code, or
  when asked why something is written a certain way.
---

{SKILL_BODY}"""


def _home() -> Path:
    return Path.home()


def _dsh_home() -> Path:
    """Where DeepSeek Harness keeps user-level skills."""
    override = os.environ.get("DSH_HOME")
    return Path(override) if override else _home() / ".dsh"


def skill_roots() -> dict[str, Path]:
    """Every known skills directory, keyed by a short target name.

    A root is listed whether or not its parent exists: the tool decides what to
    create. Only the roots whose convention is published are included.
    """
    home = _home()
    return {
        # DeepSeek Harness: user-level root, applies to every project.
        "dsh": _dsh_home() / "skills",
        # DeepSeek Harness: project-level root, committed with the repository so a
        # clone carries the skill with no install step. This is also the copy the
        # test suite compares against the constant below, which keeps the
        # committed file from drifting away from what `install-skills` writes.
        "project": Path.cwd() / ".dsh" / "skills",
        # Claude Code reads ~/.claude/skills.
        "claude": home / ".claude" / "skills",
        # Cursor reads ~/.cursor/rules for project rules; skills live beside them.
        "cursor": home / ".cursor" / "skills",
        # The AGENTS.md convention: ~/.agents/skills, read by several assistants.
        "agents": home / ".agents" / "skills",
    }


def install_skills_command(
    target: list[str] | None = typer.Option(
        None,
        "--target",
        "-t",
        help="Root to install into: dsh, claude, cursor, agents. Repeatable. "
        "Defaults to every root whose parent directory already exists.",
    ),
    list_only: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="Show the roots and whether a skill is already installed; write nothing.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite an existing skill file even if it differs.",
    ),
) -> None:
    """Install the `codegraph-why` skill so a coding assistant knows to use it."""
    roots = skill_roots()
    chosen = list(target) if target else []

    if list_only:
        console.print("[bold]Skill roots[/]")
        for name, root in roots.items():
            installed = (root / SKILL_NAME / "SKILL.md").is_file()
            # `parent.exists()` is the signal used for the default selection, so show it.
            marker = "[green]installed[/]" if installed else "[dim]not installed[/]"
            exists = "" if root.parent.exists() else " [dim](parent missing)[/]"
            console.print(f"  {name:<8} {root}  {marker}{exists}")
        console.print("\n[dim]Install with: codegraph install-skills --target dsh[/]")
        return

    if not chosen:
        # Default to roots whose parent exists, so an uninstalled assistant is not
        # given a directory tree it never asked for.
        chosen = [name for name, root in roots.items() if root.parent.exists()]
        if not chosen:
            console.print(
                "[yellow]No assistant directory found.[/] "
                "Pass --target explicitly, e.g. codegraph install-skills --target dsh"
            )
            raise typer.Exit(code=1)
        console.print(f"[dim]Detected: {', '.join(chosen)}[/]")

    unknown = [name for name in chosen if name not in roots]
    if unknown:
        console.print(
            f"[bold red]Unknown target[/] {', '.join(unknown)}. "
            f"Choose from: {', '.join(roots)}"
        )
        raise typer.Exit(code=2)

    written = 0
    skipped = 0
    for name in chosen:
        destination = roots[name] / SKILL_NAME / "SKILL.md"
        try:
            if destination.is_file() and not force:
                existing = destination.read_text(encoding="utf-8")
                if existing != SKILL_FILE:
                    console.print(
                        f"  [yellow]skip[/] {name}: {destination} differs "
                        "(use --force to overwrite)"
                    )
                    skipped += 1
                    continue
                console.print(f"  [green]ok[/]   {name}: already current")
                written += 1
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(SKILL_FILE, encoding="utf-8", newline="\n")
            console.print(f"  [green]wrote[/] {name}: {destination}")
            written += 1
        except OSError as exc:
            console.print(f"  [red]fail[/] {name}: {exc}")
            skipped += 1

    if written:
        console.print(
            f"\n[bold]Installed[/] the `{SKILL_NAME}` skill in {written} location(s). "
            "Start a new assistant session for it to be discovered."
        )
    if skipped and not written:
        raise typer.Exit(code=1)


__all__ = ["SKILL_BODY", "SKILL_FILE", "SKILL_NAME", "install_skills_command", "skill_roots"]
