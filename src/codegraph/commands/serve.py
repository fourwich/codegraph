"""codegraph serve: start the local web visualizer."""

from __future__ import annotations

import threading
import time
import webbrowser

import typer
from rich.console import Console

console = Console()

READY_TIMEOUT_SECONDS = 5.0


def open_when_ready(server, url: str, timeout: float = READY_TIMEOUT_SECONDS) -> None:
    """Open the browser only once the server is actually accepting requests.

    Opening before the port is bound shows a connection error to the user, and
    on a busy port the tab points at whatever else is listening.
    """
    deadline = time.monotonic() + timeout
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if server.started:
        webbrowser.open(url)


def serve_command(
    port: int = typer.Option(8080, "--port", help="HTTP port", metavar="N"),
    open_browser: bool = typer.Option(
        True,
        "--open-browser/--no-open-browser",
        help="Open the UI in the default browser",
    ),
) -> None:
    """Start the local Cytoscape web visualizer.

    Args:
        port: HTTP listen port.
        open_browser: Launch a browser tab once the server is listening.
    """
    import uvicorn

    from codegraph.web.app import app

    url = f"http://127.0.0.1:{port}/"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    console.print(f"[bold green]CodeGraph UI[/] {url}")
    if open_browser:
        threading.Thread(
            target=open_when_ready, args=(server, url), daemon=True
        ).start()
    server.run()


app = typer.Typer(help="Start the local web visualizer")

if __name__ == "__main__":
    app()
