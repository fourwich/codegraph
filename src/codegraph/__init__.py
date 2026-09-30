"""CodeGraph: Python package for the decision memory layer of your codebase."""

import sys

__version__ = "0.1.0"


def make_console_streams_safe() -> None:
    """Stop UnicodeEncodeError on consoles that are not UTF-8.

    Chinese Windows defaults to GBK, and legacy Windows consoles render Rich
    output through the same stream; without this, a card containing an emoji
    crashes the command with `UnicodeEncodeError`.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            continue


make_console_streams_safe()
