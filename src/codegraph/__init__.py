"""CodeGraph: Python package for the decision memory layer of your codebase."""

import sys

__version__ = "0.1.0"


def make_console_streams_safe() -> None:
    """Make console output safe on a non-UTF-8 console.

    Chinese Windows defaults to GBK. Two distinct failures come from that:

    * An emoji or a character GBK cannot encode (`•`, `✅`) raises
      `UnicodeEncodeError` and kills the command.
    * A character GBK *can* encode still comes out as mojibake when the bytes are
      read back as UTF-8 — `·` renders as `路` in a redirected file or a CI log,
      which is exactly the noise that makes output look broken.

    Reconfiguring the stream to UTF-8 fixes both, since every character in the
    output is then encodable and readable. When the stream cannot be reconfigured
    (an already-wrapped object, a closed pipe) `errors="replace"` at least keeps
    the command alive instead of dying mid-card.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            try:
                reconfigure(errors="replace")
            except (AttributeError, ValueError, OSError):
                continue


make_console_streams_safe()
