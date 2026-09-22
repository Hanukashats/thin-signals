# Research and evidence protocol

Evidence quality depends on what claim it supports, how directly it maps to target behavior, and whether its origin is independent. Source count alone is not evidence strength.

## Critical-claim coverage

For each finalist maintain claim coverage for:
- `problem`
- `budget`
- `switching`
- `distribution`
- `feasibility_trust`
- `solution_commitment`
- `retention` when observable

A candidate is not "well researched" because it has many links. It is well researched when the decision-critical claims have appropriate independent evidence and known counterevidence.

## Evidence roles

Common evidence types and what they can support:

| Evidence | Strongest normal use | What it does **not** prove by itself |
|---|---|---|
| Paid pilot / transaction / renewal | solution commitment, budget, target behavior | total market size |
| Deposit / preorder / procurement action | budget, solution commitment | retention |
| Existing invoice/spend/labor budget | problem economics, budget | willingness to switch to your product |
| Job/gig/RFP posting | problem occurrence, budget allocation | product demand/solution commitment |
| Usage/workflow observation | problem, recurrence, workflow reality | willingness to pay unless money involved |
| Paying-user reviews / cancellations | pain, switching forces, competitor gaps | market size |
| Past-behavior interview | problem, workflow, buying process | target purchase behavior unless commitment occurs |
| Community posts | language, pain discovery, hypotheses | market sizing or product willingness-to-pay |
| Search/trend data | attention/trajectory | budget or urgency |
| Vendor page | current features/pricing/status | independent proof that customers value them |
| Analyst/industry report | market structure/sizing hypothesis | customer-level willingness to pay |
| Founder/agent inference | hypothesis generation | observed fact |

## Evidence record

Use `assets/evidence-record.schema.json`. Material records should contain:
- `id`
- `candidate_id` or `market`
- `claim`
- `claim_kind`: `OBSERVED | INFERRED | PROJECTED`
- `stance`: `support | rebut | neutral`
- `signal_for`: one or more critical claims the record actually informs
- `evidence_type`
- `source_ref` — URL, interview ID, internal metric ID, document reference, etc.
- `source_url` when a public URL exists
- `source_family`
- `independence_key` — common origin used for deduplication
- `source_title`
- `published_at` if known
- `observed_at`
- `actor_or_segment`
- `commercial_signal` when relevant
- `notes`

`source_url` is intentionally optional: a customer interview, internal usage metric, invoice, or user-supplied document can be stronger evidence than a public URL.

## Independence

Different domains can repeat one press release; one domain can contain many independent customer observations. Use `independence_key` to capture the **origin**, not merely the hostname.

Examples:
- ten articles repeating one company announcement → one origin;
- ten unrelated G2 reviews → multiple customer origins even on one domain;
- reposted Reddit/HN content from one author/event → one origin.

## Freshness policy

Freshness depends on claim type. Treat these as defaults, not universal laws:
- current pricing/product availability/API capability/platform policy: verify now; prefer <=30 days or the current primary page;
- rapidly changing AI/model economics/capability: verify now; prefer <=30 days;
- current laws/regulation: use current official source and effective date;
- active competitor trajectory/funding/team claims: prefer <=90 days when material;
- stable workflow pain/history: older evidence can remain useful if the workflow still exists;
- shutdown/failure history: historical sources are appropriate, but separate historical fact from current inference.

Mark stale material when it could change the decision. REFRESH mode re-checks stale claims rather than silently reusing them.

## Source-role discipline

- Prefer primary sources for current product status, pricing, API/technical capability, laws, and company announcements.
- Prefer independent customer/behavioral sources for pain and adoption.
- Vendor claims are valid observations of what the vendor says, not independent validation.
- Analyst reports can structure a market estimate but should expose methodology/denominator where possible.
- Online complaints over-sample vocal users. For quiet professional/regulatory markets, use job descriptions, procurement/RFPs, audit findings, SOPs, professional forums, support tickets, or user-provided internal evidence.

## Counterevidence

For each finalist attack the **critical claims**, not just the keyword:
- Is the status quo actually good enough?
- Is the problem rare or low consequence?
- Is there budget but no switching willingness?
- Is the buyer unreachable or procurement-heavy?
- Is the enabling technology unreliable/illegal/untrusted?
- Did similar products fail because the business model was structurally bad?
- Is demand shrinking or being bundled by incumbents?

A single negative search is not enough if it does not touch the fatal assumptions.

## Research saturation

Stop broadening when:
- successive independent searches add no new buyer-job cluster or materially new critical claim;
- promoted candidates have enough evidence to choose the next experiment;
- remaining candidates repeatedly hard-fail;
- additional desk research has lower expected decision value than a customer/behavioral experiment.

## Common failure modes

- counting source quantity rather than claim coverage;
- treating job postings as product demand;
- treating social engagement as buyer demand;
- counting syndicated content as independent evidence;
- using top-down TAM to rescue weak buyer evidence;
- treating vendor marketing as customer proof;
- stale pricing/product facts;
- over-indexing on online-visible pain;
- searching only for confirmation;
- storing exact quotes or personal details when a de-identified paraphrase is sufficient.
