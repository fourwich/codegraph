#!/usr/bin/env python
"""Capture the terminal output that the README screenshots are made from.

The README shows four SVGs under `docs/assets/`. They are rendered from the text
files in `docs/assets/captures/`, which this script produces by running the CLI on
this repository. Re-run it after a change that alters output, then re-render:

    python scripts/capture_docs_output.py
    python scripts/render_terminal_svg.py

CI re-renders the SVGs and fails if they no longer match the captures, so a
screenshot cannot silently show something the tool stopped printing.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "docs" / "assets" / "captures"

# Plain text: no ANSI escapes, so the capture is diffable and the SVG can embed it.
# PYTHONIOENCODING is removed so the capture reproduces a stock console; the CLI
# reconfigures its streams to UTF-8, which is why the bytes decode cleanly here.
ENV = {
    key: value
    for key, value in os.environ.items()
    if key != "PYTHONIOENCODING"
} | {"TERM": "dumb", "NO_COLOR": "1", "FORCE_COLOR": "0"}
ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Rich reprints each phase's progress bar on one carriage-returned line, so the
# captured text holds a finished bar per phase ("  Walk Git history    --------
# ---- 100% 0:00:00"). The bar width and elapsed time are not the answer, and they
# differ between a cold and a warm database; keep the phase name, drop the rest.
PROGRESS_TAIL = re.compile(r"\s*[-]{3,}\s+\d+%\s+\d+:\d+:\d+")
# Per-run warnings name commits and line counts; the screenshot is about the graph.
WARNING = re.compile(r"^WARNING .*$", re.MULTILINE)

# `--full` on purpose: an incremental run reports whatever the existing database
# already held ("Commits walked: 0"), which made the same command produce a
# different screenshot on a fresh clone. A full run is deterministic.
JOBS: list[tuple[str, list[str]]] = [
    ("index.txt", ["index", ".", "--depth", "50", "--full"]),
    ("why.txt", ["why", "src/codegraph/storage.py:200"]),
    ("decisions.txt", ["decisions", "--timeline"]),
    ("conflicts.txt", ["conflicts"]),
]


def clean(text: str) -> str:
    """Drop progress-bar frames and per-run warnings from captured output."""
    text = ANSI.sub("", text)
    text = PROGRESS_TAIL.sub("", text)
    text = WARNING.sub("", text)
    lines = [line.rstrip() for line in text.splitlines()]
    # Collapse the blank run left behind by removed warnings, keep inner blanks.
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def main() -> int:
    """Run each command and write its captured output."""
    CAPTURES.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name, args in JOBS:
        # Bytes, not text: the child reconfigures its own stdout to UTF-8, but
        # `text=True` would decode the pipe with the console's code page (GBK here)
        # and turn every `·` into a Chinese character before this script saw it.
        result = subprocess.run(
            [sys.executable, "-m", "codegraph.cli", *args],
            cwd=ROOT,
            env=ENV,
            capture_output=True,
        )
        # `why` exits 0 here; a non-zero exit is still a capture we want to see.
        text = clean(
            result.stdout.decode("utf-8", errors="replace")
            + result.stderr.decode("utf-8", errors="replace")
        )
        if not text.strip():
            print(f"  {name}: EMPTY (exit {result.returncode})", file=sys.stderr)
            failures += 1
            continue
        if "\ufffd" in text:
            print(f"  {name}: output was not decodable as UTF-8", file=sys.stderr)
            failures += 1
            continue
        (CAPTURES / name).write_text(text, encoding="utf-8", newline="")
        print(f"  {name}: {len(text.splitlines())} lines (exit {result.returncode})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
