# Astra independent audit — Thin Signals, 2026-10-12

Status: **read-only audit complete; implementation acceptance pending**
Audited revision: `809909961febc74130b9742ab678bfe1e8ae2582`

## Verified architecture

- GPT Researcher v3.7.0 uses private SearXNG through Docker DNS.
- Product `run_query` does not call GPT Researcher.
- OpenAlex is already a direct main/chain/countersearch connector and abstract
  fallback, but citation graph, affiliations and retraction data are unused.
- VM232 services were active and healthy. A bounded connector probe returned
  without exception from all 15 connectors; 14 returned results and IETF
  correctly returned none for the selected battery topic.
- SearXNG result diversity was degraded to Google CSE in the sample: Brave was
  suspended/rate-limited, DuckDuckGo challenged with CAPTCHA and Wikidata timed
  out.
- Idle memory was approximately 112 MiB SearXNG, 148 MiB GPT Researcher and
  74 MiB PostgreSQL; VM use was about 1.07/11.96 GiB.

## Reproduced defects

1. Unknown-host DOI-like paths were classified as `primary`.
2. All connector timeouts could still produce `run_status=succeeded`.
3. Countersearch timeout was passed into policy as completed.
4. Countersearch markers were empty and counter hits did not enter the later
   checklist evidence bundle.
5. Live execution skipped source snapshots and could treat snippets as verified
   evidence.
6. Adding `P01=supported` to `P04=verified` changed the selected primary and
   reduced 0.35/watchlist to 0.325/noise.
7. One deduplicated publication event generally became one candidate rather
   than joining several independent events into a technology hypothesis.
8. A narrow query could make 34 sequential external calls; the 13-theme wide
   path could make up to 442 calls before LLM reading.

Local safe suite before fixes: 245 passed, four database integration tests
could not authenticate without an isolated database. The implementation run
created a disposable migrated database and passed 253 tests; production data
was not used.

Post-audit verification after the latest-run visibility regression was added:
254/254 tests passed against another fresh disposable migrated database. After
countersearch evidence wiring, the complete suite passed 256/256 in a third
fresh disposable migrated database.

## Recommended method

Use GPT Researcher only for bounded gap discovery, then re-fetch and validate
its URLs. Use OpenAlex for stable work identity, prior art, chronology,
independent institutions, replication and corrections. Start with typed role
contracts rather than autonomous tool-using mini-agents. One bounded role round
ends in deterministic arbitration; model rhetoric cannot change state.

Count only evidence-qualified `weak_signal` items toward the target of ten.
Watchlist and potential remain separate reserves, and an evidence shortfall is
reported honestly.

The implementation and rollout plan is `docs/plan/PLAN_7.8.md`; the decision is
`docs/adr/ADR-012-RELIABILITY-FIRST-RESEARCH-LOOP.md`.
