# 5-minute pitch script

Target: **4:45** spoken + demo footage. Recorded in one take is fine; the shot
list below is what should be on screen at each moment.

Rubric mapping (the competition weighs Effort 40%, Feasibility 25%, Impact 25%,
Communication 10%):

| Segment | Time | Rubric |
|---|---|---|
| 1. The question nobody answers | 0:00–0:40 | Impact, Communication |
| 2. Live demo | 0:40–2:05 | Feasibility, Communication |
| 3. How it works | 2:05–3:00 | Feasibility |
| 4. What review broke, and what I cut | 3:00–4:05 | **Effort** |
| 5. Verified numbers + close | 4:05–4:45 | Effort, Impact |

Preparation:
- `codegraph index .` already run in the repo; the DB is warm.
- Terminal at a readable size (~14 pt, dark theme), font with clear box drawing.
- `docs/case-study.md` and the GitHub Actions page open in two browser tabs.
- Record 1920×1080, then burn subtitles (the repo has the burn scripts).

---

## 1. The question nobody answers (0:00–0:40)

**On screen:** a file with `const retryLimit = 3;` highlighted, then `git blame`
on that line showing a name and a date.

> Git blame tells you **who** last touched this line. It cannot tell you **why**
> the limit is three and not five.
>
> I'm fifteen. When I read code, the reason is usually somewhere: a commit
> message, an ADR nobody updated, a PR comment from two years ago. It exists —
> it's just not attached to the line.
>
> So I built CodeGraph: it treats design decisions as data, and connects each one
> to the exact line it justifies.

**On screen:** cut to the decision card.

---

## 2. Live demo (0:40–2:05)

**On screen:** terminal, typing `codegraph index .` (show the summary lines only),
then `codegraph why src/codegraph/storage.py:200`.

> One command builds the graph. Structure from tree-sitter, history from Git
> commits, decisions from commit bodies, ADRs and CHANGELOGs.
>
> Now the question from the beginning: why is this line here?

**On screen:** the decision card renders — `[Decision]`, `[Reason]`,
`[Alternatives]`, `[Source]` with a commit SHA.

> It gives me the decision, the stated reason, the rejected alternative, and the
> commit that introduced it. Checkable, not guessed. This one resolves through an
> ADR that declares which code it governs.

**On screen:** `codegraph graph --at 2026-09-01 --scope src`, then the web UI at
`codegraph serve` with the timeline slider moving back.

> The graph is versioned. Every node carries `valid_from` and `valid_to` from real
> commits, so I can ask what the codebase looked like at any past date — nodes
> **and** edges, since an edge only counts when both ends are alive.
>
> And when the record doesn't exist, it says so instead of inventing something.

**On screen:** `codegraph why` on a line with no decision → "No decision record found".

---

## 3. How it works (2:05–3:00)

**On screen:** the architecture diagram (`submission/codegraph-architecture.pdf`),
one slide.

> Three layers, one store.
>
> Structure: seven languages, one `BaseParser` contract — TypeScript, JavaScript,
> Python, Java, Go, Rust, C++. Language files only map AST kinds to
> function/class; no language logic leaks into storage.
>
> Time: nodes are versioned from Git history, so time travel is a SQL predicate,
> not a re-index.
>
> Decisions: rule-based extraction. A record is only a *decision* if it states a
> reason ("because…") or a rejected alternative ("instead of…"). Everything else
> stays as history, hidden by default.
>
> SQLite, a CLI, a local web UI, and a VSCode extension. No server, no Docker.

---

## 4. What review broke, and what I cut (3:00–4:05)

**On screen:** GitHub Actions pages — the red run history, then the green matrix.

> The most useful thing that happened to this project was a third-party review that
> found twenty-two real problems in an hour.
>
> The worst: running `index` twice destroyed the graph. The indexer skipped
> already-indexed commits but cleared the tables first — 7027 nodes became 1871, and
> every node lost its history. And the CI had been red since September 24th, so
> mypy and pytest had never actually run there.
>
> I fixed both, and then changed how I verify numbers: a script now compares every
> "N tests" claim in the docs against `pytest --collect-only`, and CI fails if they
> disagree. All six CI jobs are green now — Ubuntu, Windows, macOS.

**On screen:** `git log --oneline` over the fix commits, then ADR-006.

> And I deleted a feature I was proud of. I had built a Dgraph backend because
> "graph database" sounded like the right answer. A review showed it added five
> hundred lines and no command ever used it. It's gone, and ADR-006 explains why —
> a decision record about removing code.

**On screen:** the precision numbers from `docs/extraction-recall.md`.

> The same honesty applies to the product: on Express.js, 204 records reduce to
> **5 decisions** that actually explain a choice. A small checkable number beats a
> large impressive one.

---

## 5. Verified numbers + close (4:05–4:45)

**On screen:** README status block and the live site.

> Today: 154 tests, 84% coverage, 8 commands, 7 languages, and a green CI matrix.
> Every number in the README is measured by a script, not typed by hand.
>
> What's next is publishing to PyPI so `pip install` works without cloning, and
> widening decision extraction to projects that never wrote an ADR.
>
> Git blame tells you who changed it. CodeGraph tells you why.

---

## Optional 30-second cut (if the submission wants short)

> Git blame tells you who changed it, not why. CodeGraph answers "why is this line
> here?" with a decision card: the reason, the rejected alternative, and the commit
> that introduced it. It parses seven languages, versions the graph from real Git
> history so you can query any past date, and stays silent when no decision was
> ever recorded. 154 tests, an honest precision number on Express.js, and a green
> CI matrix. Decisions as data, not lost chat history.
