"""codegraph serve: start the local web visualizer."""

from __future__ import annotations

import threading
import time
import webbrowser

import typer
from rich.console import Console

from codegraph.i18n import help_text, t

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
        help=help_text("Open the UI in the default browser", "用默认浏览器打开界面"),
    ),
) -> None:
    """Start the local Cytoscape web visualizer.

    The web stack (FastAPI, uvicorn) is an optional extra: most users only run
    `index` and `why`, and installing a server framework for them is dead weight in
    a `pip install`. The import happens here so the base install stays small, and a
    missing extra names the command that fixes it instead of raising ImportError.

    Args:
        port: HTTP listen port.
        open_browser: Launch a browser tab once the server is listening.
    """
    try:
        import uvicorn

        from codegraph.web.app import app
    except ImportError as exc:
        # The brackets need quoting on most shells, and PowerShell would otherwise
        # read them as a wildcard pattern.
        console.print(
            f"[bold red]{t('serve.missing_extra')}[/]\n"
            '  pip install codegraphx\\[serve]\n'
            f"  [dim]{exc}[/]"
        )
        raise typer.Exit(code=1) from exc

    url = f"http://127.0.0.1:{port}/"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    console.print(f"[bold green]CodeGraph UI[/] {url}")
    if open_browser:
        threading.Thread(
            target=open_when_ready, args=(server, url), daemon=True
        ).start()
    server.run()


app = typer.Typer(help=help_text("Start the local web visualizer", "启动本地网页可视化"))

if __name__ == "__main__":
    app()
