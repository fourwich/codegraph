#!/usr/bin/env bash
# One-click CodeGraph demo recording (Linux / macOS / WSL).
#
# Uses a real asciinema recording when the CLI is installed, otherwise falls
# back to the self-contained cast generator (which is what Windows needs).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=python3
if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
fi

if command -v asciinema >/dev/null 2>&1; then
    echo "Recording a live session with asciinema -> demo.cast"
    asciinema rec demo.cast --overwrite --command "$PY scripts/record_demo.py --no-cast"
else
    echo "asciinema not found; generating demo.cast directly"
    "$PY" scripts/record_demo.py
fi

echo
echo "  Cast   : $(pwd)/demo.cast"
echo "  Page   : $(pwd)/demo.html  (published as /codegraph/demo.html)"
echo "  Upload : asciinema upload demo.cast"