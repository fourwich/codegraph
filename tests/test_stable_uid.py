"""Decision uids must be reproducible across processes.

Python's str hash is salted per process, so a uid built from `hash(content)`
changes on every run. That breaks incremental indexing, dedup and `diff`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from codegraph.decisions.extractor import content_fingerprint, decision_from_sentence
from codegraph.models import DecisionSource

REPO_ROOT = Path(__file__).resolve().parents[1]

_CHILD = """
import sys
from datetime import datetime, timezone
from codegraph.decisions.extractor import decision_from_sentence
from codegraph.models import DecisionSource

decision = decision_from_sentence(
    "Use SQLite because it is embedded and needs no server",
    source=DecisionSource.COMMIT,
    source_ref="commit abc",
    timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    uid_prefix="commit",
)
sys.stdout.write(decision.uid)
"""


def test_content_fingerprint_is_stable() -> None:
    """Whitespace and case do not change the fingerprint."""
    assert content_fingerprint("Use  SQLite\nbecause") == content_fingerprint(
        "use sqlite because"
    )
    assert re.fullmatch(r"[0-9a-f]{8}", content_fingerprint("x"))


def test_decision_uid_is_reproducible() -> None:
    """The same sentence yields the same uid under different hash seeds."""
    outputs = []
    for seed in ("0", "1", "12345"):
        env = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": str(REPO_ROOT / "src"),
        }
        result = subprocess.run(
            [sys.executable, "-c", _CHILD],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout.strip())

    assert len(set(outputs)) == 1, outputs
    assert re.search(r"::[0-9a-f]{8}$", outputs[0])

    # Same process, called twice: identical too.
    kwargs = dict(
        source=DecisionSource.COMMIT,
        source_ref="commit abc",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        uid_prefix="commit",
    )
    first = decision_from_sentence("Use SQLite because it is embedded", **kwargs)
    second = decision_from_sentence("Use SQLite because it is embedded", **kwargs)
    assert first.uid == second.uid
