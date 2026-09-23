# Prompt 3 — Architecture overview PDF content

Copy everything below into the agent.

```text
# Task: write Architecture Overview PDF content for CodeGraph

Context: submit to Creator Colosseum. Judges read it in 2 minutes.

Output rules:
- Full English
- One A4 page max
- Clear structure for Google Docs / Word paste
- Include an ASCII architecture diagram (boxes and arrows)
- No markdown tables; use simple indentation

Structure:
1. Title: CodeGraph — Architecture Overview
2. One-line summary
3. Problem (3-4 sentences)
4. Solution: three layers, one graph
5. Architecture (ASCII diagram)
6. Data model (CodeNode / Edge / Decision)
7. Seven commands
8. Tech choices (one reason each)
9. Status (as of submission)
10. Roadmap
11. Sign-off line: Built by a 15-year-old self-taught developer.

Constraints:
- No hype, no fake stars or user counts
- Facts only from the repo:
  - tree-sitter parsing done
  - SQLite storage works
  - 16 tests passing
  - index sample: 18 files / 88 nodes / 915 edges (example; sizes vary)
  - Dgraph backend in progress
  - Web visualization planned

Output the final copy only. No explanations.
```
