"""CodeGraph Typer CLI entrypoint."""

from __future__ import annotations

import typer

from codegraph import __version__
from codegraph.commands.conflicts import conflicts_command
from codegraph.commands.export import export_command
from codegraph.commands.graph import graph_command
from codegraph.commands.index import index_command
from codegraph.commands.serve import serve_command
from codegraph.commands.why import decisions_command, why_command

app = typer.Typer(
    name="codegraph",
    help=(
        "CodeGraph: turn code structure, history, and design decisions into one "
        "queryable graph.\n\n"
        "MVP stage ships a full command flow on bundled sample data and local graph stores."
    ),
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"codegraph {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """CodeGraph command-line entrypoint."""


app.command(
    name="index",
    help="Parse code + ingest Git history + write the graph (tree-sitter + SQLite/Dgraph)",
    rich_help_panel="Core commands",
)(index_command)

app.command(
    name="why",
    help="Show the decision card behind a source line, e.g. why src/auth/session.ts:42",
    rich_help_panel="Core commands",
)(why_command)

app.command(
    name="graph",
    help="Print a historical code-graph snapshot, e.g. graph --at 2024-11-02 --scope src",
    rich_help_panel="Core commands",
)(graph_command)

app.command(
    name="decisions",
    help="List the decision evolution timeline for a file",
    rich_help_panel="Core commands",
)(decisions_command)

app.command(
    name="conflicts",
    help="Detect contradictory accepted decisions in a scope",
    rich_help_panel="Core commands",
)(conflicts_command)

app.command(
    name="export",
    help="Export an AI-agent context pack (--for-ai --scope <path>)",
    rich_help_panel="Core commands",
)(export_command)

app.command(
    name="serve",
    help="Start the local Cytoscape web visualizer",
    rich_help_panel="Core commands",
)(serve_command)


if __name__ == "__main__":
    app()
