"""Fail when a material advertises a number that pytest does not produce.

Three separate rounds of this project shipped docs quoting a stale test count, and
the coverage figure drifted the same way. Both are now checked rather than typed:
run by CI, and by hand before publishing.

Usage:
    python scripts/check_materials.py
    python scripts/check_materials.py --fix   # rewrite the stale numbers
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Historical notes keep the numbers that were true when they were written.
SKIP = {"release_notes_v0.1.0.md"}

# Two shapes are in use for the test count: prose ("154 tests passing") and the
# shields.io URL ("tests-154%20passing"), which a word-boundary pattern misses.
CLAIM_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "tests": (
        re.compile(
            r"(?<![\w.])(\d+)\s+(?:tests?(?:\s+passing)?|passing tests)", re.IGNORECASE
        ),
        re.compile(r"tests-(\d+)%20passing"),
    ),
    "coverage": (
        re.compile(r"(?<![\w.])(\d+)%\s*coverage", re.IGNORECASE),
        re.compile(r"coverage\s*(\d+)%", re.IGNORECASE),
    ),
}


def material_files() -> list[Path]:
    """Every published file that may quote a measured number."""
    files = [ROOT / "README.md", ROOT / "index.html"]
    files.extend(sorted((ROOT / "docs").rglob("*.md")))
    return [p for p in files if p.is_file() and p.name not in SKIP]


def _pytest(args: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def _fresh(path: Path) -> bool:
    """True when the artifact is newer than every source file it should describe.

    CI writes these files minutes before the check runs. Locally they can be
    left over from an earlier run, and reading a stale `tests.xml` would validate
    a number that no longer exists.
    """
    if not path.is_file():
        return False
    sources = list((ROOT / "tests").rglob("*.py")) + list((ROOT / "src").rglob("*.py"))
    newest_source = max((p.stat().st_mtime for p in sources), default=0)
    return path.stat().st_mtime >= newest_source


def _junit_test_count(path: Path) -> int | None:
    """Test count from a JUnit report written by the run that just happened."""
    if not _fresh(path):
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    count = len(re.findall(r"<testcase\b", text))
    return count or None


def _coverage_from_xml(path: Path) -> int | None:
    """Coverage percentage from the coverage.xml of the run that just happened."""
    if not _fresh(path):
        return None
    match = re.search(
        r'line-rate="([0-9.]+)"', path.read_text(encoding="utf-8", errors="replace")
    )
    if match is None:
        return None
    return round(float(match.group(1)) * 100)


def collected_test_count() -> int:
    """Number of tests that ran (JUnit report when present, else a collect run).

    The fallback must select the same tests CI runs. Without the marker filter it
    counted the `dgraph` tests too (212), while the docs quote the number CI
    actually runs (207), so the check failed on Linux — where no JUnit artifact
    was present — and passed locally, where one was.
    """
    from_junit = _junit_test_count(ROOT / "tests.xml")
    if from_junit is not None:
        return from_junit
    stdout = _pytest(["--collect-only", "-q", "-m", "not dgraph"])
    match = re.search(r"(\d+)\s+tests?\s+collected", stdout)
    if match is None:
        _diagnose("Could not read the collected test count", stdout)
    return int(match.group(1))  # type: ignore[union-attr]


def coverage_percent() -> int:
    """Total statement coverage (coverage.xml when present, else a full run)."""
    from_xml = _coverage_from_xml(ROOT / "coverage.xml")
    if from_xml is not None:
        return from_xml
    stdout = _pytest(
        ["-q", "--cov=src/codegraph", "--cov-report=term", "-m", "not dgraph"]
    )
    match = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout, re.MULTILINE)
    if match is None:
        _diagnose("Could not read the coverage total", stdout)
    return int(match.group(1))  # type: ignore[union-attr]


def _diagnose(message: str, stdout: str) -> None:
    """Report an unreadable measurement on the run summary, then stop."""
    detail = f"{message}\n\n```\n{stdout[-1500:]}\n```"
    print(message, file=sys.stderr)
    print(stdout[-2000:], file=sys.stderr)
    _summary(detail)
    raise SystemExit(2)


def _summary(text: str) -> None:
    """Append to the GitHub Actions run summary when running there."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    except OSError:
        pass


def _annotate(message: str) -> None:
    """Surface a failure as a GitHub Actions annotation (visible without log auth)."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error title=Materials::{message}")
    _summary(f"- {message}")


def main() -> int:
    """Check (or fix) every measured-number claim."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Rewrite stale numbers in place")
    args = parser.parse_args()

    expected = {
        "tests": collected_test_count(),
        "coverage": coverage_percent(),
    }
    stale: list[tuple[Path, int, str]] = []

    def disagrees(metric: str, claim: int) -> bool:
        # A coverage claim is a floor ("over 80%"), not an exact figure: the exact
        # total differs slightly between platforms, and claiming less than the
        # measurement is the conservative, honest direction.
        if metric == "coverage":
            return expected[metric] < claim
        return claim != expected[metric]

    for path in material_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        changed = False
        for index, line in enumerate(lines):
            for metric, patterns in CLAIM_PATTERNS.items():
                for pattern in patterns:
                    for match in pattern.finditer(line):
                        if not disagrees(metric, int(match.group(1))):
                            continue
                        stale.append((path, index + 1, line.strip()))
                        if args.fix:
                            lines[index] = (
                                line[: match.start(1)]
                                + str(expected[metric])
                                + line[match.end(1) :]
                            )
                            changed = True
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")

    measured = f"{expected['tests']} tests, {expected['coverage']}% coverage"
    if not stale:
        print(f"All materials agree with pytest ({measured}).")
        return 0

    for path, line_number, line in stale:
        print(f"{path.relative_to(ROOT)}:{line_number}: {line[:110]}")
    if args.fix:
        print(f"\nRewrote {len(stale)} claim(s) to {measured}.")
        return 0
    summary = f"{len(stale)} claim(s) disagree with pytest ({measured})"
    print(f"\n{summary}. Run with --fix.")
    _annotate(summary)
    for path, line_number, line in stale[:5]:
        _annotate(f"{path.relative_to(ROOT)}:{line_number}: {line[:100]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
