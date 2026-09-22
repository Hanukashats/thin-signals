# Adaptive control flow, shortcuts, jumps, and exits

The skill is a **decision DAG**, not a mandatory linear checklist. The goal is to spend the least research/validation effort that can support the user's next consequential decision.

## 1. Classify the decision before choosing the path

Track these independently; do not compress them into one score.

### Decision target
- `EXPLORE` — discover an opportunity space.
- `CHOOSE` — select among known candidates.
- `DE-RISK` — reduce uncertainty on one thesis.
- `TEST` — obtain behavioral/commitment evidence.
- `BUILD` — authorize an experimental or production implementation.

### Reversibility / stakes
- **LOW / two-way:** cheap, fast, reversible, low trust/reputation/compliance cost. A wrong move is easy to undo.
- **MEDIUM:** non-trivial effort, external users/integrations, modest switching/reputation cost, but still recoverable.
- **HIGH / one-way-ish:** meaningful capital/team-months, hardware/capex, regulated or safety-sensitive use, irreversible data/contract/platform commitments, or expensive reputational failure.

### Evidence state
Use claim-level E0–E4 plus hard gates. The same Opportunity Quality score can deserve radically different routes depending on maturity.

### Time sensitivity
If the opportunity window is expiring, the cost of delay matters. Prefer a reversible real-world test earlier when more desk research is unlikely to change the next action.

## 2. Four legal transitions after every meaningful node

After each research or decision node, choose exactly one transition:

- **CONTINUE** — unresolved decision-critical uncertainty still benefits from this path.
- **SKIP** — the node's relevant claims are already sufficiently evidenced/fresh for the current decision, or the node is immaterial to the user's objective.
- **JUMP** — another node now has clearly higher decision value; move directly to it.
- **EXIT** — enough evidence exists to decide, or a terminal condition has been reached.

`RECYCLE` is a special JUMP back to opportunity framing when the problem survives but the buyer, wedge, channel, or solution does not.

Do not continue a phase merely because it appears earlier in the document.

## 3. Global short-circuit rules

Evaluate these after every meaningful evidence update.

### A. Fatal-gate exit
If a hard gate is `FAIL` with sufficiently direct/current evidence and there is no obvious low-cost pivot that removes the failure:
- `EXIT → KILL`, or
- `RECYCLE → PIVOT` if the underlying problem still has evidence.

Do not spend market-sizing, trend, or competitor budget on a candidate already killed.

### B. Decision-stability exit
Stop when plausible additional information is unlikely to change the **next action**. This does not require perfect information.

Examples:
- one candidate already meets the user's threshold and all remaining unknowns are low-impact;
- all survivors lead to the same next experiment;
- a candidate clearly dominates the relevant alternatives and residual uncertainty cannot plausibly reverse the ordering;
- the user asked only for a shortlist and the shortlist is stable.

### C. Test-beats-research jump
If a real-world test can resolve the highest-impact uncertainty more cheaply/faster/directly than further desk research:
- `JUMP → VALIDATION/EXPERIMENT`.

This is the default loop-breaker for research paralysis.

### D. Strong-commitment fast track
If direct target-behavior evidence already exists (e.g. paid pilot, transaction, serious procurement action, repeated paid use) and no fatal dependency is unresolved:
- skip broad discovery;
- skip generic trend research unless timing is material;
- do only the minimum competitor/economics/trust checks needed for the requested investment level;
- `JUMP → R3/R4 diligence or handoff`.

### E. Critical-dependency preflight
If one cheap-to-check dependency could invalidate the entire thesis (API permission, license, legal prohibition, data access, hardware availability, model capability):
- test that dependency **before** broad market research.

A one-hour dependency check outranks a ten-hour market study if failure would kill the project.

### F. Inaccessible-information hold
If a critical claim cannot be resolved with available sources and a real-world test is not currently possible:
- `EXIT → HOLD` with the missing evidence and a re-entry trigger.

Do not loop on equivalent searches.

### G. Non-commercial path
For learning, open-source, public-good, or internal-automation objectives, commercial budget/solution-commitment gates may be replaced by the objective's actual success mechanism (internal ROI, adoption, production use, learning outcome, maintainership burden). Do not force a startup economics workflow onto a non-commercial goal.

## 4. Skip taxonomy: not all skips are equal

Classify every material omitted node as one of:

- **SAFE-SKIP** — the relevant claim is already sufficiently evidenced/fresh for the current decision, or the node is genuinely immaterial to the objective. No special return is expected.
- **DEFERRED-DEBT** — safe to omit for the current reversible/low-commitment action, but it becomes mandatory before a named future commitment. Record the upgrade trigger, e.g. `before storing PHI`, `before annual contract`, `before paid acquisition`, `before production migration`.
- **FORBIDDEN-SKIP** — the node protects against a material legal/safety/security/trust/critical-dependency failure in the current decision. It cannot be bypassed merely to go faster.

Adaptive routing is not permission to rationalize missing diligence. For any consequential skip, record the class and trigger.

## 5. Node dependency table

| Node | Required when | May SKIP when | Preferred JUMP/EXIT |
|---|---|---|---|
| Founder context | founder constraints/edges affect choice | current request already supplies what matters | continue with provisional unknowns rather than block |
| Broad discovery | DISCOVER/SCAN or current thesis must be reframed | VALIDATE/REFRESH/BUILD-HANDOFF with a concrete buyer-job thesis | exit with shortlist if user asked only for opportunities |
| Pain/JTBD | problem/job is vague, inferred, or disputed | directly observed problem is already E2+ and well scoped | pivot/reframe if actor/job cannot be made specific |
| Trend/why-now | timing, platform shift, regulation, category creation, or market acceleration is material | durable replacement workflow where timing does not affect the decision | jump to dependency/validation if timing is not the uncertainty |
| Competitor/status quo | switching/differentiation is unclear; before meaningful production investment | direct buyer commitment + known status quo and only a low-stakes experiment is being authorized | kill if status quo is demonstrably adequate and no switching trigger exists |
| Failure archaeology | category has shutdowns/pivots, no obvious competitors, crowding, or explicit “why did this fail?” question | no analogous failures are decision-relevant | hold/pivot if structural failure mode repeats and cannot be removed |
| Economics | commercial viability affects decision | non-commercial objective; very early problem discovery | jump to paid/commitment test if price uncertainty dominates |
| Market sizing | venture-scale ceiling or portfolio allocation matters | cashflow/micro-SaaS/local wedge where beachhead economics suffice | exit when market ceiling is already clearly above/below threshold |
| Distribution/procurement | first-customer access or switching is uncertain | founder already has direct, current, credible access to buyer/budget owner | jump to outreach/procurement experiment |
| Feasibility/trust | critical dependency, regulated/sensitive data, high operational risk | low-risk prototype with no sensitive/regulated surface and obvious feasibility | dependency-first kill/hold or experimental prototype |
| Multiple solution wedges | solution choice is risky/differentiating or alternatives matter | contract/user constraint already fixes the solution, or a cheap prototype tests the only credible wedge | jump to assumption test |
| Full independent red-team | HIGH stakes or materially irreversible production investment | LOW/MEDIUM reversible decisions after a focused falsification pass | kill/pivot/hold when reviewer finds fatal evidence |
| Validation experiment | a critical claim remains uncertain and can be behaviorally tested | target behavior is already E3/E4 and current | jump to experimental/production handoff |
| Production handoff | R4 or explicit user override | always skip below R4 unless user explicitly requests override | exit with next experiment/research instead |

## 6. Research depth matrix

Use the **minimum sufficient path**.

| Evidence | LOW / reversible | MEDIUM | HIGH / one-way-ish |
|---|---|---|---|
| Sparse (E0/E1) | cheap discovery → direct test quickly | standard discovery + key dependency checks | deep research + dependency/trust first |
| Directional (E2) | jump to experiment if available | focused diligence → experiment | targeted deep diligence + stronger falsification |
| Commitment-near (E3) | fast-track to R3/R4 checks | focused competitor/economics/trust verification | targeted verification, independent red-team, domain sign-off where relevant |
| Target behavior (E4) | build/scale decision with minimal freshness checks | R4 diligence + build | production/scale diligence; do not confuse market evidence with legal/safety authorization |

## 7. Presets: reintroduce useful old rules as conditional branches

### `RAPID-CASHFLOW`
Use when the user explicitly optimizes for near-term solo/small-team revenue.
- Favor replacement lane and existing spend.
- Prefer B2B/prosumer workflows with reachable buyers.
- **72-hour-ish wedge feasibility** may be used as a ranking filter, not a universal hard gate.
- Skip top-down TAM unless it can invalidate the business.
- Prefer direct outreach / paid concierge / deposit over more web research.

### `KNOWN-BUYER`
Use when a real buyer/budget owner and concrete workflow already exist.
- Skip broad market discovery.
- Validate recurrence, value, switching, delivery, price, and dependency risk.
- Competitor work is focused on switching/status quo, not generic landscape mapping.

### `EMERGING-WINDOW`
Use when a new capability/regulation/platform behavior creates the opportunity.
- Start with why-now + affected workflow + budget creation/transfer.
- Do **not** require historical spend as a hard gate.
- Move quickly to a behavior/commitment test because desk evidence will often be sparse.

### `DEEP-VENTURE`
Use when the objective is a large durable company and downside warrants deeper work.
- Broaden opportunities until saturation; ranges such as 10–20 are guidance, never quotas.
- Include market ceiling, durability, category dynamics, failed analogs, and independent red-team.
- Do not use the 72-hour build filter.

### `REGULATED/ONE-WAY`
Use for health, finance, safety, identity, sensitive data, hardware/capex, or high irreversible commitments.
- Run feasibility/trust/dependency checks early.
- No shortcut around material legal/security/safety constraints.
- A good market score cannot authorize a prohibited/unsafe product.

### `DEVTOOL/OSS`
- Early evidence can be repeated external production use, retention, integrations, pull-through demand, and support burden.
- Delay direct willingness-to-pay requirements until a commercial monetization decision is being made.
- Before claiming commercial validation, require a credible paid path.

### `INTERNAL-AUTOMATION`
- Replace external TAM/WTP with internal workflow cost, risk, owner, deployment friction, measurable ROI, and adoption.
- Skip broad competitor research if build-vs-buy can be resolved cheaply from current vendors.

## 8. Loop breakers

A research loop is **stalled** when either:
- two consecutive independent search waves do not add a materially new opportunity/critical claim, or
- two waves do not upgrade the evidence maturity of the targeted claim, or
- the same source families keep repeating the same origin.

When stalled, do one of four things:
1. change evidence method (customer interview, internal data, expert, procurement, prototype, direct dependency check);
2. narrow/reframe the claim;
3. `HOLD` with a re-entry trigger;
4. `KILL/PIVOT` if negative evidence is sufficient.

Do not issue a third near-identical web-search wave by default.

For experiments, two inconclusive tests of the same hypothesis/method trigger a redesign of the hypothesis, segment, metric, or test method rather than simple repetition.

## 9. Minimal falsification rule

Counterevidence remains mandatory, but **depth is proportional to stakes**:
- LOW: one deliberate falsification pass is normally enough before a reversible experiment.
- MEDIUM: claim-specific rebuttal search for finalists.
- HIGH or materially irreversible production: independent adversarial review plus domain-specific checks where applicable; LOW/MEDIUM reversible R4 may use focused falsification if remaining risk is bounded.

This prevents both confirmation bias and red-team theater.

## 10. What “done” means

The skill is done when it can state:
1. the user's next decision;
2. the primary next action;
3. why further information is not currently worth more than that action;
4. which modules were skipped and why, if the skip is decision-relevant;
5. the explicit re-entry trigger for `HOLD` or `PIVOT`.

“Done” does **not** mean every reference file was consulted or every node was visited.
