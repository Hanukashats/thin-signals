# Search duration and preserved depth

Delivery package date: 2026-09-29. Evidence and timing methodology are audited below.

The earlier “about ten minutes” was a rough estimate. Reconstructed from the
command-start log and persisted completion, the fresh production query on
2026-10-01 took approximately **8m13s**; the immediately preceding equivalent
staging query took **8m51s**. Production was about 37 seconds (7%) faster.
These are approximate wall-clock reconstructions, not server timer readings.

Both queried `anode-free sodium metal pouch cell` with `limit=2`, `extract=true`,
`checklist-v15`, model `openai/gpt-5.6-luna`, provider Azure, and found 48 source
records. Production admitted **2 watchlist observations / 2 potential items**;
staging admitted **4 / 3**. Their deterministic run ID `8a6c40db48148710` is the
same in different databases and does not make them the same computation.

The prior production run of the same query on 2026-09-28 used `live-w3` without
a persisted checklist and had 30 sources / 14 admitted cards. Its duration is
not recoverable from available evidence. Do not claim an old-to-new speed
ratio. `runs.created_at` and `finished_at` are both assigned at save time;
their difference is database writing time, not research time.

## Why a fresh search is slow

Production stored 32 successful extraction responses totalling 383.527 seconds
of LLM latency, about 78% of the reconstructed total. Staging stored 34 responses
totalling 404.158 seconds. The rest includes sequential connector requests,
reading abstracts, failures, and additional explanations; there is no complete
persisted stage timer. A repeated query reads the saved result and is not a
new search.

Persistent services use a separate cache directory. The extraction and policy
cache versions also invalidate old replies with unverified provenance. The
first request after the transition is cold. Additional potential explanations
are extra work and do not replace the primary checks.

## No weakening in the latest search release

The audit compared production baseline `66581d0` with `f7a5a9d`: scoring files,
weights and thresholds are unchanged. The connector set/depth, chain search,
countersearch, six-fragment limit, four per-theme replacement attempts,
backfill cap 52, model token budget, timeouts and sequential execution are
unchanged. The 365-day wide-scan window and daily cache key predate this release.

Evidence gates became stricter: exact P01–P18/M01–M06 structure, actual `[n]`
fragment references for verified claims, off-topic rejection, and checked
model/provider/cache policy. Fewer admitted cards therefore do not imply fewer
retrieved sources. In the production sample 10 cards had `evidence_invalid`
and 3 had `reader_failed` with `LLMError`; one run does not establish recall or
research quality.

## Audit sources

- `ts/persist.py`, `ts/live.py`, `ts/harness.py`, `ts/checklist.py`,
  `ts/extract.py`, `ts/llm.py`, `ts/scale.py`, `ts/reach.py` and the Git diff.
- Read-only metadata from production and isolated test PostgreSQL databases.
- Command-start records 2026-10-01T23:32:36.046Z (staging) and
  2026-10-01T23:46:23.015Z (production); completion 23:41:26.653Z / 23:54:36.424Z.
- Sanitized full audit:
  `/srv/codex-operator/outbox/1305367840_1790904365/search-timing-audit.md`.
