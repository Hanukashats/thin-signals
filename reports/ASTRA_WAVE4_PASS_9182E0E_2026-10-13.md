# Independent Wave 4 acceptance — 9182e0e

Date: 2026-10-13 UTC. Independent verifier: `astra-verifier-v5`.

Frozen candidate: `9182e0ea09a17c8a8933c4234710ed67a0400b5a`.
Workspace: `/srv/codex-operator/worktrees/1305367840_1791810532/thin-signals`.
GOAL: `g-df30f33833c7`, independent criterion C05.

## Verdict

**PASS for the bounded deterministic Wave 4 candidate.** No remaining scoped
P0/P1/P2 finding was established. All previously reproduced findings are closed,
including the mixed-action ordering differential. The full repository suite
passes **455 tests** on a newly created, freshly migrated PostgreSQL database.
Review and scoring CLI artifacts regenerate byte-for-byte.

The lead independently exercised prior counterexamples and all eight mixed
CORRECT/NARROW permutations through the runner, direct arbiter and evaluator.
Two read-only reviewers independently checked arbitration and evaluation.
The bounded search stopped after this evidence; it is not an exhaustive proof.

Only this report and the requested verifier disposition are changed by this
audit. The worktree was clean at the exact SHA before inspection and immediately
before writing the report. Product code, datasets, committed evaluation
artifacts, production, remotes and activation flags were not modified.

## Closed findings and boundary checks

| Check | Independently observed result |
|---|---|
| Supported non-primary claim | HOLD / critical_claim_unattested, without role errors |
| Unrelated non-critical primary evidence | Cannot cover an unattested critical claim; HOLD |
| Actual ablations | 96 instrumented runner executions: 32 each for proposed/no_defender/no_control |
| Repeated stability | Two actual executions per case/path; decisions and ledger revisions match |
| Invalid scoring baseline confidence or label | Actual subprocess exit 2; stdout/artifact valid=false; one mismatch; report INVALID |
| Negative or malformed independence trace | Actual subprocess exit 1; no summary artifact |
| Unbound/wrong-evidence control | ADD_EVIDENCE, CORRECT and NARROW all HOLD / invalid_citation |
| Crossed control binding | HOLD / invalid_citation |
| Missing finding | HOLD / unresolved_critical |
| Unknown or noncritical replacement | Both CORRECT/NARROW HOLD; evaluator unresolved_critical=true |
| Second unknown critical claim | HOLD / critical_claim_unknown |
| Provider-failure ablation | Critic failure retained alongside the unavailable role; 300 tokens / $0.002 / 20 fixture ms |
| Superseded evidence | Both CORRECT/NARROW with one replacement origin HOLD; origins=1, coverage=false |
| Explicit retained replacement citations | Both CORRECT/NARROW with two primary origins REFRAME; origins=2, coverage=true |
| Valid single additive defense | PROMOTE retained |
| Mixed replacement plus addition | All eight permutations HOLD in runner and direct arbiter; evaluated origins=0, coverage=false, unresolved=true |
| Replacement targets/identities | Duplicate rewrites and identity collisions remain fail-closed |

For both CORRECT and NARROW, critic and defender lists were reversed
independently. The previously failing table is now invariant:

| Critic order | Defender order | Runner | Direct arbiter | Evaluated origins / covered |
|---|---|---|---|---|
| Replacement, ADD | Replacement, ADD | HOLD | HOLD | 0 / false |
| Replacement, ADD | ADD, replacement | HOLD | HOLD | 0 / false |
| ADD, replacement | Replacement, ADD | HOLD | HOLD | 0 / false |
| ADD, replacement | ADD, replacement | HOLD | HOLD | 0 / false |

The runner reports defender `invalid_role_output`; its dependent control
record is invalid too. The direct arbiter reports `ambiguous_claim_rewrite`.
Every evaluated permutation is stable and unresolved-critical. This agrees
with ADR-014: an unordered replacement plus any other defense for the original
claim has no implicit precedence. The fix rejects that ambiguity without
removing valid single-action positive cases.

The prior exact reproduction is retained in
`reports/ASTRA_WAVE4_FAIL_3AE2BDC_2026-10-13.md`. Re-running its fixture
construction on this SHA yields the corrected table above. The committed
parameterized tests reproduce all critic/defender permutations for both
actions and assert the direct-arbiter guard as well.

## Evaluation arithmetic and reproducibility

The independent evaluator reviewer recomputed every split/path statistic from
case outputs and resource totals from actual runner events. The lead separately
instrumented execution counts, provider-failure resources and both CLI
regenerations. All 16 complete case/path outputs remain unchanged after gold,
adjudication, risk and split annotations are removed or corrupted.

| Path, all 16 cases | TP/FP/FN/TN | Covered acceptances | Tokens / USD / fixture ms |
|---|---|---|---|
| Baseline | 6/8/0/2 | 0/14 | 0 / 0 / 0 |
| Proposed | 6/0/0/10 | 6/6 | 9450 / 0.063 / 630 |
| No defender | 0/0/6/10 | No accepted cases | 7050 / 0.047 / 470 |
| No control | 0/0/6/10 | No accepted cases | 7050 / 0.047 / 470 |

Proposed precision, recall, exact-verdict accuracy and stability are 1.0;
evidence-less and unresolved-critical acceptances are zero. Baseline has 14
evidence-less and four unresolved-critical acceptances. Both unavailable-role
paths safely HOLD all cases; their reported coverage=1.0 uses the empty
accepted-set convention, not measured evidence coverage of accepted examples.

Resources are synthetic per-round fixture quantities, excluding the second
stability execution. Failed-call usage is unavailable rather than measured
zero. They do not establish real provider latency or billing.

Scoring reproduces all 170 historical rows, with zero baseline mismatches,
changed labels or confidence changes. Baseline/candidate confusion matrices
are identical: all 97/7/3/63 and holdout 52/3/2/38. Holdout F1 is 0.9541.
Scoring gold mutations do not alter the 170 baseline/candidate outputs.

Both actual `python -m ts.cli review-eval` and `score-replay` subprocesses
returned 0 and regenerated `summary.json` plus `report.md` exactly as committed.
The second reviewer also regenerated each pair twice. Independently removing
`result_digest` and hashing sorted canonical JSON reproduced:

```text
review: a629f9089fb785441e334425eee74bfcf72b73d26e8fe9ce69cd3626d231d37a
scoring: fc08036e6e73359e7b99cd39a5e90ffab216938dfc86d779b9d5e9fa9dcce003
```

## Repository verification and isolation

| Check | Result |
|---|---|
| Full suite, fresh migrated PostgreSQL | 455 passed, 1 existing warning, 16.26 s |
| Read-only reviewer's runner/contracts suite | 53 passed, 0.47 s |
| Reviewer's additional runner/direct probes | 38 checks passed |
| Ruff, product ts scope | All checks passed |
| LivingSet | OK requirements=52 waves=19 forks=13 |
| YAML | plan, forks, requirements and rules-0.1/rules-0.2 parse |
| Whitespace | a2409f8..9182e0e and 3ae2bdc..9182e0e pass |
| Added-diff secret-pattern scan | 7170 added lines; zero matches in six bounded pattern categories |
| Disposable PostgreSQL | Migration e2c7f6a9b104; exact new database removed; absence count 0 |

The warning is the existing Starlette/httpx deprecation. Secret-pattern
inspection is a bounded check, not a comprehensive secret audit. No credential
content was read into agent context, printed or copied.

The local PostgreSQL container was healthy and published only at
`127.0.0.1:55432`. Database `astra_wave4_9182e0e_20261013_v5` was absent before
creation. The application consumed the authorized password-file path directly.
Only this newly created database was dropped; its disposable data is
reproducible with the same creation, migration and test commands.

```bash
git rev-parse HEAD
git status --short
git diff --check a2409f8..9182e0e
git diff --check 3ae2bdc..9182e0e
PYTHONDONTWRITEBYTECODE=1 .venv/bin/ruff check ts
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_living_links.py

docker exec thin-signals-pg-1 createdb -U ts astra_wave4_9182e0e_20261013_v5
export TS_DISABLE_DOTENV=1 PYTHONDONTWRITEBYTECODE=1
export TS_DATABASE_URL=postgresql+psycopg://ts@127.0.0.1:55432/astra_wave4_9182e0e_20261013_v5
export TS_PG_PASSWORD_FILE=/opt/thin-signals/.secrets/pg_password
export TS_OPENROUTER_KEY_FILE=''
.venv/bin/alembic upgrade head
.venv/bin/python -m pytest -q -p no:cacheprovider
docker exec thin-signals-pg-1 psql -U ts -d astra_wave4_9182e0e_20261013_v5 -tAc \
  'SELECT current_database(), version_num FROM alembic_version'
docker exec thin-signals-pg-1 dropdb -U ts astra_wave4_9182e0e_20261013_v5
docker exec thin-signals-pg-1 psql -U ts -d postgres -tAc \
  "SELECT count(*) FROM pg_database WHERE datname = 'astra_wave4_9182e0e_20261013_v5'"
```

CLI artifacts were generated beneath temporary directories outside Git;
tampered scoring records were supplied through `/dev/stdin`. YAML checks used
`yaml.safe_load`. No frozen source data or evaluation artifacts were overwritten.

## Limits and disposition

This PASS accepts reproducible deterministic fixture contracts, historical
scoring compatibility and closure of the scoped safety defects. Authored
replay/holdout scenarios and a Boolean seal do not independently establish
scientific generalization or external adjudication. The baseline is a
pre-review admission projection, not live retrieval. Historical scoring rows
do not evaluate the quality effect of mixed-strength evidence.

Live-model quality, independent scientific holdout quality, production canary,
optional C04's ten-signal target, remote publication and activation remain
separate. No deployment or authorization to enable rules-0.2 or adversarial
review follows from this report.

**VERIFIED:** the exact frozen Wave 4 candidate and evidence above.
**UNRESOLVED outside this bounded acceptance:** the live/quality/release gates
just listed. **NEXT TRIGGER:** the separately scoped release/canary workflow.

Verifier disposition: C05 PASS under `GOAL_AGENT=astra-verifier-v5`, followed
by verification of existing GOAL `g-df30f33833c7` with this bounded evidence.
No new GOAL is created or activated.
