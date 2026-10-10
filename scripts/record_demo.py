"""Generate a CodeGraph terminal demo as an asciicast v2 ``.cast`` file.

asciinema's own recorder needs a Unix pseudo-terminal, so it cannot run on
Windows (``asciinema`` 2.x imports the Unix-only ``fcntl`` module, and the Rust
3.x build ships no Windows binary). This script writes the ``.cast`` file
directly instead: every command is typed out character by character and the
real command output is captured and appended as events.

The demo is staged like a short keynote: a title card, one labelled beat per
command, and a closing card. The same content is echoed to stdout, so the script
also works underneath a real recorder (asciinema, terminalizer, ...) on
Unix/macOS/WSL.

Usage:
    python scripts/record_demo.py              # writes demo.cast at the repo root
    python scripts/record_demo.py --out x.cast # custom output path
    python scripts/record_demo.py --no-cast    # only replay to stdout
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WIDTH = 115
HEIGHT = 32
CHAR_DELAY = 0.05  # seconds between typed characters
PRE_OUTPUT_PAUSE = 0.45  # pause after a command is typed, before its output
POST_OUTPUT_PAUSE = 3.4  # pause after output, before the next beat
TITLE_HOLD = 2.4  # how long the title card stays on screen

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
CLEAR = "\x1b[2J\x1b[H"
PROMPT = "\x1b[38;5;252m❯\x1b[0m "  # muted grey, no loud colour
LABEL = "\x1b[38;5;244m"  # dim grey section label

# (section label, command, extra pause after its output)
COMMANDS = [
    (
        "Problem · git blame shows who touched a line, not why",
        "git blame -L 1,5 src/codegraph/cli.py",
        1.0,
    ),
    (
        "Decision · the design decision behind one source line",
        "codegraph why src/codegraph/cli.py:32",
        2.0,
    ),
    (
        "Reasoning · why SQLite, and which alternatives were rejected",
        "codegraph why docs/adr/001-use-sqlite-default.md:1",
        2.0,
    ),
    (
        "Time travel · the code graph at a past date",
        "codegraph graph --at 2026-09-28 --scope src",
        1.5,
    ),
    (
        "Evolution · what decisions changed between two versions",
        "codegraph diff 2026-09-23 2026-10-03",
        1.5,
    ),
]


class CastWriter:
    """Accumulate asciicast v2 events with a running clock and echo them out."""

    def __init__(self) -> None:
        self.events: list[list] = []
        self.now = 0.0

    def write(self, text: str, delay: float = 0.0) -> None:
        """Append an output event (after ``delay`` seconds) and print it."""
        if not text:
            self.now += delay
            return
        self.now += delay
        self.events.append([round(self.now, 6), "o", text])
        sys.stdout.write(text)
        sys.stdout.flush()

    def type_text(self, text: str, delay: float = CHAR_DELAY) -> None:
        """Emit ``text`` one character at a time, as if typed by hand."""
        for char in text:
            self.write(char, delay)

    def sleep(self, seconds: float) -> None:
        """Advance the recording clock without emitting an event."""
        self.now += seconds

    def save(self, path: Path) -> None:
        header = {
            "version": 2,
            "width": WIDTH,
            "height": HEIGHT,
            "timestamp": int(time.time()),
            "title": "CodeGraph — why is this code written this way?",
            "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"},
        }
        lines = [json.dumps(header, ensure_ascii=False)]
        lines.extend(json.dumps(event, ensure_ascii=False) for event in self.events)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _codegraph_exe() -> str:
    """Prefer the project virtualenv's entry point, else fall back to PATH."""
    for candidate in (
        ROOT / ".venv" / "Scripts" / "codegraph.exe",
        ROOT / ".venv" / "bin" / "codegraph",
    ):
        if candidate.exists():
            return str(candidate)
    return shutil.which("codegraph") or "codegraph"


def _to_cast_text(raw: str) -> str:
    """Normalise captured output for terminal playback (LF -> CRLF)."""
    return raw.replace("\r\n", "\n").replace("\n", "\r\n")


def run_command(command: str) -> str:
    """Run one demo command from the repo root and return its output."""
    env = dict(os.environ)
    env["FORCE_COLOR"] = "1"
    env["TERM"] = "xterm-256color"
    env["COLUMNS"] = str(WIDTH)
    env["LINES"] = str(HEIGHT)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    resolved = command
    if command.startswith("codegraph "):
        resolved = f'"{_codegraph_exe()}" {command[len("codegraph "):]}'

    proc = subprocess.run(
        resolved,
        shell=True,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout + proc.stderr


def _title_card(writer: CastWriter) -> None:
    """Type the product name and tagline, hold, then clear the stage."""
    writer.write(CLEAR, 0.8)
    writer.write(BOLD)
    writer.type_text("CodeGraph")
    writer.write(RESET + "\r\n\r\n", 0.7)
    writer.type_text("not just what changed — why it was allowed to change")
    writer.sleep(TITLE_HOLD)
    writer.write(CLEAR, 0.4)


def _closing_card(writer: CastWriter) -> None:
    """Clear, then leave just the name, one line, and the repo URL."""
    writer.write(CLEAR, 0.8)
    writer.write("\r\n\r\n", 0.4)
    writer.write(BOLD + "  CodeGraph" + RESET + "\r\n", 0.5)
    writer.write(LABEL + "  the decision memory layer for your codebase" + RESET + "\r\n", 0.6)
    writer.write("\x1b[38;5;240m  github.com/fourwich/codegraph" + RESET + "\r\n", 1.6)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(ROOT / "demo.cast"),
        help="output .cast path (default: demo.cast at the repo root)",
    )
    parser.add_argument(
        "--no-cast",
        action="store_true",
        help="replay the demo to stdout only, without writing a .cast file",
    )
    args = parser.parse_args()

    # The demo prints box-drawing characters and star ratings; make sure the
    # Windows console does not choke on them.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    writer = CastWriter()
    _title_card(writer)

    for label, command, pause in COMMANDS:
        writer.write(f"{LABEL}  ── {label}{RESET}\r\n", 0.5)
        writer.write("\r\n", 0.2)
        writer.write(PROMPT, 0.4)
        writer.type_text(command)
        writer.write("\r\n", PRE_OUTPUT_PAUSE)

        output = run_command(command)
        writer.write(_to_cast_text(output), 0.2)
        if output and not output.endswith("\n"):
            writer.write("\r\n", 0.1)
        writer.sleep(pause + POST_OUTPUT_PAUSE)

    _closing_card(writer)

    if not args.no_cast:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        writer.save(out_path)
        sys.stdout.write(f"\n\n[demo.cast written to {out_path}]\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()