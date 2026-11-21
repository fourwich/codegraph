"""Install the agent skill that teaches `codegraph why` to coding assistants.

The skill is a Markdown file with YAML frontmatter. Every agent that reads a skills
directory understands that format, and each one uses a different root, so this command
writes the same file to whichever roots the caller asks for.

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

from codegraph.i18n import help_text

console = Console()

# The skill text. Kept as a module constant rather than a data file so the wheel stays
# a single package and `pip install` is enough to ship it. `.dsh/skills` in this
# repository holds the same bytes, and a test compares them so they cannot drift.
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

```bash
pip install codegraphx
codegraph index . --depth 50
```

`--depth` is how far back the git history is read; deeper finds older decisions and
takes longer. The database lands in `.codegraph/graph.db`. Run this once per
repository — `why` reports no record until the repository is indexed.

## Two ways to ask

**By location** — the precise form:

```bash
codegraph why src/codegraph/storage.py:200
```

**By symbol name** — when you know the function, not the line:

```bash
codegraph why insert_nodes
```

The symbol form resolves to the innermost live definition and prints it, so you can
see which one was chosen. If the name does not exist, the error suggests close
matches:

```
Cannot parse location 'insert'. ... Did you mean: insert_edges, insert_nodes, insert_decisions?
```

Names are matched exactly. A near miss is never silently accepted — a fuzzy match
would return the wrong symbol and the card alone would not reveal it.

A symbol has no path to carry its repository, so querying one from outside its
repository needs `--root`:

```bash
codegraph why make_response --root ../flask
```

`path:line` does not need it: an absolute path already names the repository, and a
relative one is resolved by walking up.

## Reading the answer

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

**`binding`** tells you how the record was matched:

| binding | meaning |
|---|---|
| `line` | a record bound to this exact line — the strongest answer |
| `file` | nothing bound to the line; these records concern the file |
| `commit` | matched through the commit that touched the line |
| `dir` | concerns the surrounding directory — weakest, use with care |
| `none` | no record |

**`found: false` is a real answer.** CodeGraph only shows a decision card when the
record states a reason or a rejected alternative. A project that never wrote down its
rationale produces no cards — that is the honest result, not a tool failure. Say so,
rather than inventing a plausible reason.

## Flags

| flag | effect |
|---|---|
| `--json` | machine-readable payload, for scripting or an editor |
| `--include-events` | also show plain history (commit subjects, changelog lines) |
| `--include-dependency` | also show dependency-bump decisions |

`--json` returns `{ file, line, node, decisions, binding, related }`. It exits 1 when
no decision matched, so a script can branch on the code without parsing text.

## Going further

```bash
codegraph decisions --file src/storage.py --timeline   # how a file's decisions evolved
codegraph decisions --timeline                         # the whole repository, oldest first
codegraph conflicts --scope src                        # decisions that contradict each other
codegraph graph --at 2026-09-28 --scope src            # the code graph as of a past date
codegraph export --for-ai --scope src                  # a context pack for a larger review
```

`decisions --timeline` is the one to reach for when the question is "how did this file
get to its current shape" rather than "why does this one line exist".

## Limits worth stating to the user

- **Coverage is partial.** Measured on seven real repositories, 12–40% of sampled
  lines returned a line-level card. A changelog entry links to one line, not to every
  line it influenced; the file-level fallback covers part of that gap.
- **A root-level file gets no directory fallback.** The root is not a subject area, so
  `why LICENSE:1` correctly reports no record.
- **A shallow clone carries only recent history**, so older decisions are absent.
- **Seven languages:** Python, TypeScript, JavaScript, Java, Go, Rust, C++.
- **Indexing is a prerequisite, not automatic.** An unindexed repository reports no
  record for everything, which reads like a broken tool rather than a missing step.

When the answer is no record, report that plainly. The value of this tool is that it
does not fabricate an explanation.
"""

SKILL_FILE = f"""\
---
name: {SKILL_NAME}
description: >-
  Answer "why is this line written this way?" from the repository's own decision
  records (ADRs, changelogs, commit messages). Use before editing unfamiliar code,
  or when a value looks arbitrary. Accepts a path:line or a symbol name.
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
        # test suite compares against the constant above, which keeps the committed
        # file from drifting away from what `install-skills` writes.
        "project": Path.cwd() / ".dsh" / "skills",
        # Claude Code: personal skills.
        "claude": home / ".claude" / "skills",
        # Cursor discovers project skills from .cursor/skills. There is no documented
        # user-level equivalent, so this is the project root, not a home directory.
        "cursor": Path.cwd() / ".cursor" / "skills",
        # The shared Agent Skills tree: read by Codex, and by Cursor as well.
        "agents": home / ".agents" / "skills",
        # The repository's own `skills/` directory. This is where `npx skills add
        # <owner>/<repo>` and the marketplaces look, so a project that publishes a skill
        # keeps the copy there rather than only in a tool-specific root.
        "published": Path.cwd() / "skills",
    }


def install_skills_command(
    target: list[str] | None = typer.Option(
        None,
        "--target",
        "-t",
        help="Root to install into: dsh, project, claude, cursor, agents. Repeatable. "
        "Defaults to every root whose parent directory already exists.",
    ),
    list_only: bool = typer.Option(
        False,
        "--list",
        "-l",
        help=help_text(
            "Show the roots and whether a skill is already installed; write nothing.",
            "只显示各目录与安装状态，不写文件。",
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help=help_text("Overwrite an existing skill file even if it differs.", "覆盖已有文件"),
    ),
) -> None:
    """Install the `codegraph-why` skill so a coding assistant knows to use it."""
    roots = skill_roots()
    chosen = list(target) if target else []

    if list_only:
        console.print("[bold]Skill roots[/]")
        for name, root in roots.items():
            installed = (root / SKILL_NAME / "SKILL.md").is_file()
            marker = "[green]installed[/]" if installed else "[dim]not installed[/]"
            exists = "" if root.parent.exists() else " [dim](parent missing)[/]"
            console.print(f"  {name:<8} {root}  {marker}{exists}")
        console.print("\n[dim]Install with: codegraph install-skills --target dsh[/]")
        return

    if not chosen:
        # Default to roots whose parent exists, so an uninstalled assistant is not
        # given a directory tree it never asked for.
        # A project root is only a sensible default inside a repository, where its
        # parent is the working directory itself; elsewhere it would write a stray
        # tree into whatever directory the caller happened to be in. `published` joins
        # them for the same reason: a repository's own `skills/` directory is a
        # publishing decision, not something to create unasked.
        project_roots = {"project", "cursor", "published"}
        chosen = [
            name
            for name, root in roots.items()
            if name not in project_roots and root.parent.exists()
        ]
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
