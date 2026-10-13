# Independent Wave 4 audit — 74445de

Date: 2026-10-13 UTC. Verifier identity: `astra-verifier`.

Frozen candidate: `74445deaf346e7d63cb90b59302bdf54e9eb8281`.
Diff baseline: `a2409f8379b4b5b0c6740f816219a7e8794d4bfb`.
Workspace: `/srv/codex-operator/worktrees/1305367840_1791810532/thin-signals`.
GOAL: `g-df30f33833c7`, criterion C05.

## Verdict

**C05 FAIL — changes required.** No P0. One inherited P1 safety defect affects
the required Wave 4 acceptance gate; two P2 defects are introduced by this diff.
All 423 repository tests pass and the committed artifacts regenerate exactly,
but those successes do not resolve the counterexamples below. C02/C03's recorded
PASS evidence is insufficient for independent acceptance. The whole GOAL is not
verified; production activation remains gated.

This audit changes only this report and C05's verifier status. Product code,
datasets, generated evaluation artifacts and the frozen commit are unchanged.
Two read-only reviewers independently challenged review evaluation and scoring
replay; the lead verifier independently reproduced the decisive findings.

## Findings

### F1 — P1, inherited: supported claims can PROMOTE without primary evidence

Locations: `ts/review/runner.py:298`, `ts/review/arbiter.py:42`,
`ts/review/arbiter.py:157`; the new coverage gap is
`ts/review/evaluation.py:378` and H05 in `data/review_eval_v1.json`.

Take H05's existing `weak_provenance` fixture and change only the researcher's
claim status from `verified` to the schema-valid `supported`. Both cited
evidence items remain `preserved_non_primary`; there is no qualifying primary
evidence. The actual `run_review` executes all four roles without an error and
returns `PROMOTE`, reason `all_critical_objections_resolved`. The evaluator's own
`evidence_covered` is false. Through the unchanged H05 risk annotation, the
proposed evidence-less promotion count becomes **1**, not zero.

The runner requires primary attestation only for `verified` claims. The arbiter
then counts origin IDs without checking their provenance and promotes when two
are present. The shipped H05 only tests rejection of an invalid *verified*
citation; it misses the valid supported-claim route.

Runner/arbiter code predates this diff. This is not presented as a newly
introduced production regression, nor was live end-to-end reachability tested.
It is a reproducible counterexample to the same runner/arbiter safety contract
that Wave 4 is meant to establish, using a minimal variation of its own fixture.

Required correction: enforce qualifying cited evidence at the promotion gate,
regardless of how the role labels the claim; add the supported/non-primary case
to evaluation and regression tests. Do not weaken or remove H05's gold label.

### F2 — P2, introduced: ablations bypass validation and do not execute the claimed paths

Locations: `ts/review/evaluation.py:497`, `:503`, `:518`, `:554`;
reference validation: `ts/review/runner.py:374`.

The evaluator executes the full round twice. For ablations it parses the original
fixture outputs, substitutes an empty defender or control output, and calls
`arbitrate` directly. The no-defender path retains control findings referring to
the removed defender's `rebuttal-1`. Those records would fail the runner's
reference checks.

Concrete discrepancy on R03 `fatal_false_novelty`:

| Execution | Verdict | Role error |
|---|---|---|
| Published `evaluate_case(...)["no_defender"]` | REJECT | Not validated as an ablation |
| Same fixture with empty defender through real `run_review` | HOLD | `control_critic: invalid_citation` |

The numeric acceptance metric happens to classify both as negative. It therefore
does not reveal that the claimed contract path is different. Ablation resource
totals are selected from full-round events, rather than collected from ablation
execution; ablation stability is assigned `True` without a second run.

Required correction: execute explicit reduced-role paths through the relevant
runner/reference validation, supply control input appropriate to the remaining
roles, and account for those actual fixture calls. Alternatively, label this
output-removal calculation as a post hoc estimate and leave the executed-ablation
acceptance criterion open. Do not present hardcoded stability as a measurement.

### F3 — P2, introduced: scoring replay succeeds when baseline reconstruction fails

Locations: `ts/scoring/replay.py:120`, `ts/cli.py:114`;
contradictory claimed gate: `docs/EVAL.md:56` and `ARCHITECTURE.md:116`.

The code scores both versions, increments `baseline_reproduction_mismatches`,
and still writes normal candidate results and returns success. The CLI stdout
does not even include the mismatch count. Feeding the 170 original rows with
only the first stored confidence changed to `0.123456` produced:

```text
exit=0 baseline_reproduction_mismatches=1 n=170
stdout_exposes_mismatch=False
```

Thus exact reproduction is not actually required before candidate comparison,
despite the documentation. A consumer using exit status can accept an invalid
reconstruction. The committed unmodified dataset has no mismatch; this finding
concerns failure behavior, not a false accusation about the published 170 rows.

Required correction: fail with a nonzero status or a clearly invalid evaluation
state when any baseline mismatch exists; expose that state to the CLI consumer
and test it with a real mismatched input.

## Reproduced positive evidence

| Check | Observed result |
|---|---|
| Frozen HEAD / initial worktree | Requested SHA; clean |
| `ruff check ts` | All checks passed |
| LivingSet cross-links | `OK requirements=52 waves=19 forks=13` |
| YAML parse | plan, forks, requirements, rules-0.1 and rules-0.2 all parse |
| Diff whitespace | `git diff --check a2409f8..74445de` passed |
| Focused evaluation/scorer tests | 26 passed in 1.42 s |
| Full suite on disposable migrated PostgreSQL | 423 passed, 1 warning in 13.29 s |
| Review CLI regeneration | summary.json and report.md byte-identical |
| Scoring CLI regeneration | summary.json and report.md byte-identical |
| Independent summary digest calculation | Both result digests verified |
| Review gold mutation | All 16 cases' four-path verdicts unchanged |
| Scoring gold mutation | All 170 baseline/candidate outputs unchanged |
| Disposable DB cleanup | Exact test database removed; absence count 0 |

The sole full-suite warning is the existing Starlette/httpx deprecation warning.
Runtime versions: Python 3.14.4, pytest 9.1.1, SQLAlchemy 2.0.54, psycopg 3.3.6,
Pydantic 2.13.5. `.venv` points to `/opt/thin-signals/.venv`.
Donor/lineage Ruff debt was excluded as requested.

The proposed fixture path calls the real typed runner and deterministic arbiter.
The baseline is a pre-review admission projection of the fixture candidate,
not a live baseline retrieval run. Gold/adjudication do not enter fixture
construction or role decisions. All original failure fixtures remain safe
under their encoded inputs.

Published review results are arithmetically reproducible: 16 cases, 6 accepted
gold cases and 10 negatives. Baseline has TP=6, FP=8, FN=0, TN=2; the full fixture
path has TP=6, FP=0, FN=0, TN=10. Each split contains 8 cases and 3 positives.
The two post hoc ablations each report TP=2 and FN=4 in aggregate, yielding
recall 0.3333, subject to F2.

The full path totals 63 completed synthetic role calls: 9,450 tokens,
$0.063 and 630 fixture milliseconds. Every successful fixture call declares
150 tokens, $0.001 and 10 ms. One critic call raises; its unknown usage is not
an actual measured zero. These are deterministic fixture quantities, not
observed provider latency, billing, or the total computation of both repeated
stability runs. The report's live-model limitation is appropriate.

The scoring replay reproduces all 170 historical labels and confidence values:
75 train, 95 holdout, zero mismatches, zero changed labels, zero confidence
increases/decreases. Holdout F1 is 0.9541 with 3 false positives out of 95 rows.
The rules files retain identical weights/thresholds; the versioned aggregation
change and ADR-013 were inspected. Existing property tests independently exercise
primary choice and status monotonicity.

Digests:

```text
review dataset logical SHA-256:
07371c1af0f2d8efa0d65d5d085012a635c186c87e2b891070fe7a1c66dbd175
review result SHA-256:
b26922c55e9d3e100d6510387de53eaafd239aac04d87de37f93051a9616bf0a
scoring records logical SHA-256:
042aab83a94926a6e20767118a93882da1dad715c17167e33d887a580bb71ab7
scoring result SHA-256:
c9e97cadbccea1385e92a7405f695cbcf806ccc686030daad69120bca662e039
historical records.jsonl raw file SHA-256:
5359c4ccaa84901ca61f930b4415c3cdca4528cc630d72363149f8c3bcab30a8
```

## Evidence limits and unresolved gates

- Replay/holdout case IDs and scenario names are disjoint, and several holdout
  cases add meaningful contract variations, such as two objections and a role
  failure. The loader enforces disjoint *names*, not structural fingerprints.
  Fatal chronology and false novelty still share an arbiter topology, as do
  correction and narrowing. The JSON records authored expected-verdict
  explanations, a Boolean seal and a timestamp; it provides no independent
  adjudicator or separate sealing receipt. This supports additional frozen
  contract fixtures, not independently demonstrated generalization. No tuning
  or hidden gold access is alleged without evidence.
- The review fixture metadata references frozen code `9f3a139`; runner/arbiter
  are unchanged from that reference. The fixture generator and dataset were
  introduced together at `74445de`. Freeze metadata alone does not attest to
  independent adjudication of the new dataset.
- Safety metrics count `risk_flags`, rather than deriving all safety state from
  cited/accepted evidence and unresolved critical records. Current H05 is
  correctly tagged and the supported variation produces one evidence-less
  promotion. Omitting that annotation is loader-valid and would hide it from
  that count. Coverage also checks all available fixture evidence, not only
  evidence accepted for each claim.
- `PROMOTE` and `REFRAME` are both projected to accepted=true. `gold_verdict`
  is stored but not scored; the published metrics cannot detect replacing a
  correct REFRAME with an incorrect PROMOTE. A separate exact-verdict check is
  needed for that contract claim. An additional inherited probe—R07 with a
  second critical unknown claim—returns REFRAME because that return precedes
  the unknown-claim gate (`arbiter.py:145-151`). This was observed through the
  runner, not on production; the current binary fixture metrics do not establish
  absence of every unresolved critical claim in accepted actions.
- Scoring inputs are reconstructed from derived prediction traces, not full
  original extraction objects. Sixty-six records short-circuit on counters;
  the remaining 104 have 373 pattern predictors, all `supported`, and their
  confidence is 0.4–0.675. There are no mixed-strength examples. Removing the
  candidate aggregation strategy in memory produces the same complete replay
  digest. This is useful historical compatibility evidence, but cannot assess
  the affected mixed-strength cases' quality. The review holdout does not call
  the scorer, so ADR-013's separate scoring holdout/production gate remains open.
- No live model, retrieval, production canary, ten-signal result, provider bill,
  or production deployment was tested or established. Existing authored-negative
  dataset limitations remain documented in EVAL/requirements. No whole-GOAL
  acceptance or permission to activate rules-0.2 follows from this audit.

## Commands and reproduction

All commands below use the workspace stated above. Repository writes were
disabled where practical (`PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled).
Ephemeral CLI artifacts were written only into `TemporaryDirectory` locations.

```bash
git rev-parse HEAD
git status --short
git diff --stat a2409f8..74445de
git diff --check a2409f8..74445de
PYTHONDONTWRITEBYTECODE=1 .venv/bin/ruff check ts
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_living_links.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  ts/tests/test_review_evaluation.py ts/tests/test_scoring_replay.py \
  ts/tests/test_scorer.py ts/tests/test_eval.py
```

YAML validation used `yaml.safe_load(Path(name).read_text())` for `plan.yaml`,
`forks.yaml`, `requirements.yaml`, `ts/scoring/rules-0.1.yaml`, and
`ts/scoring/rules-0.2.yaml`.

Database verification was confined to the explicit new test database:

```bash
docker inspect thin-signals-pg-1 \
  --format '{{json .State.Health.Status}} {{json .NetworkSettings.Ports}}'
docker exec thin-signals-pg-1 psql -U ts -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname = 'astra_wave4_74445de_20261013_v1'"
docker exec thin-signals-pg-1 createdb -U ts astra_wave4_74445de_20261013_v1
export TS_DISABLE_DOTENV=1 PYTHONDONTWRITEBYTECODE=1
export TS_DATABASE_URL=postgresql+psycopg://ts@127.0.0.1:55432/astra_wave4_74445de_20261013_v1
export TS_PG_PASSWORD_FILE=/opt/thin-signals/.secrets/pg_password
export TS_OPENROUTER_KEY_FILE=''
.venv/bin/alembic upgrade head
.venv/bin/python -m pytest -q -p no:cacheprovider
docker exec thin-signals-pg-1 psql -U ts -d astra_wave4_74445de_20261013_v1 -tAc \
  'SELECT current_database(), version_num FROM alembic_version'
docker exec thin-signals-pg-1 dropdb -U ts astra_wave4_74445de_20261013_v1
docker exec thin-signals-pg-1 psql -U ts -d postgres -tAc \
  "SELECT count(*) FROM pg_database WHERE datname = 'astra_wave4_74445de_20261013_v1'"
```

The absence query was initially empty; migration reached `e2c7f6a9b104`;
the final absence count was 0. The service was healthy and published PostgreSQL
only on `127.0.0.1:55432`. The password was consumed by the application from the
authorized path and never printed. One initial migration attempt stopped in
settings before DB access because `TS_OPENROUTER_KEY_FILE=/nonexistent` resolved
to an unreadable existing path; setting that variable to empty disabled the
unused model key and the migration/test run passed. No production rows were
accessed by the tests. Only disposable test data was deleted; it can be recreated
by the commands above.

Exact CLI regeneration and mismatch probe, run with
`TS_DISABLE_DOTENV=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -`:

```python
import json, os, subprocess, tempfile
from pathlib import Path
from ts.scoring.replay import load_scoring_records

root = Path.cwd()
with tempfile.TemporaryDirectory(prefix="astra-wave4-cli-") as scratch:
    for cmd, source in [("review-eval", "review-2026-10-13"),
                        ("score-replay", "rules-0.2-2026-10-13")]:
        out = Path(scratch) / cmd
        result = subprocess.run(
            [str(root / ".venv/bin/python"), "-m", "ts.cli", cmd, "--out", str(out)],
            check=True, capture_output=True, text=True, env=os.environ.copy())
        for name in ("summary.json", "report.md"):
            assert (out / name).read_bytes() == (root / "reports/eval" / source / name).read_bytes()
        print(cmd, json.loads(result.stdout)["result_digest"])

records = load_scoring_records(Path("reports/eval/2026-09-23/records.jsonl"))
records[0]["confidence"] = 0.123456
with tempfile.TemporaryDirectory(prefix="astra-mismatch-") as scratch:
    result = subprocess.run(
        [str(root / ".venv/bin/python"), "-m", "ts.cli", "score-replay",
         "--records", "/dev/stdin", "--out", scratch],
        input="\n".join(json.dumps(row) for row in records),
        capture_output=True, text=True, env=os.environ.copy())
    summary = json.loads((Path(scratch) / "summary.json").read_text())
    assert result.returncode == 0
    assert summary["baseline_reproduction_mismatches"] == 1
    assert "baseline_reproduction_mismatches" not in json.loads(result.stdout)
```

Decisive runner probes, using the same Python invocation:

```python
from pathlib import Path
from ts.review import evaluation as e
from ts.review.runner import run_review

cases = e.load_review_dataset(Path("data/review_eval_v1.json"))["cases"]
def run(case, mutate):
    candidate, evidence, outputs = e._fixture(case)
    mutate(candidate, evidence, outputs)
    result = run_review(
        run_id="astra-probe-" + case["case_id"], candidate=candidate,
        gateway=e._Gateway(outputs), evidence_provider=e._Provider(evidence),
        budget=e._BUDGET, models=e._MODELS)
    return result, evidence

case = next(c for c in cases if c["case_id"] == "H05-weak-provenance")
result, evidence = run(case, lambda c, ev, o:
    o["researcher"]["claims"][0].update(status="supported"))
assert result.decision.verdict == "PROMOTE"
assert not any(event.error_code for event in result.events)
assert not e._covered(evidence)

case = next(c for c in cases if c["case_id"] == "R03-false-novelty")
result, _ = run(case, lambda c, ev, o: o.update(defender={"rebuttals": []}))
assert e.evaluate_case(case)["no_defender"]["verdict"] == "REJECT"
assert result.decision.verdict == "HOLD"
assert any(x.role == "control_critic" and x.error_code == "invalid_citation"
           for x in result.events)

case = next(c for c in cases if c["case_id"] == "R07-valid-narrowing")
def add_unknown(c, ev, o):
    o["researcher"]["claims"].append({
        "claim_id": "claim-unknown", "statement": "A second critical claim remains unknown.",
        "critical": True, "evidence_ids": ["evidence-2"],
        "status": "unknown", "reason_codes": ["P03"]})
result, _ = run(case, add_unknown)
assert result.decision.verdict == "REFRAME"
assert not any(event.error_code for event in result.events)
```

Independent digest checks removed `result_digest` from each loaded summary and
hashed `json.dumps(summary, sort_keys=True, separators=(",", ":"),
ensure_ascii=True).encode()` with SHA-256. Gold checks flipped every review case's
gold acceptance/verdict and replaced adjudication/risk metadata, comparing all
four verdicts before/after; the scoring check flipped all 170 gold labels and
compared both versions' `(label, confidence)` outputs. All comparisons passed.

## GOAL disposition

Only C05 was set to FAIL under independent identity `astra-verifier`, with this
report as evidence:

```bash
GOAL_AGENT=astra-verifier goalctl crit g-df30f33833c7 C05 FAIL \
  reports/ASTRA_WAVE4_AUDIT_74445DE_2026-10-13.md
```

The kernel returned `ok: true`, C05 `FAIL`, goal `IN_PROGRESS`, 3/4 required
criteria PASS. Readback confirmed `set_by: astra-verifier` and `verified: false`.
No whole-goal verification call was made. A new frozen candidate must resolve
F1–F3 and receive fresh independent verification; the current artifact must
remain historical.
