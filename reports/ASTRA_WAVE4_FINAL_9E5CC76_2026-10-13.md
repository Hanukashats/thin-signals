# Independent Wave 4 final audit — 9e5cc76

Date: 2026-10-13 UTC. Verifier: `astra-verifier-v3`.

Frozen candidate: `9e5cc7620169d385c45caee0747b9f7f39ac5df5` on
`feat/thin-signals-reliability-20261012`.
Workspace: `/srv/codex-operator/worktrees/1305367840_1791810532/thin-signals`.
GOAL: `g-df30f33833c7`, criterion C05 only.
Historical receipts read: `ASTRA_WAVE4_AUDIT_74445DE_2026-10-13.md` and
`ASTRA_WAVE4_REAUDIT_26B4E8D_2026-10-13.md` in this directory.

## Verdict

**C05 FAIL — one scoped P2 remains.** The exact prior F1–F3 and R1–R3
counterexamples are closed. However, a corrected or narrowed claim can still
receive REFRAME by counting an independent origin cited only by the superseded
claim. This violates ADR-014's two-origin gate for accepted evidence. The
evaluator repeats that evidence union and reports full coverage.

No P0 or P1 was established in this audit. All **435 full-suite tests** and
**63 focused tests** pass; both artifact sets regenerate byte-for-byte. Those
results do not resolve the effective-evidence counterexample below.

This audit changes only this report and C05's verifier status. Product code,
datasets and evaluation artifacts were not edited. Initial and pre-report
worktree checks were clean at the exact frozen SHA. The independent lead and
a read-only reviewer separately reproduced the decisive differential; a second
read-only reviewer corroborated the evaluator's matching union by inspection.
Production, remotes and activation flags were not touched.

## F1 — P2: superseded evidence satisfies the replacement's origin gate

Locations: `ts/review/arbiter.py:98`, `:149`, `:179`;
`ts/review/evaluation.py:481`, `:489`, `:505`, `:642`.

Use R07 `valid_narrowing` or H07 `valid_correction`. The original critical
claim cites only `evidence-1` from origin A. Its replacement, the defender's
action and the bound resolved control finding all cite only `evidence-3` from
origin C. Set `changed_fields=["statement", "evidence_ids"]` to make citation
replacement explicit; H07 already has those fields in the committed fixture.

The real typed runner returns **REFRAME / validated_narrower_claim**, with all
roles successful. The replacement has only one primary origin. The second
origin exists solely in the original, superseded citation set: the arbiter
initializes `accepted_by_claim` from the researcher and then calls `.update()`
for CORRECT/NARROW instead of replacing that claim's effective evidence.

A structural differential isolates the cause without changing the replacement:

| Scenario | Original-only evidence-1 origin | Effective replacement citations | Runner result | Evaluator origins / covered |
|---|---|---|---|---|
| R07 NARROW | A | evidence-3, origin C | REFRAME | 2 / true |
| R07 NARROW | C | evidence-3, origin C | HOLD / insufficient_origin_diversity | 1 / false |
| H07 CORRECT | A | evidence-3, origin C | REFRAME | 2 / true |
| H07 CORRECT | C | evidence-3, origin C | HOLD / insufficient_origin_diversity | 1 / false |

All four runs have no role errors. Changing only the stale origin changes
acceptance while the replacement and its control validation remain identical.
The evaluator's `_promotion_evidence_ids` likewise begins with all original
citations and unions replacement citations, so its reported coverage does not
independently detect this defect. `unresolved_critical` is false for all four;
the demonstrated failure is the effective two-origin gate, not a missing
control/rebuttal link.

This is an inherited effective-evidence gap newly reproduced under the scoped
Wave 4 acceptance contract. It is not an allegation of a production exploit
or a direct PROMOTE outcome. Required correction: construct the effective
claim/evidence set after validated replacements, remove superseded citations
unless the replacement explicitly retains them, and derive coverage from that
same accepted state. ADD_EVIDENCE remains additive. Valid positive replacement
fixtures must explicitly cite the independent origins on which they rely;
regressions should retain the one-origin replacement as a negative case.

### Minimal reproduction

Run from the frozen workspace; this changes only in-memory objects:

```bash
PYTHONDONTWRITEBYTECODE=1 TS_DISABLE_DOTENV=1 .venv/bin/python - <<'PY'
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import ts.review.evaluation as e
from ts.review.runner import run_review

cases = e.load_review_dataset(Path('data/review_eval_v1.json'))['cases']
for scenario in ('valid_narrowing', 'valid_correction'):
    case = next(c for c in cases if c['scenario'] == scenario)
    candidate, evidence, outputs = e._fixture(case)
    outputs['defender']['rebuttals'][0]['changed_fields'] = [
        'statement', 'evidence_ids']
    same_origin = [
        row.model_copy(update={'origin_group_id': 'ror:origin-c'})
        if row.evidence_id == 'evidence-1' else row
        for row in evidence
    ]
    for label, rows in [('distinct_old_origin', evidence),
                        ('same_old_origin', same_origin)]:
        result = run_review(
            run_id='astra-final-proof', candidate=candidate,
            evidence_provider=e._Provider(rows), gateway=e._Gateway(outputs),
            budget=e._BUDGET, models=e._MODELS)
        with patch.object(e, '_fixture', return_value=(
                candidate, rows, deepcopy(outputs))):
            measured = e.evaluate_case(case)['proposed']
        print(case['case_id'], label, result.decision.model_dump(),
              e._role_errors(result), measured['primary_origin_count'],
              measured['evidence_covered'], measured['unresolved_critical'])
PY
```

## Prior findings and positive verification

| Check | Observed result |
|---|---|
| Exact candidate / initial worktree | Requested full SHA; clean |
| Supported, non-primary and unrelated evidence routes | Existing actual-runner safety regressions pass |
| R1 unbound/wrong-evidence controls | HOLD; control invalid_citation; separately checked for ADD_EVIDENCE, CORRECT and NARROW |
| Unknown/noncritical/missing replacement | HOLD in reviewer probes and focused regressions |
| Non-primary replacement | HOLD in reviewer probe |
| Multiple claims/objections | Crossed rebuttal, missing finding, unknown second claim and missing claim reference all HOLD |
| R2 unknown replacement metric | HOLD and unresolved_critical=true in actual evaluator regression |
| R3 scenario-preserving ablations | H08 retains critic plus removed-role failure, 300 tokens / $0.002 / 20 fixture ms |
| Executed ablations | Instrumented 96 real runner executions: 32 each for proposed/no_defender/no_control |
| Repeated stability | Derived from two actual decisions and ledger revisions per path |
| Replay invalid baseline confidence / label | Actual subprocess exit 2; stdout and artifact valid=false; mismatch count 1 |
| Negative / malformed independence trace | Actual subprocess exit 1; no accepted artifact |
| Focused review/scoring suite | 63 passed in 3.70 s |
| Full suite on fresh migrated disposable PostgreSQL | 435 passed, 1 warning in 15.92 s |
| Ruff | All checks passed for ts |
| LivingSet | OK requirements=52 waves=19 forks=13 |
| YAML | plan, forks, requirements and both rules files parse |
| Diff whitespace | Both a2409f8..9e5cc76 and 26b4e8d..9e5cc76 pass; prior P3 fixed |
| Review CLI regeneration | summary.json and report.md byte-identical |
| Scoring CLI regeneration | summary.json and report.md byte-identical |
| Summary hashes | Independently recomputed both result digests |
| Gold/annotation isolation | All 16 complete path results and all 170 scoring outputs unchanged |
| Annotation removal | Aggregate review metrics unchanged |
| Dataset preservation | Cases array identical to 74445de |
| Disposable DB cleanup | Exact new database dropped; absence count 0 |

The full-suite warning is the existing Starlette/httpx deprecation. Ruff scope
was product `ts`; donor/lineage lint debt was not used as a product blocker.

Published fixture arithmetic reproduces: 16 cases, six gold acceptances,
full-path TP=6/FP=0/FN=0/TN=10, precision/recall/exact-verdict accuracy 1.0,
and zero reported unsafe acceptances. These are results against the authored
fixture expectations; the replacement finding above limits their acceptance
meaning. Both role-unavailable paths return HOLD throughout, with recall 0.0.

Actual per-round aggregate resources are 9,450 tokens / $0.063 / 630 fixture ms
for proposed and 7,050 / $0.047 / 470 for each ablation. These represent 63 and
47 completed synthetic calls respectively, at 150 tokens / $0.001 / 10 ms per
call. They exclude the second stability execution and do not claim real
provider billing or latency. Failed-call usage is unavailable, not measured zero.

Scoring reproduces 170 historical rows with zero reconstruction mismatches,
zero changed labels and zero confidence changes. The holdout has 95 rows,
F1=0.9541 and three false positives. Gold changes do not alter either scorer's
outputs. Removing rules-0.2's aggregation strategy in memory leaves the replay
digest unchanged; this remains compatibility evidence, not a quality evaluation
of mixed-strength evidence. The separate scoring holdout/release gate is open.

```text
review dataset logical SHA-256:
acf1bd3b7c19f7602a5eb4bf07e2e2d77aef30a5e1513378e7102f570ca37347
review result SHA-256:
33e63cf110d20b175755764ec55f2054820456ec42fdfe0c925b8a041c486c5c
scoring records logical SHA-256:
042aab83a94926a6e20767118a93882da1dad715c17167e33d887a580bb71ab7
scoring result SHA-256:
fc08036e6e73359e7b99cd39a5e90ffab216938dfc86d779b9d5e9fa9dcce003
historical records.jsonl raw SHA-256:
5359c4ccaa84901ca61f930b4415c3cdca4528cc630d72363149f8c3bcab30a8
```

## Verification commands and isolation

```bash
git rev-parse HEAD
git status --short
git diff --check a2409f8..9e5cc76
git diff --check 26b4e8d..9e5cc76
PYTHONDONTWRITEBYTECODE=1 .venv/bin/ruff check ts
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_living_links.py

docker inspect thin-signals-pg-1 \
  --format '{{json .State.Health.Status}} {{json .NetworkSettings.Ports}}'
docker exec thin-signals-pg-1 psql -U ts -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname = 'astra_wave4_9e5cc76_20261013_v3'"
docker exec thin-signals-pg-1 createdb -U ts astra_wave4_9e5cc76_20261013_v3
export TS_DISABLE_DOTENV=1 PYTHONDONTWRITEBYTECODE=1
export TS_DATABASE_URL=postgresql+psycopg://ts@127.0.0.1:55432/astra_wave4_9e5cc76_20261013_v3
export TS_PG_PASSWORD_FILE=/opt/thin-signals/.secrets/pg_password
export TS_OPENROUTER_KEY_FILE=''
.venv/bin/alembic upgrade head
.venv/bin/python -m pytest -q -p no:cacheprovider \
  ts/tests/test_review_evaluation.py ts/tests/test_scoring_replay.py \
  ts/tests/test_review_runner.py ts/tests/test_scorer.py ts/tests/test_eval.py
.venv/bin/python -m pytest -q -p no:cacheprovider
docker exec thin-signals-pg-1 psql -U ts -d astra_wave4_9e5cc76_20261013_v3 -tAc \
  'SELECT current_database(), version_num FROM alembic_version'
docker exec thin-signals-pg-1 dropdb -U ts astra_wave4_9e5cc76_20261013_v3
docker exec thin-signals-pg-1 psql -U ts -d postgres -tAc \
  "SELECT count(*) FROM pg_database WHERE datname = 'astra_wave4_9e5cc76_20261013_v3'"
```

The absence query was empty before creation. The service was healthy and bound
only to 127.0.0.1:55432. The new database reached migration `e2c7f6a9b104`; the
post-cleanup absence count was 0. Only disposable test data was removed and can
be recreated by the commands above. Credentials were consumed by the application
from its authorized file path, never printed or copied into this report.

YAML validation used `yaml.safe_load(Path(path).read_text())` on `plan.yaml`,
`forks.yaml`, `requirements.yaml`, `ts/scoring/rules-0.1.yaml` and
`ts/scoring/rules-0.2.yaml`. Artifact checks ran real `python -m ts.cli`
subprocesses with `--out` under `TemporaryDirectory`, comparing raw bytes to
committed `reports/eval/review-2026-10-13/` and
`reports/eval/rules-0.2-2026-10-13/`. Tampered scoring inputs were passed through
`--records /dev/stdin`; no frozen data files were modified. Hash verification
removed `result_digest` and independently hashed canonical sorted JSON.

## Evidence limits and disposition

The baseline remains a pre-review admission projection, not live retrieval.
The holdout has disjoint case/scenario names and authored expected outcomes;
a Boolean seal and metadata do not independently establish structural
independence or external adjudication. No new independent sealing receipt was
found. The dataset's original `frozen_code_sha` remains `9f3a139`, while its
arbiter candidate is 0.2; the executable audited here is the exact full SHA at
the top of this report. These limits are unchanged from the historical audits.

**VERIFIED:** prior exact remediation, tests, isolation and artifact
reproducibility above. **UNRESOLVED:** effective replacement evidence (F1).
**NEXT TRIGGER:** a new frozen candidate with replacement-aware accepted
evidence and coverage, followed by independent verification.

Only C05 was set FAIL under `GOAL_AGENT=astra-verifier-v3`, using this report
as evidence. The kernel returned `ok: true`, C05 `FAIL`, goal `IN_PROGRESS`,
3/4 required criteria PASS. No whole-GOAL verification call was made.
Optional C04, live-model quality, production canary, release, remote publication
and activation remain outside this audit.
