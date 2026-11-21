# codegraph-why

Ask an AI coding agent **why a line of code is written the way it is**, and get the
answer from the repository's own records — ADRs, changelog entries, commit messages —
instead of a guess reconstructed from the code.

```bash
pip install codegraphx
codegraph index .
```

```bash
codegraph why src/app.py:42      # by location
codegraph why insert_nodes       # by symbol, when you do not know the line
```

The skill teaches the agent when to reach for the command: before editing unfamiliar
code, and whenever a value looks arbitrary (`retryLimit = 3`, a 200ms timeout, an
unusual ordering).

The one rule it enforces: **`found: false` is an answer.** CodeGraph shows a decision
card only when a record states a reason or a rejected alternative. A project that never
wrote down its rationale produces no cards, and the agent says so rather than inventing a
plausible reason.

Install the skill for every agent that reads a skills directory:

```bash
codegraph install-skills           # auto-detects
codegraph install-skills --list    # show the roots
```

- [Project](https://github.com/fourwich/codegraph)
- [Why the answer is sometimes empty](https://github.com/fourwich/codegraph#readme)
