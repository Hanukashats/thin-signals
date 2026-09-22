# Decision model: gates, quality, evidence maturity, and readiness

Keep **Opportunity Quality**, **Hard Gates**, **Evidence Maturity**, and **Decision Readiness** separate. Never compress them into one universal rank.

## 1. Hard gates

Evaluate each gate as `PASS | UNKNOWN | FAIL`.

For consequential `FAIL`, prefer an evidence-linked form:

```json
{
  "state": "FAIL",
  "confidence": "verified",
  "scope": "current_wedge",
  "evidence_refs": ["ev-42"],
  "note": "API terms prohibit this use case"
}
```

`confidence` may be `verified | supported | weak | unspecified`.

- `verified/supported FAIL` can terminally kill or reroute the affected scope.
- `weak/unspecified FAIL` means **verify the gate**, not automatic kill.
- `scope=current_wedge` may allow a pivot; `scope=whole_problem` is broader.

### G1 — Specific actor + job/outcome
Can you name the actor/user, buyer/value owner where different, circumstance, desired outcome, and current alternative?

### G2 — Meaningful consequence
Is there credible evidence of recurrent or high-consequence cost, delay, risk, lost revenue, effort, cognitive load, failure, or another material consequence?

### G3 — Viable value mechanism for this objective
Interpret by archetype:
- **commercial:** existing budget/spend/labor/economic loss or credible budget creation/transfer;
- **internal:** measurable workflow cost/risk/throughput gain plus an owner/sponsor/resource mechanism;
- **devtool-oss:** material user/developer value plus a feasible maintenance/resource model; paid path is required only before claiming commercial validation;
- **noncommercial:** a concrete success/impact mechanism appropriate to the stated objective.

### G4 — Reachable adoption path
Is there a concrete way to reach/activate the first relevant users/buyers and a plausible adoption or switching trigger?

### G5 — Deliverable and trustworthy wedge
**Assuming required dependencies are available**, can the narrow outcome be delivered with acceptable technical quality, operational burden, privacy, security, compliance, safety, and accuracy for the current commitment level?

### G6 — Credible reason to adopt/switch
Is there a meaningful buyer/user reason to choose this wedge over the current status quo or alternatives?

Do **not** require a venture-style moat here. Durability/compounding advantage is scored separately and becomes strategically stricter for venture objectives.

### G7 — Critical dependencies available/obtainable
Are required external dependencies available or realistically obtainable: license, dataset, API permission, platform policy, regulatory authorization, hardware, partner, or model capability?

This gate is about **availability/permission**, not delivery quality. Avoid double-counting the same issue under G5 and G7.

## 2. Opportunity Quality

Score six pillars 0–5. A rating must be evidence-backed or explicitly provisional.

1. **Demand** — severity/consequence, recurrence, observed job, dissatisfaction/status quo friction.
2. **Economics / Resource Leverage** — commercial value capture, internal ROI, or resource efficiency appropriate to the archetype.
3. **Adoption** — reachability, switching/adoption trigger, procurement/onboarding friction, buyer/user clarity.
4. **Execution** — technical/operational feasibility plus founder domain/build/ops edge. Do not include distribution here.
5. **Timing & Market** — why-now or durable demand, beachhead depth, category/market ceiling when relevant.
6. **Durability** — recurrence/retention and compounding defensibility/maintainability after the initial wedge.

### Objective profiles

| Pillar | balanced | cashflow | venture |
|---|---:|---:|---:|
| Demand | 25 | 25 | 20 |
| Economics / Resource Leverage | 20 | 25 | 15 |
| Adoption | 20 | 20 | 15 |
| Execution | 15 | 15 | 10 |
| Timing & Market | 10 | 5 | 20 |
| Durability | 10 | 10 | 20 |
| **Total** | **100** | **100** | **100** |

These are operational defaults, not calibrated priors. Select the profile **before** comparing candidates. Never tune weights after seeing a preferred winner.

### Aggregation

`quality = Σ(weight × rating / 5)`

Treat the result as a transparent heuristic, not probability. Always show pillar ratings and weakest pillar.

## 3. Claim Evidence Maturity

Use the same storage keys for portability, but interpret them by archetype.

- **E0 — absent:** pure assumption.
- **E1 — weak/directional:** inference, secondary attention signal, isolated anecdote, vendor claim, weak proxy.
- **E2 — observed/triangulated:** direct observation/past behavior or multiple independent relevant observations.
- **E3 — commitment-near:** costly/revealing behavior close to the target decision.
- **E4 — target behavior:** actual intended/near-intended use, transaction, deployment, renewal, repeat/retained use, or equivalent target outcome.

Stored claim keys:
- `problem`
- `budget`
- `switching`
- `distribution`
- `feasibility_trust`
- `solution_commitment`
- `retention`

### Claim semantics by archetype

| Claim key | commercial | internal | devtool-oss / noncommercial |
|---|---|---|---|
| problem | real buyer/user problem | real internal workflow problem | real user/developer/impact problem |
| budget | spend/value-transfer path | internal cost/ROI/resource owner | optional monetization/resource mechanism |
| switching | willingness to leave status quo | adoption/migration friction | adoption/migration friction |
| distribution | customer acquisition/access | rollout/access to internal users | user/community/distribution path |
| feasibility_trust | delivery/trust | delivery/trust | delivery/maintainability/trust |
| solution_commitment | paid/procurement/use commitment | sponsor/deployment/use commitment | repeated external use/integration/maintainer/user commitment |
| retention | renewal/repeat use | sustained internal use | retained/repeated use/maintainership |

A job posting can support `problem` and sometimes `budget`; it does not prove `solution_commitment`.

### Replication / independence

E-level captures **proximity/strength**, not total confidence. Also inspect:
- number of independent support origins;
- segment match;
- counterevidence;
- freshness where material.

Do not use one universal sample threshold. Stakes/archetype determine how much replication is adequate.

## 4. Archetype-aware Decision Readiness

Readiness describes what commitment the evidence supports.

- **R0 — thesis/block:** pure thesis or verified structural hard failure.
- **R1 — researchable:** plausible, but key claims remain E0/E1.
- **R2 — validation-ready:** enough reality for targeted validation/direct testing.
- **R3 — experimental-build-ready:** narrow prototype/concierge/deployment is the cheapest high-information test.
- **R4 — production-build candidate:** evidence supports meaningful production investment for the selected archetype; external domain authorization may still be required.

### Commercial defaults

- **R2:** no terminal verified FAIL; `problem >= E2`; `budget, distribution, feasibility_trust >= E1`.
- **R3:** `problem >= E2`, `budget >= E2`, `switching >= E1`, `distribution >= E2`, `feasibility_trust >= E2`, `solution_commitment >= E2`.
- **R4:** all hard gates PASS; `problem >= E3`, `budget >= E3`, `switching >= E2`, `distribution >= E2`, `feasibility_trust >= E3`, `solution_commitment >= E3`. Retention may be lower for a new product but recurrence must be credible.

### Internal defaults

- **R2:** `problem >= E2`, `distribution >= E1`, `feasibility_trust >= E1`.
- **R3:** `problem >= E2`, `distribution >= E2`, `feasibility_trust >= E2`, `solution_commitment >= E2` where commitment means sponsor/deployment/use commitment.
- **R4:** all hard gates PASS; `problem >= E3`, `distribution >= E2`, `feasibility_trust >= E3`, `solution_commitment >= E3`, and `retention >= E2` or a clearly evidenced recurring internal workflow. External WTP is not required.

### Devtool/OSS defaults

- **R2:** `problem >= E2`, `distribution >= E1`, `feasibility_trust >= E1`.
- **R3:** `problem >= E2`, `distribution >= E2`, `feasibility_trust >= E2`, `solution_commitment >= E2` where commitment can be repeated external production use/integration/adoption.
- **R4:** all hard gates PASS; `problem >= E3`, `distribution >= E2`, `feasibility_trust >= E3`, `solution_commitment >= E3`, `retention >= E2`. Paid evidence is required only when claiming a commercial business, not for a mature OSS release decision.

### Noncommercial defaults

Use the `devtool-oss` structure but replace monetization with the declared impact/success mechanism. Never call the opportunity commercially validated without commercial evidence.

### Venture objective guard

A venture objective does not make durability a universal gate, but before calling something an R4 **venture-scale production candidate**, require no material unresolved durability/category-ceiling blocker. If durability is weak or unknown, keep the product buildable but label the venture thesis unresolved.

## 5. Comparison rule

Do not emit one default scalar rank across heterogeneous candidates.

Show separately:
1. **Quality/upside view**;
2. **Readiness/commitment view**;
3. **Pareto frontier** across quality and readiness;
4. the **next discriminating action**.

A candidate can lead on upside while another leads on readiness. That is information, not a scoring failure.

## 6. Override rule

A user may override a readiness recommendation for a reversible prototype or consciously speculative build after unresolved risk is stated.

An override **never converts** a verified illegal/safety/security/critical-dependency FAIL into PASS or authorization.
