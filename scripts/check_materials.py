"""Fail when a material advertises a test count that pytest does not produce.

Three separate rounds of this project shipped docs quoting a stale number, so the
number is now checked rather than typed. Run by CI, and by hand before publishing.

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

PATTERN = re.compile(r"(?<![\w.])(\d+)\s+(?:tests?(?:\s+passing)?|passing tests)", re.IGNORECASE)


def material_files() -> list[Path]:
    """Every published file that may quote a test count."""
    files = [ROOT / "README.md", ROOT / "index.html"]
    files.extend(sorted((ROOT / "docs").rglob("*.md")))
    return [p for p in files if p.is_file() and p.name not in SKIP]


def collected_test_count() -> int:
    """Number of tests pytest collects."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    match = re.search(r"(\d+)\s+tests?\s+collected", result.stdout)
    if match is None:
        print("Could not read the collected test count:", file=sys.stderr)
        print(result.stdout[-2000:], file=sys.stderr)
        raise SystemExit(2)
    return int(match.group(1))


def main() -> int:
    """Check (or fix) every test-count claim."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Rewrite stale numbers in place")
    args = parser.parse_args()

    expected = collected_test_count()
    stale: list[tuple[Path, int, str]] = []

    for path in material_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        changed = False
        for index, line in enumerate(lines):
            for match in PATTERN.finditer(line):
                if int(match.group(1)) == expected:
                    continue
                stale.append((path, index + 1, line.strip()))
                if args.fix:
                    lines[index] = line[: match.start(1)] + str(expected) + line[match.end(1) :]
                    changed = True
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")

    if not stale:
        print(f"All materials report {expected} tests.")
        return 0

    for path, line_number, line in stale:
        print(f"{path.relative_to(ROOT)}:{line_number}: {line[:110]}")
    if args.fix:
        print(f"\nRewrote {len(stale)} claim(s) to {expected} tests.")
        return 0
    print(f"\n{len(stale)} claim(s) disagree with pytest ({expected} tests). Run with --fix.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
