# Quality, governance and stopping gates

## Evidence hierarchy

1. deterministic test/build/policy evidence;
2. reproducible runtime/benchmark evidence;
3. independent code/spec review;
4. static/documentary evidence;
5. model judgment alone.

Use higher levels whenever economically practical.

## Two-stage review

### Stage A — Spec compliance

- acceptance criterion mapped to implementation/evidence;
- no missing required behavior;
- no hidden scope expansion;
- compatibility/migration requirements met.

### Stage B — Engineering quality

- correctness/edge cases;
- simplicity and maintainability;
- security/trust boundary;
- architecture fitness;
- observability;
- performance/resource implications;
- rollback/recovery;
- docs/runbooks.

## Separation of duties

For medium+ risk:

- implementer != sole verifier;
- high/critical security changes require independent security review;
- architecture-significant changes require Lead Architect acceptance after the challenge pass;
- a subagent may not grant itself new permissions or expand autonomy class.

## Progress metrics

Track:

- acceptance criteria verified / total;
- unresolved risk weight;
- review defect count/severity;
- retries and repeated-failure signatures;
- elapsed/cost/token/tool budgets;
- test/build/pass rates;
- architecture fitness violations;
- regression escapes discovered after integration.

## Stop gate

A `done` status is invalid if any mandatory criterion lacks evidence, a blocking review is open, or global regression has not run after integration.
