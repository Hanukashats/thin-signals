# Astra retrieval remediation — 2026-10-12

Scope: independent rejection of the first frozen candidate for GOAL
`g-62fcfd60cd61`. Production was not touched.

## Reproduced failures

1. Public-host validation and the HTTP transport performed separate DNS
   resolutions. A rebinding test reached an isolated loopback canary.
2. A slow streamed response outlived a 100 ms inherited deadline and its body
   was still preserved.
3. A source dictionary containing only `status=preserved` and arbitrary text
   retained a model-produced `verified` claim without a snapshot hash/ref.
4. A DOI view and an OpenAlex-only view of Work `W123` became two events when
   their shared title was shorter than the title heuristic.

The verifier also ran the prior focused and full suites successfully. That was
not treated as evidence that the adversarial boundaries passed.

## Remediation

- `retrieval-0.4` resolves every URL/redirect hop once, rejects any non-public
  answer, and passes the exact numeric addresses to a pinned socket transport.
  The connection performs no second `getaddrinfo`; HTTP keeps the original Host
  and HTTPS keeps the original hostname for certificate validation and SNI.
- Connect, headers and every streamed read share one monotonic deadline. The
  harness separately bounds the injected snapshot worker, discards late
  results and records the run as `degraded`.
- Snapshot evidence now carries content and fragment SHA-256 attestations.
  `checklist-v19` verifies their relationship and, in the product path,
  re-hashes the content-addressed blob before allowing `verified`. Missing,
  malformed or corrupt evidence is treated as snippet-only and capped to
  `supported`.
- Deduplication joins records on an explicit shared DOI/OpenAlex Work alias
  before applying conservative title similarity. Conflicting explicit Work IDs
  remain separated by the existing guard.
- `live-w21`, `retrieval-0.4` and `checklist-v19` invalidate incompatible cached
  run/checklist identities; historical database rows remain immutable.

## Verification

- Exact regressions cover validated-address handoff, absence of a second DNS
  lookup, slow-stream total timeout, inherited snapshot deadline, missing blob,
  unattested preserved text and short-title Work mirrors.
- Full suite: **327 passed** on a fresh migrated disposable PostgreSQL database.
- Ruff, LivingSet links, YAML loading, `git diff --check` and bounded credential
  pattern scan passed.
- The only warning is the pre-existing Starlette TestClient/httpx deprecation.

This document is implementer evidence, not an independent PASS. A fresh Astra
verification of the frozen remediation commit remains mandatory before the next
GOAL or any release action.
