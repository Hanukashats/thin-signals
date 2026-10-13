# Independent Wave 4 re-audit — 26b4e8d

Date: 2026-10-13 UTC. Verifier: `astra-verifier-v2`.

Frozen candidate: `26b4e8dcb9e97833decaa589cbdab378f2d160b5` on
`feat/thin-signals-reliability-20261012`.
Comparison: `74445deaf346e7d63cb90b59302bdf54e9eb8281`.
Workspace: `/srv/codex-operator/worktrees/1305367840_1791810532/thin-signals`.
GOAL: `g-df30f33833c7`, criterion C05 only.

## Verdict

**C05 FAIL — changes required.** No P0; one P1 and two P2 findings remain in
the scoped acceptance contract. There is also one P3 whitespace defect.
The exact three reproductions from the preceding audit are fixed, but the
strengthened acceptance and evaluation claims do not hold for the additional
schema-valid cases below. The full suite passes **429 tests**; passing tests
and reproducible artifacts do not resolve these counterexamples.

The independent verifier and two read-only sub-reviewers inspected the frozen
candidate. The lead independently reproduced all three findings. Product code,
datasets and generated artifacts were not edited. Only this report and C05's
verifier status are in scope; the whole GOAL is not verified or completed.
Production, external remotes and feature flags were not touched.

## Findings

### R1 — P1: a control finding can resolve an unreferenced rebuttal

Locations: `ts/review/runner.py:366-379`,
`ts/review/arbiter.py:107-135`; related evaluation blind spot:
`ts/review/evaluation.py:512-540`.

Take R02 `defended_positive`. Change only the control finding to
`rebuttal_id=None` and `evidence_ids=["evidence-2"]`.
`evidence-2` is the critic's original counterevidence. The defender's new,
independent `evidence-3` is neither referenced through a rebuttal nor cited
by the control finding. The real runner nevertheless completes every role
successfully and returns **PROMOTE**, reason
`all_critical_objections_resolved`. Applying the same change to R07 narrowing
and H07 correction returns **REFRAME** without any role error.

The reference validator legitimately permits an objection-only finding, but
does not distinguish that from a finding that claims a rebuttal has resolved
the objection. The arbiter looks up rebuttal and finding separately by objection
ID and never requires the finding to name that rebuttal or validate the evidence
being accepted from it. A Boolean `evidence_valid` on the original counterevidence
therefore supplies the missing control validation for newly accepted evidence.
The evaluator also records `unresolved_critical=False`.

This behavior predates the remediation; it is a newly reproduced bypass of
the scoped evidence-gated acceptance claim, not a newly introduced production
regression. Its P1 severity follows from direct PROMOTE with a critical defense
that has no corresponding control citation. No live-provider or production
exploit is alleged.

Required correction: require a resolved critical finding to bind the exact
rebuttal and the evidence used to accept its ADD_EVIDENCE/CORRECT/NARROW action.
Keep objection-only findings usable for their legitimate unresolved/fatal
purpose. Add actual-runner regressions for all three accepted action types.

### R2 — P2: unknown critical replacement claims still receive REFRAME

Locations: `ts/review/arbiter.py:136-153`, `:173-175`;
`ts/review/evaluation.py:512-520`, `:622-624`.

Take R07 `valid_narrowing` and change only
`defender.rebuttals[0].replacement_claim.status` from `verified` to `unknown`.
The replacement remains critical and schema-valid. All four roles succeed,
and the actual runner returns **REFRAME**, reason `validated_narrower_claim`.
The unknown-claim gate checks only the researcher's original claims; it never
checks the effective replacement claim. Moving that gate ahead of REFRAME
therefore fixes the prior second-researcher-claim example without closing this
equivalent replacement route.

The new evaluator repeats the same omission. It reports primary-origin count
2, covered evidence, no role errors and `unresolved_critical=False`. Replacing
only this fixture output in memory while running the complete dataset leaves
proposed unresolved-critical promotions **0**, P/R **1.0/1.0**, exact-verdict
accuracy **1.0**, and overpromotions **0**. The unchanged gold verdict remains
REFRAME, so exact-verdict scoring cannot substitute for deriving safety from
the effective accepted claims.

The arbiter hole is inherited; the incomplete safety derivation is part of
the remediation. This is one finding, not a separate count for each layer.
Its demonstrated outcome is REFRAME, not PROMOTE. Required correction: build
and validate the effective critical-claim set after replacements, enforce
unknown/attestation rules on it, and derive safety from validated resolution
records rather than only the original researcher payload.

### R3 — P2: provider-failure ablations silently restore the critic

Location: `ts/review/evaluation.py:554-565`.

The new ablations really execute the runner twice, fixing the preceding
post-hoc-validation defect. However, the single `unavailable_role` selection
replaces H08 `provider_failure`'s original critic failure with the ablated
role. Thus removing defender/control also repairs the critic, changing two
conditions in this comparison.

| H08 path | Errors | Tokens | USD | Fixture ms |
|---|---|---:|---:|---:|
| Published no_defender | defender | 450 | 0.003 | 30 |
| Preserve scenario, remove defender | critic, defender | 300 | 0.002 | 20 |
| Published no_control | control_critic | 450 | 0.003 | 30 |
| Preserve scenario, remove control | critic, control_critic | 300 | 0.002 | 20 |

Every row remains HOLD, so the safety verdict is unchanged. The error/resource
comparison is nevertheless not an ablation of the same failed case. Preserving
the original scenario makes each aggregate ablation **7,050 tokens / $0.047 /
470 fixture ms**, rather than the published 7,200 / $0.048 / 480.
Required correction: retain scenario failures and layer the removed role on
top, then regenerate the two affected rows and aggregate resources.

### P3: diff whitespace check fails

`git diff --check 74445de..26b4e8d` exits 2 at
`docs/adr/ADR-014-ATTESTED-PROMOTION-GATE.md:3` for two trailing spaces after
the date. This is Markdown formatting, not a functional or safety blocker;
it is recorded separately from R1-R3. The verifier did not alter it.

## Prior findings and positive evidence

| Check | Observed result |
|---|---|
| Frozen SHA / initial worktree | Exact requested SHA; clean |
| Prior F1 supported non-primary route | HOLD / critical_claim_unattested; no role error |
| Unrelated non-critical primary evidence smuggling | HOLD / critical_claim_unattested |
| Prior unknown second researcher claim | Existing actual-runner regression passes |
| Prior F2 post-hoc ablations | Fixed: 96 runner executions, 32 per proposed/ablation path |
| R03 no-defender reference validation | HOLD; defender failure and control invalid_citation recorded |
| Ablation repeated stability | Derived from two actual decisions and ledger hashes |
| Prior F3 changed stored confidence or label | CLI exit 2, valid=false, mismatch count 1 |
| Malformed/negative independence trace | Nonzero CLI exit; no accepted artifact |
| Focused review/scoring tests | 57 passed in 3.67 s |
| Full suite on fresh migrated disposable PostgreSQL | 429 passed, 1 warning in 15.61 s |
| Ruff | All checks passed for ts |
| LivingSet | OK requirements=52 waves=19 forks=13 |
| YAML | plan, forks, requirements, both rules files parse |
| Review regeneration | summary.json and report.md byte-identical |
| Scoring regeneration | summary.json and report.md byte-identical |
| Independent summary hash calculations | Both result digests match |
| Gold mutation | All 16 review path results and all 170 scorer outputs unchanged |
| Annotation removal | All review paths and aggregate metrics unchanged |
| Dataset cases | Cases array preserved from 74445de |
| Disposable DB cleanup | Exact test database removed; absence count 0 |

The sole full-suite warning is the existing Starlette/httpx deprecation.
The database reached migration `e2c7f6a9b104`. PostgreSQL was healthy and
published only on `127.0.0.1:55432`. Credentials were consumed from the authorized
password-file path and were never read into tool output or this report.

Hashes independently recomputed by the read-only sub-reviewers:

```text
review dataset logical SHA-256:
acf1bd3b7c19f7602a5eb4bf07e2e2d77aef30a5e1513378e7102f570ca37347
review result SHA-256:
acdfe389595b17c5cd62397cfd3b38122034618e3cb001f0954ca9eb9a6cc533
scoring result SHA-256:
fc08036e6e73359e7b99cd39a5e90ffab216938dfc86d779b9d5e9fa9dcce003
```

## Reproduction

Run commands from the stated frozen workspace. Python probes mutate only
in-memory copies. Temporary regeneration artifacts are outside the repository.

```bash
git rev-parse HEAD
git status --short
PYTHONDONTWRITEBYTECODE=1 .venv/bin/ruff check ts
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_living_links.py
git diff --check 74445de..26b4e8d
```

Minimal R1/R2 probes, including evaluator behavior:

```bash
PYTHONDONTWRITEBYTECODE=1 TS_DISABLE_DOTENV=1 .venv/bin/python - <<'PY'
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import ts.review.evaluation as e
from ts.review.runner import run_review

data = e.load_review_dataset(Path('data/review_eval_v1.json'))
for scenario, attack in [
    ('defended_positive', 'unbound_control'),
    ('valid_narrowing', 'unbound_control'),
    ('valid_correction', 'unbound_control'),
    ('valid_narrowing', 'unknown_replacement'),
]:
    case = next(c for c in data['cases'] if c['scenario'] == scenario)
    candidate, evidence, outputs = e._fixture(case)
    outputs = deepcopy(outputs)
    if attack == 'unknown_replacement':
        outputs['defender']['rebuttals'][0]['replacement_claim']['status'] = 'unknown'
    else:
        outputs['control_critic']['findings'][0].update(
            rebuttal_id=None, evidence_ids=['evidence-2'])
    result = run_review(
        run_id='audit-probe', candidate=candidate,
        evidence_provider=e._Provider(evidence), gateway=e._Gateway(outputs),
        budget=e._BUDGET, models=e._MODELS)
    with patch.object(e, '_fixture', return_value=(candidate, evidence, outputs)):
        measured = e.evaluate_case(case)['proposed']
    print(case['case_id'], attack, result.decision.model_dump(),
          e._role_errors(result), measured)
PY
```

Minimal R3 differential:

```bash
PYTHONDONTWRITEBYTECODE=1 TS_DISABLE_DOTENV=1 .venv/bin/python - <<'PY'
from pathlib import Path
from unittest.mock import patch
import ts.review.evaluation as e

data = e.load_review_dataset(Path('data/review_eval_v1.json'))
case = next(c for c in data['cases'] if c['scenario'] == 'provider_failure')
published = e.evaluate_case(case)
class PreserveCriticFailure(e._Gateway):
    def call(self, role, *args, **kwargs):
        if role == 'critic':
            raise RuntimeError('deterministic provider failure fixture')
        return super().call(role, *args, **kwargs)
with patch.object(e, '_Gateway', PreserveCriticFailure):
    preserved = e.evaluate_case(case)
for path in ('no_defender', 'no_control'):
    for label, rows in (('published', published), ('preserved', preserved)):
        r = rows[path]
        print(path, label, r['verdict'], r['role_errors'],
              r['tokens'], r['cost_usd'], r['latency_ms'])
PY
```

Database verification was confined to this explicit disposable database:

```bash
docker inspect thin-signals-pg-1 \
  --format '{{json .State.Health.Status}} {{json .NetworkSettings.Ports}}'
docker exec thin-signals-pg-1 psql -U ts -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname = 'astra_wave4_26b4e8d_20261013_v2'"
docker exec thin-signals-pg-1 createdb -U ts astra_wave4_26b4e8d_20261013_v2
export TS_DISABLE_DOTENV=1 PYTHONDONTWRITEBYTECODE=1
export TS_DATABASE_URL=postgresql+psycopg://ts@127.0.0.1:55432/astra_wave4_26b4e8d_20261013_v2
export TS_PG_PASSWORD_FILE=/opt/thin-signals/.secrets/pg_password
export TS_OPENROUTER_KEY_FILE=''
.venv/bin/alembic upgrade head
.venv/bin/python -m pytest -q -p no:cacheprovider \
  ts/tests/test_review_evaluation.py ts/tests/test_scoring_replay.py \
  ts/tests/test_review_runner.py ts/tests/test_scorer.py ts/tests/test_eval.py
.venv/bin/python -m pytest -q -p no:cacheprovider
docker exec thin-signals-pg-1 psql -U ts -d astra_wave4_26b4e8d_20261013_v2 -tAc \
  'SELECT current_database(), version_num FROM alembic_version'
docker exec thin-signals-pg-1 dropdb -U ts astra_wave4_26b4e8d_20261013_v2
docker exec thin-signals-pg-1 psql -U ts -d postgres -tAc \
  "SELECT count(*) FROM pg_database WHERE datname = 'astra_wave4_26b4e8d_20261013_v2'"
```

The absence check was empty before creation and returned 0 after cleanup.
Only newly created test data was removed; rerunning the commands recreates it.
YAML validation used `yaml.safe_load(Path(name).read_text())` for `plan.yaml`,
`forks.yaml`, `requirements.yaml`, `ts/scoring/rules-0.1.yaml` and
`ts/scoring/rules-0.2.yaml`.

## Evidence limits and disposition

The original fixture results are numerically reproducible: 16 cases, six gold
acceptances, full-path P/R and exact-verdict accuracy 1.0, no encoded unsafe
acceptances, both role-unavailable paths HOLD. This establishes the behavior
of those fixtures, not the absence of the schema-valid counterexamples above.
Resource figures describe one synthetic round per path, not provider billing
or the cost of both stability executions. The baseline is a pre-review admission
projection, not an independently executed live baseline pipeline.

Disjoint case/scenario names do not establish structural holdout independence
or independent adjudication. The dataset's `frozen_code_sha` still names
`9f3a139`; the separate `arbiter_candidate` names `review-arbiter-0.2`, and the
exact executable audited here is the full SHA at the top of this report.
No independent sealing receipt or new model-generalization evidence was found.

Scoring replay correctly reproduces all 170 stored rows with zero mismatches
and zero changed labels/confidences. Its evidence limitation is unchanged:
66 rows short-circuit on counters and all 373 remaining pattern statuses are
`supported`. Removing candidate `pattern_aggregation` in memory leaves the
complete replay digest unchanged. Historical compatibility therefore does not
measure quality of the affected mixed-strength cases; ADR-013's separate
adjudicated scoring holdout and production gates remain open. No false scoring
release closure was found.

**VERIFIED:** exact prior repro fixes, tests and artifact reproducibility above.
**UNRESOLVED:** R1-R3; C05 remains FAIL.
**NEXT TRIGGER:** a new frozen candidate correcting those findings, followed by
fresh independent verification. No whole-GOAL acceptance, production canary,
live retrieval/model-quality result, ten-signal result, deployment or push is
implied by this audit.
