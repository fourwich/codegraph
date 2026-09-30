# Case Study: CodeGraph on Express.js

## Why this project

Express is one of the most widely used Node.js web frameworks. Its Git history spans over a decade with real architectural decisions and a dense TypeScript-less JavaScript codebase — a good stress test after adding JS parsing.

## Index results

- Repository: https://github.com/expressjs/express
- Clone: `--depth 200` (200 most recent commits)
- Commits indexed: **200**
- Files parsed: JavaScript under `lib/`, `examples/`, root
- Nodes: **5920** node versions
- Edges: **883** (both endpoints stored)
- Records: **204** = **5 decisions** + **199 history events**
- Languages: JavaScript (`.js` / `.mjs` / `.cjs`)
- Index wall time: **~66 s** (includes historical snapshots)

Two numbers moved after the 2026 correctness pass, both downwards because the old
ones were inflated:

- **Nodes 7027 → 5920.** The old versioning opened a new node version every time
  a commit touched a file, so a symbol that never changed still got a fresh
  version per commit, and sometimes two simultaneously-live versions.
- **Edges 1180 → 883.** About a quarter of the old edges pointed at node uids
  that were never stored, so they could not be traversed or counted anyway.

The record count also changed meaning. Express has **204 extractable records**;
only **5 of them state a reason or a rejected alternative**. The rest are commit
subjects and release-note lines, kept as `event` records and hidden from `why`
and `decisions` unless `--include-events` is passed.

Verify with `python scripts/eval_decision_precision.py <express-clone> --depth 200`.

## What CodeGraph reveals

### 1. Decision provenance

```text
$ codegraph why lib/response.js:229
Matched CodeNode: function ... lib/response.js
Query lib/response.js:229 → 1 matched file-level decision(s)

Decision #1: use node:buffer
  binding: file-level decision
  [Decision]      use node:buffer
  [Reason]        Not recorded
  [Alternatives]  · safe-buffer (#6071)
  [Source] commit c70197ad33057e88565bd7bde6454f9225ead6cc
           author: Bhavya Dhiman · date: 2024-10-27
  [Status] active      [Confidence] 60%
```

This is a real decision with a rejected alternative, from the commit that made
the change. It binds at **file** level, not line level: the commit touched 13
lines across `lib/response.js`.

The commit the case study previously highlighted,
`use cached slice in app.listen (#6897)`, carries no rationale. It is now an
`event`, so `why` reports no decision for that line — and says so:

```text
$ codegraph why lib/application.js:50
No decision record found
1 history record(s) exist for lib/application.js:50 but are not decisions.
  Add --include-events (and --include-dependency) to see them.
```

That is intended: a commit subject is provenance, not an answer.

### 2. Structure at a past moment

```text
$ codegraph graph --at 2026-07-01 --scope lib
Nodes     194      Edges      72      Decisions   1

$ codegraph graph --at 2026-09-28 --scope lib
Nodes     194      Edges      72      Decisions   1
```

`lib/` is structurally flat over this window: the shallow clone's recent commits
are dependency and CI bumps, and `lib/` itself barely moves. The earlier claim
that `lib/` grew 550 → 627 node versions was an artifact of the
duplicate-version bug, and has been withdrawn — the corrected count is stable.

### 3. Decision evolution (diff)

```text
$ codegraph diff 2026-07-05 2026-09-28 --scope lib
+ ADDED  Configure dependabot to group all github actions version updates…  · 2026-09-15
Summary: 1 added · 0 changed · 0 removed · 0 superseded
```

### 4. Conflicts

```text
$ codegraph conflicts --scope lib
No conflicts detected in scope=lib
```

Honest result: Express `lib/` did not produce contradictory accepted decisions under the current opposite-word / supersede / temporal rules.

## Limitations observed

- Express commit messages often lack *because / instead of* wording, so 199 of
  204 records are history events rather than decisions. Precision now costs
  recall: the tool says "I don't know" more often, and that is deliberate.
- 4 of the 5 Express decisions are not bound to a line, so `why` reaches them
  through the file / directory fallback and labels the binding accordingly.
- ADR and CHANGELOG decisions are not bound to code at all yet — they have no
  commit sha and no `file:line`, so `why` cannot surface them. Binding an ADR to
  the files it governs is the next concrete improvement.
- `why lib/router/index.js:100` returned no decision when that exact line was not
  inside a linked node range in this shallow history.
- `--format` date refs must match a calendar day that contains a commit;
  arbitrary mid-week dates can return "No commit found".
- Pure JS examples outside `lib/` inflate node counts with require/import
  identifiers (variable nodes).

## Reproduce

```bash
git clone --depth 200 https://github.com/expressjs/express.git
cd express
codegraph index . --depth 200
python ../scripts/eval_decision_precision.py . --depth 200
codegraph why lib/response.js:229
codegraph graph --at 2026-07-01 --scope lib
codegraph diff 2026-07-05 2026-09-28 --scope lib
```
