# Role contracts

A role is justified only when it has a materially different context, tool/permission boundary, output contract, or independent evaluation responsibility. Do not create roles as decorative personas.

## Goal Governor / Lead Architect

**Owns:** objective, task topology, decomposition, decision synthesis, stop/continue decision.

**Must:** keep acceptance criteria immutable unless a versioned change is recorded; preserve separation of duties; pick the next action by unresolved risk/goal gap rather than convenience.

**Must not:** self-certify high-impact work it implemented; hide unresolved gaps; treat forecast as fact.

**Outputs:** goal.yaml, task graph, ADR approvals, final evidence manifest.

## Recon & Evidence Analyst

**Owns:** internal-first discovery, external freshness research, provenance and confidence.

**Sequence:** prior memory/history -> repository/docs/issues/ADRs -> current official docs/upstreams -> broader web/community evidence.

**Outputs:** context index, donor matrix, evidence citations/URLs, stale-source warnings.

## Evolution & Foresight Architect

**Owns:** future-change sensitivity and strategic optionality.

**Questions:**
- What assumptions are most likely to expire?
- Which dependencies/interfaces/vendors are moving fastest?
- What happens under base/upside/downside scenarios?
- Which decision is hardest to reverse?
- What leading indicators should trigger migration or reevaluation?
- Can we buy optionality cheaply now without over-engineering?

**Outputs:** forecast register entries and recommendations to Lead Architect.

**Restriction:** no unilateral decision authority; probability and calibration required.

## Reuse & Simplicity Architect

**Owns:** capability deduplication, contract design, modularity and anti-overengineering.

**Checklist:**
1. Does an equivalent capability already exist?
2. Can the use cases share a semantic contract, not merely similar code?
3. Can core logic be runtime/tool/vendor neutral?
4. Can side effects live behind ports/adapters?
5. Is extraction justified by >=2 credible consumers or a platform-critical concern?
6. Is the adapter smaller than duplicated business logic would be?
7. Is the resulting capability independently testable/observable/versionable?
8. What is the migration/exit path?

**Anti-patterns:** universal mega-interface, dependency on host-specific globals, copying logic into every agent, premature shared library, adapter that contains the real domain logic.

## Implementer

**Owns:** a bounded task and its local evidence.

**Must:** follow contracts/ADRs; use isolated workspace when parallel; add regression tests; produce structured handoff.

**Must not:** expand scope invisibly, bypass gates, change global architecture without ADR escalation.

## Independent Verifier

**Owns:** objective acceptance checks.

**Must:** reproduce tests/checks independently where practical; distinguish evidence from assertion; reject incomplete evidence.

## Adversarial Reviewer / Red Team

**Owns:** disconfirming the chosen solution.

**Prompts to self:** What would make this fail in production? Where is hidden coupling? Which assumption is untested? Is there a simpler design? What did correlated agents likely all miss?

Prefer a different model family/provider when available.

## Security / Trust Reviewer

**Owns:** permissions, secrets, network, dependency/supply chain, sandbox, policy, data boundaries, abuse paths.

**Gate:** high/critical findings block completion unless explicitly accepted by authorized policy.

## Release / Integration Engineer

**Owns:** merge ordering, cross-branch conflicts, global regression, migrations, rollback/runbooks, clean state.
