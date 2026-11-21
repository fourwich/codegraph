"""CodeGraph: Python package for the decision memory layer of your codebase."""

import sys
from importlib.metadata import PackageNotFoundError, version


def _version_from_pyproject() -> str | None:
    """Read the version from a sibling `pyproject.toml`, for an uninstalled checkout.

    Returns None when there is no manifest to read, so the caller can fall back to a
    value that is obviously not a release.
    """
    from pathlib import Path

    manifest = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    if not manifest.is_file():
        return None
    try:
        import tomllib

        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    candidate = data.get("project", {}).get("version")
    return candidate if isinstance(candidate, str) else None


try:
    # The installed distribution is the only place the version is written down. A
    # second hardcoded copy drifts: `pyproject.toml` said 0.2.0 while this module still
    # reported 0.1.0, so `codegraph --version` disagreed with the package a user had
    # just installed.
    __version__ = version("codegraphx")
except PackageNotFoundError:  # a source tree that was never installed
    __version__ = _version_from_pyproject() or "0.0.0+source"


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
