# Routing, depth, presets, and stop conditions

This reference chooses the **minimum sufficient path**. Read [adaptive-control-flow.md](adaptive-control-flow.md) only when a non-trivial skip/jump/preset/high-stakes/stalled-loop decision actually needs it.

## Mode entry and exit

### DISCOVER
Use when the founder can build many things but lacks a target.
- Entry: no committed target-actor/job thesis.
- Minimum path: objective → cheap breadth scan → early hard-gate triage → shortlist.
- Add diligence only to survivors whose ranking/next action could change.
- Exit as soon as a stable shortlist + next action satisfies the request; do not automatically continue to validation/build.

### SCAN
Use when the starting point is an external change.
- Entry: technology, platform, regulation, demographic, labor, cost, security, or market shift.
- Minimum path: change → affected actor/workflow → value/resource/behavior mechanism → candidate opportunities.
- Prefer `EMERGING-WINDOW` preset when historical spend is not expected.
- Exit with opportunity theses and the smallest tests that can distinguish them.

### VALIDATE
Use when a concrete idea/wedge exists.
- Skip broad discovery unless normalization reveals the target-actor/job thesis is broken.
- Search disconfirmation early.
- Exit with research / validate / experimental build / production build / pivot / hold / kill.

### COMPARE
Normalize candidates to target actor + job + status quo + outcome + archetype/model + objective. Research **only dimensions capable of changing the ordering or next action**. If one candidate is decision-stably dominant, stop comparison early.

### REFRESH
Load the previous run. Re-check only claims whose freshness/materiality can change the decision: entrants, pricing, regulation, platform/API capability, buyer behavior, major shutdowns, and stale critical evidence. Preserve historical evidence.

### BUILD-HANDOFF
- R0–R2: production handoff is not justified; give research/validation or an explicit override path.
- R3: experimental prototype/concierge handoff.
- R4: narrow production handoff allowed.
- HIGH/one-way decisions may still require domain-specific legal/security/safety authorization outside this skill.

## Depth is a ceiling, not a checklist

### FAST
Goal: determine what deserves more attention.
- cheap breadth or one focused validation;
- one deliberate falsification pass for a finalist;
- directional economics only if material;
- jump to a direct test early when it is more informative than browsing.

### STANDARD
Goal: robust next-decision quality.
- claim-level triangulation only for promoted finalists;
- current status quo/competitor/economics/distribution checks as relevant;
- one focused red-team;
- explicit next experiment or terminal action.

### DEEP
Goal: support meaningful irreversible investment **where the risk warrants it**.
- broaden until saturation, not to a candidate quota;
- run failure archaeology only when analogous failures are material;
- include distribution/procurement and trust/security/compliance when relevant;
- top-down market cross-check only when market ceiling matters;
- independent adversarial review for high-stakes finalists.

A DEEP request does not force every module. It permits deeper work where uncertainty and stakes justify it.

## Scheduling rule: cheapest fatal uncertainty first

Before spending heavily, identify the uncertainty that is:
1. capable of killing or rerouting the thesis;
2. cheap/fast to resolve;
3. currently unknown.

Examples: API permission, target-actor reachability, legal prohibition, data availability, a known status quo that may already be adequate. Resolve those before market-size decks or broad competitor archaeology.

## Promotion funnel

1. **Breadth scan** — cheap discovery only when needed.
2. **Triage** — obvious hard gates and critical dependencies immediately.
3. **Promote** — only plausible candidates get economics/status-quo/distribution depth.
4. **Diligence** — only decision-relevant finalists get full falsification/risk analysis.
5. **Experiment** — desk research stops when a real-world test has greater decision value.
6. **Commit** — production investment only when readiness/stakes justify it.

## Stop / jump conditions

Immediately evaluate after each research wave:
- reliable hard `FAIL` → KILL/PIVOT;
- critical unknown resolvable by direct test → JUMP to that test;
- strong target-behavior evidence + no fatal unknown → fast-track focused diligence/handoff;
- no decision-changing value from more research → EXIT with decision;
- information inaccessible and no useful test available → HOLD;
- two consecutive non-upgrading search waves → change method or stop;
- opportunity window expiring + reversible test available → prefer the reversible test over more browsing.

## Presets

Choose only when the request matches:
- `RAPID-CASHFLOW`
- `KNOWN-BUYER`
- `EMERGING-WINDOW`
- `DEEP-VENTURE`
- `REGULATED/ONE-WAY`
- `DEVTOOL/OSS`
- `INTERNAL-AUTOMATION`

Preset details and the reintroduced conditional rules (e.g. 72-hour wedge, existing-spend bias, broad candidate ranges) are in [adaptive-control-flow.md](adaptive-control-flow.md).


## Forced-decision / deadline rule

If the user must choose before additional evidence can realistically arrive, do not hide behind `RESEARCH`. Make a provisional choice using:
- current evidence/readiness;
- reversibility and expected regret;
- the smallest option-preserving hedge;
- explicit confidence;
- the first post-decision check that could reverse or unwind the choice.

This rule never authorizes bypassing verified legal/safety/security/critical-dependency prohibitions.
