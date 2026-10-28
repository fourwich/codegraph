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


def collected_test_count() -> int:
    """Number of tests pytest collects."""
    stdout = _pytest(["--collect-only", "-q"])
    match = re.search(r"(\d+)\s+tests?\s+collected", stdout)
    if match is None:
        print("Could not read the collected test count:", file=sys.stderr)
        print(stdout[-2000:], file=sys.stderr)
        raise SystemExit(2)
    return int(match.group(1))


def coverage_percent() -> int:
    """Total statement coverage of src/codegraph, as pytest reports it."""
    stdout = _pytest(
        ["-q", "--cov=src/codegraph", "--cov-report=term", "-m", "not dgraph"]
    )
    match = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout, re.MULTILINE)
    if match is None:
        print("Could not read the coverage total:", file=sys.stderr)
        print(stdout[-2000:], file=sys.stderr)
        raise SystemExit(2)
    return int(match.group(1))


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

    for path in material_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        changed = False
        for index, line in enumerate(lines):
            for metric, patterns in CLAIM_PATTERNS.items():
                for pattern in patterns:
                    for match in pattern.finditer(line):
                        if int(match.group(1)) == expected[metric]:
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

    if not stale:
        print(
            f"All materials report {expected['tests']} tests and "
            f"{expected['coverage']}% coverage."
        )
        return 0

    for path, line_number, line in stale:
        print(f"{path.relative_to(ROOT)}:{line_number}: {line[:110]}")
    if args.fix:
        print(f"\nRewrote {len(stale)} claim(s).")
        return 0
    print(
        f"\n{len(stale)} claim(s) disagree with pytest "
        f"({expected['tests']} tests, {expected['coverage']}% coverage). Run with --fix."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
