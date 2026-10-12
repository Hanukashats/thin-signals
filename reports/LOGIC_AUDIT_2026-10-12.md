# Thin Signals logic audit — 2026-10-12

Status: **read-only audit; fixes are not bundled with the SearXNG upgrade**

## Scope and evidence

Reviewed the live path from connector construction through search, evidence
reading, deterministic scoring, persistence and public output. The review used
the repository at `0c1fdd37cd95`, the 231-test pre-change baseline, current
VM232 health evidence and the isolated SearXNG upgrade canary. It did not alter
`rules-0.1`, `checklist-v15`, stored runs, prompts or database schemas.

## Findings, ordered by risk

### HIGH — a fully failed search is persisted as `succeeded`

`Harness._search()` records per-connector exceptions and continues. Even when
every connector fails, `save_report()` and `public_report()` unconditionally
write/return `succeeded` (`ts/harness.py:166-179`, `ts/persist.py:36-45`,
`ts/persist.py:86-103`). This makes “the search completed” indistinguishable
from “the search infrastructure produced no usable result”.

Required follow-up: define and version a run-state contract such as
`succeeded | degraded | failed`, with explicit minimum-source rules, migration,
API compatibility and regression tests. Do not patch this inside an image
upgrade because it changes persisted/API semantics.

### HIGH — `verified` may be supported only by a search/API snippet

The live call does not pass `fetch_body`, so the harness snapshot stage is
always skipped (`ts/live.py:141-147`, `ts/harness.py:198-213`). The checklist
does enforce an `[n]` reference, which is good, but `_fragments()` normally
uses the connector snippet directly and fetches an abstract only when the
snippet reaches the 500-character truncation cap or no snippets exist
(`ts/checklist.py:31-70`, `ts/checklist.py:123-151`). Therefore a syntactically
cited `verified` judgment can still rest on unpreserved search-result text.

Required follow-up: attach evidence provenance to each fragment and reserve
`verified` for directly fetched, preserved primary-source text. Treat an
unfetched snippet as at most `supported`; fail closed when a claimed source
cannot be retrieved. Backfill/evaluate before changing historical labels.

### MEDIUM — sequential fan-out has no global time budget

The default live path has 15 connectors. It calls all 15 for the main search,
four for the chain query and all 15 for countersearch: up to 34 sequential
external calls. Each HTTP call has a 40-second timeout
(`ts/live.py:250-272`, `ts/harness.py:88-102`, `ts/harness.py:166-179`). The
theoretical pre-LLM delay is therefore about 1,360 seconds (22m40s). This is
consistent with multi-minute production runs, even though normal calls finish
well before their timeout.

Required follow-up: add bounded concurrency, a global run deadline,
per-connector budgets and a durable timing/failure ledger. Preserve stable
ordering and idempotency, and compare source recall before rollout.

### MEDIUM — SearXNG engine diversity is not demonstrated

The old image and the isolated upgrade canary both returned 20 JSON results for
three test queries and remained API-compatible. In those samples every result
reported `google cse`; no second SearXNG engine was observed. Direct OpenAlex,
Crossref, arXiv and other product connectors still provide independent paths,
but the metasearch service itself must not be described as diverse on this
evidence.

Required follow-up: expose engine-level health/latency/result counters and mark
single-engine operation as an explicit degradation. Do not require a fixed
number of results, which would incentivize filler.

### MEDIUM — high-complexity orchestration is expensive to change safely

Static review reports 25 complexity/signature findings. Concentrations include
`score_card` and `apply_checklist` in `ts/checklist.py`,
`validate_scoring_output` in `ts/extract.py`, `dedup` and high-arity methods in
`ts/harness.py`, `normalized_growth` in `ts/scoring/policy.py`, and
`signal_detail` in `ui/views.py`. `ts/desk.py` is 870 lines. These are not
runtime failures, but they raise regression risk around the most sensitive
policy paths.

Required follow-up: behavior-preserving extraction on a separate branch, with
characterization tests before each small change. No scoring or threshold
change belongs in that refactor.

### LOW — cache and HTTP-client lifecycles are implicit

Extraction cache files have no configured retention/size ceiling
(`ts/extract.py:254-298`). `OpenRouterClient` owns a persistent `httpx.Client`
but has no explicit close/context lifecycle (`ts/llm.py:80-95`). These can grow
or retain resources in long-lived workers.

Required follow-up: measure cache growth and open connections, then introduce
bounded retention and an explicit client lifecycle with regression tests.

### LOW — test dependency emits a deprecation warning

The safe suite passes but Starlette's test client emits an httpx-related
deprecation warning. Pin/upgrade the test dependency pair in a separate
maintenance change after confirming application compatibility.

## Controls that are working

- The LLM does not calculate the score; it fills a strict schema and the local
  deterministic scorer decides the label.
- Model allowlisting, mandatory ZDR/no-collection policy and returned-provider
  validation fail closed, including cached outputs (`ts/llm.py`).
- Web fragments are explicitly framed as untrusted content in the extraction
  prompt, and malformed or uncited checklist output is rejected.
- Connector failures are isolated and visible per step rather than aborting the
  whole run on one dead source.
- Idempotency, exclusion reasons and evidence references have regression tests.

## Recommended sequence

1. Land the isolated-canary-verified SearXNG pin as a one-module operational
   upgrade; keep GPT Researcher v3.7.0 unchanged.
2. Version the evidence-provenance rule and total-failure run contract, then
   evaluate them against saved cases before production migration.
3. Add bounded parallel search plus a global deadline and per-connector
   observability; verify recall and stable ordering.
4. Refactor complexity and resource lifecycles without changing behavior.
5. Only after this baseline is trustworthy, experimentally evaluate ADR-011's
   researcher/critic/defender proposal. It remains operator-gated and inactive.

## Verification boundary

This audit is the implementer's evidence-backed review, not independent
acceptance. No finding above authorizes a schema, scoring, prompt or runtime
change by itself.
