# Thin Signals — plan 7.7: self-contained research and adversarial review proposal

Date: **2026-10-12**. Parent: **7.6**. Class: major operational boundary
change plus a gated methodology proposal. Existing scoring rules, thresholds,
P01–P18 and production records remain unchanged.

Organizer delivery cutoff: **2026-09-29 23:59 MSK**. Recovery work and Git
history keep their real 2026-10-12 timestamps.

## Wave A — restore local research (authorized)

1. Deploy pinned SearXNG and official-release GPT Researcher on VM232.
2. Keep both host listeners on loopback and use VM232's host sing-box egress.
3. Point the existing SearXNG connector at the local service.
4. Prove container/systemd restart, product independence and rollback.
5. Record live query duration, source count, failures and resource use.

Acceptance: JSON metasearch succeeds, a bounded deep-research query returns
cited sources, a Thin Signals query produces candidates, and API/UI/public
health remain green before and after a controlled service restart.

State: **implemented and self-tested**. Evidence is in
`reports/VM232_RESEARCH_2026-10-12.md`; independent acceptance remains open.

## Wave B — evidence-gated debate (operator gate)

Specify researcher, critic, defender, control critic and deterministic arbiter
contracts as ADR-011. Implement only after a separate command. The feature is
disabled by default, uses PostgreSQL as its only ledger, and cannot bypass the
existing checklist/exclusion/score gates.

## Wave C — evaluation (after Wave B authorization)

Run baseline versus proposed replay and an untouched holdout. Report quality,
false promotions, evidence coverage, duration, tokens and cost. Independent
verification, not the implementing role, decides acceptance.

## Release and provenance

SourceCraft remains canonical. GitHub mirroring is blocked until the exact
repository and scoped authentication are confirmed. Real commit and test times
are preserved; an analytical `as_of` date may be supplied to a search, but is
never represented as a fake implementation timestamp.
