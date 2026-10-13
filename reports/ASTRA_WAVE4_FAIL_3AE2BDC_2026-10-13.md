# Independent Wave 4 audit — 3ae2bdc

Date: 2026-10-13 UTC. Verifier: `astra-verifier-v4`.

Frozen candidate: `3ae2bdc52370c0cc6b30fac65834dba54158bce5`.
Workspace: `/srv/codex-operator/worktrees/1305367840_1791810532/thin-signals`.
GOAL: `g-df30f33833c7`, criterion C05.

## Verdict

**C05 FAIL — one scoped P2 remains.** The prior F1–F3, R1–R3 and
superseded-evidence counterexamples are fixed. However, combining one
CORRECT/NARROW action with one ADD_EVIDENCE action for the same original claim
remains order-dependent. Reordering the critic's objections changes HOLD to
REFRAME; independently reordering the defender's rebuttals changes the
evaluator's coverage without changing that verdict.

No P0 or P1 was established. All **439 repository tests** pass on a fresh
migrated disposable PostgreSQL database. Both evaluation artifact sets
regenerate byte-for-byte. Those successes do not resolve the differential below.

The lead verifier independently reproduced both action variants and all four
list permutations. Two read-only reviewers separately reproduced the issue.
The candidate and worktree were clean before this report. Only this report and
C05's verifier disposition are changed; product code, production, remotes and
feature flags are untouched. No whole-GOAL verification follows from this verdict.

## F1 — P2: mixed actions have incompatible order-dependent evidence reduction

Locations: `ts/review/runner.py:330`, `ts/review/arbiter.py:102`,
`ts/review/arbiter.py:136`, `ts/review/arbiter.py:152`,
`ts/review/evaluation.py:502`, `ts/review/evaluation.py:518`.

Start with the existing `valid_narrowing` or `valid_correction` fixture. Its
original claim cites origin A. Give the replacement only `evidence-3`, origin C,
and bind its rebuttal/control finding to that evidence. Add a second critical
objection targeting the same original claim and resolve it with ADD_EVIDENCE
of new `evidence-4`, origin D, through its own correctly bound control finding.

All IDs, evidence, statements, statuses and control bindings remain identical
across the following permutations. Every role succeeds with no errors.

| Critic objection order | Defender rebuttal order | Actual runner verdict | Evaluator origins / covered |
|---|---|---|---|
| Replacement, ADD | Replacement, ADD | REFRAME | 2 / true |
| Replacement, ADD | ADD, replacement | REFRAME | 1 / false |
| ADD, replacement | Replacement, ADD | HOLD | 2 / true |
| ADD, replacement | ADD, replacement | HOLD | 1 / false |

The same table reproduces for CORRECT and NARROW. HOLD is
`insufficient_origin_diversity`; REFRAME is `validated_narrower_claim`.
All eight evaluator results report `unresolved_critical=false` and `stable=true`.
Repeated identical ordering is stable, but equivalent unordered records are not.

The validator rejects multiple replacements but allows this mixed pair.
The arbiter updates/replaces accepted citations while iterating critic
objections. The evaluator independently updates/replaces citations while
iterating defender rebuttals. Thus their effective evidence sets can disagree
even for one accepted result. This is one combined correctness/evaluation
finding; no direct PROMOTE bypass or production exploit is claimed.

Required correction: define one order-independent effective-claim policy and
derive both arbitration and reported coverage from its validated result.
The bounded fail-closed option is to reject a claim with both a replacement
and an ADD_EVIDENCE response in the same unordered round: additions currently
target the original claim and have no explicit binding to its replacement.
Do not silently assign precedence from either list. If mixed actions are
intentionally supported instead, their target/precedence semantics need an
explicit contract. Regressions must permute critic and defender lists
independently for both CORRECT and NARROW, while retaining valid single-action
positive cases and unambiguous additive defenses.

### Reproduction

Run from the frozen workspace. This mutates only in-memory objects.

```bash
TS_DISABLE_DOTENV=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from copy import deepcopy
from itertools import product
from pathlib import Path
from unittest.mock import patch
import ts.review.evaluation as e
from ts.review.runner import run_review

cases = e.load_review_dataset(Path('data/review_eval_v1.json'))['cases']
for scenario in ('valid_narrowing', 'valid_correction'):
    case = next(c for c in cases if c['scenario'] == scenario)
    candidate, evidence, base = e._fixture(case)
    evidence.append(e._evidence('evidence-4', 'ror:origin-d', '4'))
    replacement = base['defender']['rebuttals'][0]
    replacement['evidence_ids'] = ['evidence-3']
    replacement['replacement_claim']['evidence_ids'] = ['evidence-3']
    replacement['changed_fields'] = ['statement', 'evidence_ids']
    base['control_critic']['findings'][0]['evidence_ids'] = ['evidence-3']
    second = deepcopy(base['critic']['objections'][0])
    second['objection_id'] = 'objection-2'
    base['critic']['objections'].append(second)
    base['defender']['rebuttals'].append({
        'rebuttal_id': 'rebuttal-2', 'objection_id': 'objection-2',
        'action': 'ADD_EVIDENCE', 'evidence_ids': ['evidence-4'],
        'replacement_claim': None, 'changed_fields': [],
        'statement': 'Independent primary evidence supports the original claim.',
    })
    finding = deepcopy(base['control_critic']['findings'][0])
    finding.update(
        finding_id='finding-2', objection_id='objection-2',
        rebuttal_id='rebuttal-2', evidence_ids=['evidence-4'],
        origin_independent=True)
    base['control_critic']['findings'].append(finding)
    for critic_reverse, defender_reverse in product((False, True), repeat=2):
        outputs = deepcopy(base)
        if critic_reverse:
            outputs['critic']['objections'].reverse()
        if defender_reverse:
            outputs['defender']['rebuttals'].reverse()
        result = run_review(
            run_id='astra-v4-order-proof', candidate=candidate,
            evidence_provider=e._Provider(evidence), gateway=e._Gateway(outputs),
            budget=e._BUDGET, models=e._MODELS)
        with patch.object(e, '_fixture', return_value=(
                candidate, evidence, deepcopy(outputs))):
            measured = e.evaluate_case(case)['proposed']
        assert not e._role_errors(result)
        assert result.decision.verdict == ('HOLD' if critic_reverse else 'REFRAME')
        assert measured['primary_origin_count'] == (1 if defender_reverse else 2)
        assert not measured['unresolved_critical'] and measured['stable']
        print(scenario, critic_reverse, defender_reverse,
              result.decision.verdict, measured['primary_origin_count'],
              measured['evidence_covered'])
PY
```

## Reproduced positive evidence

| Check | Observed result |
|---|---|
| Frozen SHA / pre-report worktree | Exact requested SHA; clean |
| Prior F1 supported non-primary claim | HOLD / critical_claim_unattested |
| Prior F2 executed ablations | Instrumented 96 actual runner executions; 32 per path |
| Prior F3 modified stored confidence / label | Actual CLI subprocess exits 2; stdout/artifact valid=false; one mismatch |
| Prior R1 unbound control | ADD_EVIDENCE, NARROW and CORRECT all HOLD; control invalid_citation |
| Prior R2 unknown critical replacement | HOLD; evaluated unresolved_critical=true |
| Prior R3 provider-failure ablations | Critic plus removed-role failure retained; 300 tokens / $0.002 / 20 fixture ms |
| Prior superseded-evidence flaw | Both CORRECT/NARROW with one replacement origin HOLD; coverage false and origin count 1 |
| Explicit two-origin replacements | Both CORRECT/NARROW REFRAME; coverage true and origin count 2 |
| Ambiguous multiple replacements | Existing actual-runner regression passes within the full suite |
| Full fresh migrated PostgreSQL suite | 439 passed, 1 warning in 15.61 s |
| Read-only reviewer focused runner/contracts/evaluation suite | 57 passed in 3.37 s |
| Ruff / LivingSet | All checks passed; requirements=52 waves=19 forks=13 |
| YAML | plan, forks, requirements, rules-0.1 and rules-0.2 parse |
| Whitespace | a2409f8..3ae2bdc and 9e5cc76..3ae2bdc pass |
| Review and scoring CLI regeneration | Both summary.json/report.md pairs byte-identical |
| Result hashes | Independently recomputed from canonical JSON |
| Bounded added-diff secret-pattern scan | Zero matches; not an exhaustive secret audit |
| Disposable database cleanup | Migration e2c7f6a9b104; exact database dropped; absence count 0 |

The sole full-suite warning is the existing Starlette/httpx deprecation.
The published 16-case fixture results reproduce TP=6, FP=0, FN=0, TN=10,
P/R and exact-verdict accuracy 1.0, and zero encoded unsafe acceptances.
Those metrics do not detect the mixed-action permutation above.

Review result SHA-256:
`a629f9089fb785441e334425eee74bfcf72b73d26e8fe9ce69cd3626d231d37a`.
Scoring result SHA-256:
`fc08036e6e73359e7b99cd39a5e90ffab216938dfc86d779b9d5e9fa9dcce003`.

Database checks used a newly created
`astra_wave4_3ae2bdc_20261013_v4` in healthy local container
`thin-signals-pg-1`, published only at `127.0.0.1:55432`. Before creation the
name was absent. Settings were `TS_DISABLE_DOTENV=1`,
`TS_DATABASE_URL=postgresql+psycopg://ts@127.0.0.1:55432/astra_wave4_3ae2bdc_20261013_v4`,
`TS_PG_PASSWORD_FILE=/opt/thin-signals/.secrets/pg_password` and an empty
`TS_OPENROUTER_KEY_FILE`. The application consumed the authorized password file;
no credential was displayed or copied. Commands were `.venv/bin/alembic upgrade
head` and `.venv/bin/python -m pytest -q -p no:cacheprovider`, with
`PYTHONDONTWRITEBYTECODE=1`. Only disposable test data was removed; rerunning the
same creation/migration/test commands recreates it.

Regeneration ran real `python -m ts.cli review-eval` and `score-replay`
subprocesses with `--out` in temporary directories outside Git. Mismatch probes
passed copies of the 170 original rows through `--records /dev/stdin`.
No frozen dataset or generated artifact was edited.

## Limits and disposition

The prior audit's scope limitations remain: authored contract fixtures do not
establish live-model quality, independent scientific generalization or the
optional ten-signal target. The 170-row scoring replay establishes historical
compatibility; separate scoring quality and production canary gates remain.

**VERIFIED:** the prior exact fixes, complete suite, isolation and artifact
reproducibility above. **UNRESOLVED:** mixed-action order dependence and
divergent effective-evidence reporting. **NEXT TRIGGER:** a new frozen candidate
with unambiguous order-independent claim resolution and independent re-audit.

This report's disposition is C05 FAIL under `GOAL_AGENT=astra-verifier-v4`.
Only that criterion is to be updated; no whole-GOAL verification, production
activation or remote publication is implied.
