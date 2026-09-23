"""codegraph serve: start the local web visualizer."""

from __future__ import annotations

import webbrowser

import typer
from rich.console import Console

console = Console()


def serve_command(
    port: int = typer.Option(8080, "--port", help="HTTP port", metavar="N"),
    backend: str = typer.Option(
        "sqlite",
        "--backend",
        help="Graph backend: sqlite | dgraph",
        metavar="BACKEND",
    ),
    open_browser: bool = typer.Option(
        True,
        "--open-browser/--no-open-browser",
        help="Open the UI in the default browser",
    ),
) -> None:
    """Start the local Cytoscape web visualizer.

    Args:
        port: HTTP listen port.
        backend: Storage backend used by API routes.
        open_browser: Launch a browser tab on start.
    """
    if backend not in {"sqlite", "dgraph"}:
        console.print(
            f"[bold red]Invalid argument[/] Unknown backend: {backend} (use sqlite | dgraph)"
        )
        raise typer.Exit(code=2)

    import uvicorn

    from codegraph.web.app import app

    url = f"http://127.0.0.1:{port}/"
    console.print(f"[bold green]CodeGraph UI[/] {url}  [dim]backend={backend}[/]")
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


app = typer.Typer(help="Start the local web visualizer")

if __name__ == "__main__":
    app()
