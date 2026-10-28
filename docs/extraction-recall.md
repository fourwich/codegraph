# Decision extraction: recall and precision

Rules stay non-LLM. The extractor produces two kinds of record:

| Tier | Meaning | Shown by default |
|---|---|---|
| `decision` | States a reason (`because …`, `to fix …`) or a rejected alternative (`instead of X`) | yes |
| `event` | Plain history: a commit subject, a release-note line | no (`--include-events`) |

Dependency records carry `category = dependency` and are hidden too, unless they
state a reason — in which case they are dependency **decisions**.

## What changed in the precision pass

1. A commit subject is no longer a decision by default. It becomes one only when
   it states a reason or a rejected alternative. `feat: use the new logo` is an
   event; `refactor: use node:buffer instead of safe-buffer` is a decision.
2. Reasons are required, not implied. A fragment with a keyword but no
   `because / so that / to fix / …` clause is an event.
3. Keywords were narrowed. `since`, `reason`, `must be`, `should not`,
   `to support`, `to keep`, `to match`, `to improve`, bare `avoid`, bare
   `replaced` matched ordinary English and were removed.
4. A dependency bump that says why is upgraded:
   `deps: bump body-parser to ^2.3.0 to fix CVE-2026-12590` → dependency
   decision at 0.65; `bump morgan from 1.12.0 to 1.12.1` → dependency event.
5. `instead of X` / `rather than X` populate `alternatives` instead of being
   folded into the decision text.
6. The whole commit message is no longer scanned *and* its subject *and* its
   body: that triple emission double counted the same sentence. Records are now
   de-duplicated by `(source_ref, content)` keeping the richer of the two.
7. uids use a blake2b fingerprint, so they are reproducible across processes.

## Measured (reproduce with `scripts/eval_decision_precision.py`)

| Project | Depth | Records | Decisions | Decision share | With reason | With alternative |
|---|---|---|---|---|---|---|
| sindresorhus/got | 200 | 237 | **36** | 15.2% | 12 | 25 |
| expressjs/express | 200 | 204 | **5** | 2.5% | 2 | 3 |
| CodeGraph self | 50 | 70 | **14** | 20.0% | 9 | 10 |

`got` and `express` bracket the product's actual range, which is why both are
here rather than only the flattering one. Express writes free-form commit
subjects, so only 5 of 204 records carry a rationale. `got` writes conventional
commits whose bodies explain the change, so 36 of 237 records (15.2%) are real
decisions without any extra configuration — the extractor is not tuned per
repository.

The Express row is the stable reference. The self row was measured on this
repository at its current HEAD and drifts with every commit made here — the
number to trust is the one the script prints now.

The old headline was "174 decisions on Express". Under the tier model the same
run yields 204 records of which **5** are decisions: precision went up, and the
number went down, which is the point.

The self repo's 14 decisions are 6 ADRs, 7 CHANGELOG entries and 1 commit body —
sources that are handwritten rather than scraped from commit subjects, which is
also why they are all reachable from `why`.

## Recall note

Earlier work raised Express recall from 109 to 174 records (+60%) by treating
every conventional-commit subject as a decision. That traded precision for a
bigger number and has been reverted: those 199 extra records are now events,
still stored, still queryable with `--include-events`, but never presented as
answers.

## Binding (what `why` can actually reach)

A record is only useful if a query can find it.

| Source | Binding rule |
|---|---|
| commit decision | changed lines of that commit that land inside a CodeNode |
| commit decision spanning > 10 files or > 250 lines | no line links; reachable through the commit-level fallback only |
| ADR / CHANGELOG decision | `governs:` declaration → backticked path → distinctive backticked identifier |

Adding `<!-- governs: src/... -->` (or `governs: src/...` front matter) is the
cheapest way to make an ADR answer for the code it describes. In this repository
12 of the 14 decision-tier records have line links: 4 ADRs through their
`governs:` declaration, and the CHANGELOG entries through the lines they touched.
So `why src/codegraph/storage.py:200` returns ADR-001 instead of nothing. The two
unbound ADRs (server-side sessions vs stateless JWT) are a deliberate conflicting
pair that governs no code.

Line links per repository, same index run:

| | before | after |
|---|---|---|
| `decision_code_links` rows | 9323 | 2588 |
| widest single record | 3233 links / 46 files | 240 links / 4 files |

Express tells a different story, and it is worth stating plainly: all 199 of its
`decision_code_links` rows belong to **event**-tier records. Its 5 decisions have
**0 line links**, so `why` reaches them through the commit- or file-level fallback
only — `why lib/response.js:229` reports `binding: file-level decision`. On a
repository with ADRs, line-level answers are the common case; on a repository
without them, they are rare.

## Conflict precision

`codegraph conflicts` used raw substring matching: `use` fired inside `because`,
`sync` inside `async`, and any two decisions in one folder could be reported as
contradictory. On this repository that produced **5 conflicts, 4 of them false**.

Now opposite terms match on word boundaries, the two decisions must share a file
(or a folder *and* vocabulary), and the generic pairs (`add`/`remove`,
`keep`/`drop`) only count when the topic really overlaps. Temporal conflicts
additionally require opposite terms — being close in time is not a contradiction.
Result on this repository: **1 conflict**, the deliberate stateful-vs-stateless
pair in `docs/adr/004` vs `docs/adr/005`.

## Sample decisions now captured on Express

- `use node:buffer` — alternative: `safe-buffer (#6071)`
- `values at parser initialization` — alternative: `failing open`
- `deps: bump body-parser to ^2.3.0` — reason: `to fix CVE-2026-12590 (#7390)`
- `Configure dependabot … to reduce noise` — reason: `to avoid errors from version mismatches`
- `Update multiple links to use `https`` — alternative: `` `http` (#6338)`
