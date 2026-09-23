# Prompt 7 — CONTRIBUTING + issue/PR templates

Copy everything below into the agent.

```text
# Task: write CONTRIBUTING.md and GitHub templates for CodeGraph

Repo: https://github.com/fourwich/codegraph

## A. CONTRIBUTING.md
1. Welcome (one line)
2. Ways to contribute
3. Development setup (clone, venv, pip install -e ".[dev]", tests)
4. Code style (ruff + mypy; commit type(scope): subject)
5. Pull request process
6. Short code of conduct
7. Questions

Rules: English, <= 600 words, friendly tone suitable for a 15-year-old maintainer. Use "I" or "the maintainer", not "our team".

## B. Templates
Create:
.github/ISSUE_TEMPLATE/bug_report.md
  Description / Steps to reproduce / Expected / Actual / Environment
.github/ISSUE_TEMPLATE/feature_request.md
  Problem / Proposed solution / Alternatives / Additional context
.github/PULL_REQUEST_TEMPLATE.md
  What changed / Why / How tested / checklist

Each template <= 80 lines, English.

Output full file contents in order A then B. No explanations.
```
