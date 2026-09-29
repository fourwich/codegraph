# Case Study: CodeGraph on Express.js

## Why this project

Express is one of the most widely used Node.js web frameworks. Its Git history spans over a decade with real architectural decisions and a dense TypeScript-less JavaScript codebase — a good stress test after adding JS parsing.

## Index results

- Repository: https://github.com/expressjs/express
- Clone: `--depth 200` (200 most recent commits)
- Commits indexed: **200**
- Files parsed: JavaScript under `lib/`, `examples/`, root
- Nodes: **7027**
- Edges: **1180**
- Decisions extracted: **109**
- Languages: JavaScript (`.js` / `.mjs` / `.cjs`)
- Index wall time: **45.8 s** (includes historical snapshots)

## What CodeGraph reveals

### 1. Decision provenance

```text
$ codegraph why lib/application.js:50
Query lib/application.js:50 → 1 matched file-level decision(s)

Decision #1: use cached slice in app.listen (#6897)
  binding: file-level decision
  [Source] commit 54af593b739ea44674e4a445efa15b8024f093da
           author: TheMysterious · date: 2025-11-23
  [Status] active
```

The decision is tied to the real commit that changed `app.listen`, not a canned sample. Line-level binding lands when the query line falls inside a function whose range includes diff lines from that commit.

### 2. Structure at a past moment

```text
$ codegraph graph --at 2026-07-01 --scope lib
Nodes     550
Edges     110   (both endpoints live at that date)
Decisions 11

# vs 2026-09-28
Nodes     627
Edges     110
Decisions 13
```

Time travel shows `lib/` growing over the summer (550 → 627 node versions) while decision count stays small — most commits do not carry rationale keywords.

### 3. Decision evolution (diff)

```text
$ codegraph diff 2026-07-05 2026-09-28 --scope lib
+ ADDED  clean up deprecated back string references (#7406)  · 2026-08-22
+ ADDED  preserve ETag generation with Transfer-Encoding...  · 2026-09-15
Summary: 2 added · 0 changed · 0 removed · 0 superseded
```

### 4. Conflicts

```text
$ codegraph conflicts --scope lib
No conflicts detected in scope=lib
```

Honest result: Express `lib/` did not produce contradictory accepted decisions under the current opposite-word / supersede / temporal rules.

## Limitations observed

- Express commit messages often lack *because / since / instead of* wording, so many commits contribute only weak conventional-subject decisions.
- `why lib/router/index.js:100` returned no decision when that exact line was not inside a linked node range in this shallow history.
- `--format` date refs must match a calendar day that contains a commit; arbitrary mid-week dates can return "No commit found".
- Pure JS examples outside `lib/` inflate node counts with require/import identifiers (variable nodes).
- Structural completeness is the win: **0 nodes before JS support → 7027 nodes after**.

## Reproduce

```bash
git clone --depth 200 https://github.com/expressjs/express.git
cd express
codegraph index . --depth 200
codegraph why lib/application.js:50
codegraph graph --at 2026-07-01 --scope lib
codegraph diff 2026-07-05 2026-09-28 --scope lib
```
