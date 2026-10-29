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
| pallets/flask | 200 | 229 | **54** | 23.6% | 18 | 37 |
| spf13/cobra | 200 | 217 | **12** | 5.5% | 8 | 4 |
| expressjs/express | 200 | 242 | **22** | 9.1% | 14 | 8 |
| google/gson | 200 | 223 | **29** | 13.0% | 19 | 10 |
| CodeGraph self | 50 | 81 | **20** | 24.7% | 11 | 15 |

The five projects bracket the product's actual range, which is why all of them
are here rather than only the flattering one. Express writes free-form commit
subjects, so 22 of its 242 records carry a rationale — and 17 of those 22 come
from its own `History.md`, which states reasons in release notes. `got` writes
conventional commits whose bodies explain the change: 36 of 237. Flask documents
every release in `CHANGES.rst`, a reStructuredText file, so 54 of 229 records
state a reason or a rejected alternative. Cobra is the other direction again —
short Go commit subjects, terse notes — and only 12 of 217. Gson sits in between:
29 of 223, ten of them read from javadoc comments that explain a design choice.
None of the five is configured for: the extractor reads what the project already
writes down. Five projects across TypeScript, JavaScript, Python, Go and Java also
exercise five of the seven parsers end to end on real code.

The flask row is also a bug report: before `CHANGES.rst` support existed, the
same checkout produced **one** decision, because the extractor looked only at
`CHANGELOG.md` under a `## Changed` heading. Real Python projects ship neither.

The Express row is the stable reference. The self row was measured on this
repository at its current HEAD and drifts with every commit made here — the
number to trust is the one the script prints now.

The old headline was "174 decisions on Express". Under the tier model that run
yields 242 records of which **22** are decisions — and the 22 are the ones that
state a reason or a rejected alternative, mostly in Express's own changelog. The
number fell from 174 to 22 because the other 220 records are history, not choices.

The self repo's 20 decisions are 6 ADRs, 11 CHANGELOG entries and 3 commit bodies —
sources that are handwritten rather than scraped from commit subjects, which is
also why most of them are reachable from `why`.

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
17 of the 20 decision-tier records have line links: 4 ADRs through their
`governs:` declaration, and the CHANGELOG entries through the lines they touched.
So `why src/codegraph/storage.py:200` returns ADR-001 instead of nothing. The two
unbound ADRs (server-side sessions vs stateless JWT) are a deliberate conflicting
pair that governs no code.

Line links per repository, same index run:

| | before | after |
|---|---|---|
| `decision_code_links` rows | 9323 | 3094 |
| widest single record | 3233 links / 46 files | 240 links / 4 files |

Binding is the weakest part of a changelog-only corpus: Flask has 54 decisions and
only **10** of them carry a line link. A release note that says "use `flit_core`
instead of `setuptools`" names no file, so there is nothing to link to; one that
backticks a symbol does bind when that name is unique in the graph (`` `redirect` ``
binds, a word shared by several files like `` `send` `` does not). The rest stay
queryable from `CHANGES.rst` itself, and `why` on a code line in Flask mostly
answers "no record" — the honest limit of reading rationale from prose that does
not point at code.

Express used to be the counter-example: 5 decisions and **0** line links, every
one of its 199 `decision_code_links` rows belonging to an event. Reading its
`History.md` changed that — 17 of its 22 decisions now bind, because the release
notes name `encodeurl`, `body-parser` and friends. The lesson is about the input,
not the binder: prose that names a symbol binds; prose that describes behaviour
without naming anything does not.

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

Zero conflicts on a repository is only meaningful if the detector could have found
something. `scripts/eval_conflict_precision.py` reports the reported conflicts *and*
every same-place pair that matched an opposite term but was rejected by the topic
gate, so "nothing here" and "cannot see it" are distinguishable:

| Repository | Decisions | Conflicts | Same-place pairs | Pairs with opposite terms | Rejected by topic gate |
|---|---|---|---|---|---|
| CodeGraph self | 20 | **1** | 93 | 1 | 0 |
| expressjs/express | 21 | 0 | 153 | 0 | 0 |
| pallets/flask | 54 | 0 | 1431 | 0 | 0 |
| sindresorhus/got | 36 | 0 | 229 | 3 | **3** |
| spf13/cobra | 12 | 0 | 11 | 0 | 0 |

Flask is the interesting row: 1431 pairs of decisions in one file and not one pair
uses opposite vocabulary, because its records are release notes rather than
competing choices. `got` is the calibration check — three pairs share
`always`/`never`, and all three are correctly rejected with a topic overlap of
0.00–0.14 (`Infinity` stays a valid "never" count is not the opposite of starting
a timeout). The detector is quiet because the corpus is quiet, not because it is
blind.

## Sample decisions now captured on Express

- `use node:buffer` — alternative: `safe-buffer (#6071)`
- `values at parser initialization` — alternative: `failing open`
- `deps: bump body-parser to ^2.3.0` — reason: `to fix CVE-2026-12590 (#7390)`
- `Configure dependabot … to reduce noise` — reason: `to avoid errors from version mismatches`
- `Update multiple links to use `https`` — alternative: `` `http` (#6338)`
