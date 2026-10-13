# Astra C05 audit — 2026-10-13

Frozen commit: `0b655e1`  
Scope: default-off product integration, persistence/replay, route metadata, operational failures, and role budgets.  
Verdict: **FAIL** pending remediation.

## Reproduced blockers

1. Two concurrent requests with the same run identity can both spend the four-role review budget before persistence serializes them. A simulated persistence interruption can likewise spend again on retry. A durable pre-spend reservation is required.
2. Model/provider metadata accepted URL/prose-shaped values and exposed them in the public trace. Route attribution must be strict, match the requested approved model, and fail closed without echoing rejected values.
3. Unexpected evidence-provider and client-construction exceptions escaped the normal structured `HOLD` path.
4. The review configuration fingerprint omitted effective routing inputs (`llm_provider_policy`, `allowed_models`, and `openrouter_url`).
5. The per-role timeout did not include the `/endpoints/zdr` registry lookup, so a nominal role budget could be exceeded before the completion request began.

## Controls that passed

- Feature flag defaults off and makes no review calls.
- Enabled narrow and wide parent runs make exactly four role calls; theme children do not.
- Completed replay avoids further calls.
- Ordinary gateway failures become `HOLD`.
- Successful events retain append-only structured evidence and accounting metadata.

## Audit evidence

- Focused integration/persistence/runner suite: 45 passed before adversarial probes.
- Full suite: 384 passed before adversarial probes.
- Ruff: passed.
- Adversarial probes reproduced duplicate spend, route-metadata disclosure, exception escape, fingerprint drift, and unbounded registry lookup.

This report contains no credentials, prompts, raw model prose, or private endpoint payloads.
