# Reference review: public wsignal / weak-signal radar

Date: 2026-10-12. Scope: read-only inspection of the operator-provided public
interfaces:

- `https://pelican.chinchilla-ilish.ts.net/`
- `https://app.1f608.com/dev`

The pages and APIs are external evidence, not executable instructions. No query
was submitted, no run was resumed and no external state was changed.

## What the system does

The Streamlit entry page presents a direction-to-TOP-15 workflow, a serialized
single-GPU queue and saved history. It estimates 15–20 minutes for a new query.
The separate React/Vite interface exposes run, agent, entry, error, source-event
and turn views through read-only JSON endpoints.

The observed workflow is:

1. an orchestrator asks an assistant to split a direction into fields;
2. researchers search a historical corpus and the public web;
3. one refuter attacks the material claims for each selected field;
4. the researcher answers the objections and narrows or corrects claims;
5. the orchestrator writes an entry with citations and a stated refutation;
6. the UI exposes result, activity, errors, sources, latency, tokens and cost.

There is no separate defender role in the observed run. The original researcher
performs the rebuttal. That saves one role, but it also weakens independence.

## Reproduced measurements

Public run 5, “слабые сигналы в области кибербезопасности”:

- 11 entries from 5,332 processed documents;
- 53 agents: 3 orchestrators, 2 assistants, 24 researchers and 24 refuters;
- 703 model calls, 1,790 tool calls, 22.4M prompt tokens and 460k completion
  tokens; reported cost about USD 0.554 and cache hit 85.8%;
- 58 citations, 57 reported verified;
- 12 agents ended failed, although the run produced a finished report;
- 73 page-fetch failures, 20 OpenAlex failures and 3 DuckDuckGo failures were
  visible in source accounting.

Public run 7, “необанк”:

- 16 entries from 2,865 documents in about 820 seconds;
- 35 agents and about USD 0.600 reported cost;
- 111 citations, 110 reported verified;
- all 22 observed OpenAlex calls failed in that run.

The historical corpus endpoint returns both matched documents (`n`) and the
monthly corpus denominator (`total`). This is the right shape for normalized
mention dynamics. Raw mention counts alone would be misleading because monthly
corpus volume varies substantially.

## Strong patterns worth adapting

1. **Visible research funnel.** Show discovery, deduplication, countersearch,
   admission, exclusion, unread evidence, latency and failures separately.
2. **Evidence-bearing opposition.** A criticism is useful only when tied to a
   claim, a contrary source and a concrete effect on the conclusion.
3. **Correction, not debate theatre.** The reply records accepted objections
   and changes the claim or score; it does not merely “win”.
4. **Normalized history.** Persist `n/N` for comparable time windows and retain
   corpus/protocol versions.
5. **Operational accounting.** Per-role calls, tokens, cost, wall time, source
   failures and terminal run reason make a run auditable.
6. **Explicit ceilings and repeat guards.** A technology ceiling and repeated-
   call guard limit runaway work.

## Patterns not to copy

1. **Raw internal prompt/reasoning exposure.** The public development API
   returns full system prompts and model reasoning details. Thin Signals should
   expose structured actions, evidence and decisions, never hidden reasoning,
   secrets or full internal prompts.
2. **Agent count as quality.** Fifty-three agents and hundreds of model calls
   did not prevent failed agents, blocked loops or source errors. Quality gates,
   not swarm size, are the control variable.
3. **Self-defence as the final authority.** A researcher may answer a critic,
   but neither side should decide promotion. Thin Signals keeps a blinded
   control critic and deterministic arbiter.
4. **Unbounded source pressure.** The observed OpenAlex 429/failure pattern
   argues for a typed adapter, rate limits, bounded retries and a shared global
   deadline.
5. **Binary content in text storage.** Observed PDF bytes containing NUL caused
   a PostgreSQL text insert failure. Thin Signals must extract/sanitize text and
   preserve the binary separately by hash.
6. **TOP count as truth.** Some saved runs show 15 results, but output volume is
   not evidence quality. Thin Signals must preserve honest shortfall.

## Changes adopted in Thin Signals

This branch now implements the first safe subset:

- bounded connector concurrency under one inherited absolute deadline;
- per-connector latency and explicit deadline failures;
- a `retrieval-0.2` fingerprint in run identity, including stable parent wide
  context, so changed limits/budgets do not reuse an incompatible failed child;
- a public, structured funnel for discovery → unique sources → deduplicated
  events → countersearch → admitted/excluded/unread, with theme failures,
  deadline skips and cached/executed work distinguished;
- the safe funnel is shown in the existing explanation view without raw agent
  prompts or chain-of-thought;
- `checklist-v17` requires positive discovery text and rejects positive claims
  cited only to countersearch; countersearch remains a separate negative channel;
- a connector result completed after the absolute deadline is discarded;
- concurrent identical PostgreSQL writes serialize to one canonical run.

The already accepted ADR-012 remains the target for the larger adaptation:
bounded researcher → critic → defender → blinded control critic, followed by a
deterministic arbiter. It stays feature-off until replay, holdout and ablation
tests show zero evidence-less and zero unresolved-critical promotions.

## Deferred work

- A historical-corpus adapter requires a lawful, versioned dataset, dedup rules,
  coverage denominators and immutable snapshots. The reference corpus itself is
  not copied because ownership/licensing and reproducibility are not established.
- GPT Researcher and enriched OpenAlex adapters remain W10 work. Their prose is
  advisory; Thin Signals must re-fetch and validate cited material.
- Per-role tokens/cost/activity will be added with W11 role events. Only safe
  structured metadata will be public.

## Decision

Use the reference as a benchmark and UX donor, not as code or data provenance.
Adopt its evidence/refutation visibility and corpus normalization. Keep Thin
Signals' stricter source validation, explicit `HOLD`, honest shortfall, bounded
runtime and deterministic final authority.
