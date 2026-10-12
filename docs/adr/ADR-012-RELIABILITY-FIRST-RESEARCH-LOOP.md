# ADR-012 — Reliability-first research and adversarial review

Status: **accepted; implementation in progress, activation gated by evaluation**
Date: 2026-10-12
Decision class: major methodology, persistence and runtime change

## Context

The local SearXNG and GPT Researcher services are healthy, but the product path
does not call GPT Researcher. The audit also reproduced four unsafe behaviours:

- an arbitrary hostname could become `primary` when its path looked like a DOI;
- total connector failure was persisted as `succeeded`;
- failed countersearch was passed to policy as completed;
- adding positive evidence could reduce a candidate's score after primary-pattern
  reassignment.

The live path usually evaluates one publication as one candidate. It does not
yet aggregate several independent events into a technology hypothesis. A quota
of ten results therefore cannot be repaired honestly by lowering thresholds.

## Decision

1. Repair evidence and run-state invariants before enabling agentic review.
2. Version run semantics as `run-status-0.2`: `succeeded`, `degraded`, and
   `failed` are separate from the signal label. A failed countersearch is not
   represented as complete and cannot silently admit a card.
3. Source trust is determined by the normalized hostname and source type.
   DOI-shaped path text on an unknown host never raises trust.
4. Add bounded concurrency, a global deadline, per-source timings and a durable
   pipeline fingerprint before increasing search breadth.
5. A verified claim requires fetched, preserved primary-source text. A search
   snippet is at most `supported`.
6. Integrate GPT Researcher through its pinned v3.7.0 native interface as an
   optional, disabled-by-default evidence-discovery adapter. Its report and
   model prose are advisory; URLs are re-fetched and validated by the product.
7. Keep OpenAlex as a typed product adapter for DOI/work identity, prior art,
   chronology, author/institution independence, retractions and replication.
   Crossref/OpenAlex/SearXNG views of one work count as one origin.
8. Implement one bounded researcher → critic → defender → blinded control
   critic round. Only a deterministic arbiter may produce `PROMOTE`, `REFRAME`,
   `HOLD` or `REJECT`. Invalid model output produces `HOLD`; it does not reject
   the underlying technology. A reframe creates a new candidate revision and
   repeats the critical gates.
9. `target_signals=10` is a retrieval/evaluation objective, not an admission
   rule. It counts only `weak_signal`, never watchlist/potential. If evidence
   supports fewer, the product reports the shortfall and a separate reserve.
10. Any scoring correction is a new rules version with frozen replay, separate
    holdout, ablations and independent verification. Historical decisions stay
    immutable.
11. Public activity views expose structured role, state, tool category, evidence
    references, latency, tokens, cost and errors. They never expose raw system
    prompts, hidden model reasoning, credentials or unrestricted tool payloads.
12. Historical mention dynamics use comparable versioned corpus windows and
    persist both numerator and denominator. A large crawl or raw mention count
    is not itself evidence of momentum.

## Upstream boundary

No GPT Researcher fork is introduced. The first adapter uses synchronous
`POST /report/` inside a bounded worker. In exact v3.7.0, background report IDs
do not provide the same JSON evidence contract, so background polling is not
assumed without a separate upstream contract test.

## Activation gates

- zero evidence-less promotions;
- zero promotions with unresolved critical objections;
- false-promotion rate no worse than baseline;
- reproducible verdict from the same frozen ledger;
- accepted latency and cost;
- backup, rollback and independent release verification.

The feature flag remains off until all required gates pass. Deadline or target
count never turns `UNKNOWN` into `PROMOTE`.

The operator-provided public wsignal reference was inspected read-only. Its
evidence-bearing refutation, normalized corpus series and run accounting are
useful donor patterns; its high agent count, raw prompt/reasoning exposure and
observed source failures are not. Detailed evidence and adaptation decisions are
recorded in `reports/REFERENCE_WSIGNAL_REVIEW_2026-10-12.md`.

## Consequences

PostgreSQL remains the only writable product ledger. GOAL remains the single
development controller. Role prompts cannot call shell, deployment or database
tools, and web/model output remains untrusted data.
