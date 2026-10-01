# Potential review correction

Baseline `81ed4f9`; independent reviewer rejected three concrete defects before deployment:

- High-potential threshold 65 was unreachable for real scores below 0.35 (enumerated upper bound 56.7).
- `ДРУГОЙ_МЕХАНИЗМ` could return early as below-watchlist and enter the review queue.
- Legacy exclusions were re-ranked without checklist drift warnings.

Decision: preserve `rules-0.1` exactly. `potential-v2` considers current scored watchlist observations below 0.60 for the independent high-potential index, as well as near-watchlist exclusions [0.25, 0.35). Deduplicate both sources; do not alter the signal label or admitted ranking. Target distances identify 0.35 (watchlist) or 0.60 (weak signal). High-potential priority uses the potential index, not proximity to the already passed watchlist gate. UI exposes the formula and source provenance.

`checklist-v15` rejects off-topic before threshold returns and invalidates prior run-cache identities. Historical results remain readable but do not populate the current potential ranking; UI requires a new run. Drift checks inspect exclusions as well as top rows.

Verification: three regression tests reproduced RED; all 223 tests then passed using isolated database `thin_signals_test_1790887573`. Ruff, LivingSet links and diff checks passed. New independent review and runtime receipt remain release gates. No weights, thresholds, source registry, donor code or production data were changed.
