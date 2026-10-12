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

The first remediation at `4cccc20` closed all four failures above, but a second
fresh Astra review correctly rejected two deeper C02 cases: an independently
hashed invented fragment could be paired with a valid blob, and a DOI redirect
to an indicator blog retained the original DOI's primary trust. It also found
that the direct transport accepted a final EOF arriving after its total
deadline even though the harness discarded the late result.

The second remediation at `3400017` passed the complete existing suite and all
prior attacks. A third clean Astra review still found that changing a card's
display URL could misattribute attested arXiv text to an unrelated Nature URL,
and that byte-by-byte response headers could keep `getresponse()` alive beyond
the total timeout. Both findings were reproduced before the current fix.

## Remediation

- `retrieval-0.6` resolves every URL/redirect hop once, rejects any non-public
  answer, and passes the exact numeric addresses to a pinned socket transport.
  The connection performs no second `getaddrinfo`; HTTP keeps the original Host
  and HTTPS keeps the original hostname for certificate validation and SNI.
- Connect, headers and every streamed read share one monotonic deadline. The
  harness separately bounds the injected snapshot worker, discards late
  results and records the run as `degraded`.
- `snapshot-evidence-0.2` now carries an immutable content-addressed manifest
  binding the fetched URL, raw body hash, MIME type and canonical extracted-text
  hash. `checklist-v20` re-derives the text from the stored blob and requires the
  cited fragment to be its exact bounded prefix before allowing `verified`.
  Missing, malformed, corrupt or cross-paired evidence becomes snippet-only and
  is capped to `supported`.
- Trust is conservatively evaluated across both the claimed URL and the final
  fetched URL. A redirect can preserve or lower trust, never promote it. Thus a
  DOI redirect to Medium remains indicator evidence.
- The pinned transport sets the remaining deadline on the response's actual
  socket, actively aborts it at the absolute deadline while headers are parsed,
  and checks the monotonic clock after every body read, including final EOF.
- Public evidence citations use the final URL in the immutable attestation,
  never a separately mutable display URL from the candidate card.
- Deduplication joins records on an explicit shared DOI/OpenAlex Work alias
  before applying conservative title similarity. Conflicting explicit Work IDs
  remain separated by the existing guard.
- `live-w21`, `retrieval-0.6` and `checklist-v21` invalidate incompatible cached
  run/checklist identities; historical database rows remain immutable.

## Verification

- Exact regressions cover validated-address handoff, absence of a second DNS
  lookup, slow-stream/final-EOF total timeout, inherited snapshot deadline,
  missing blob, invented fragment/blob cross-pairing, immutable URL/text/MIME
  attestation, redirect trust downgrade and short-title Work mirrors.
- Full suite: **334 passed** on a fresh migrated disposable PostgreSQL database.
- Ruff, LivingSet links, YAML loading, `git diff --check` and bounded credential
  pattern scan passed.
- The only warning is the pre-existing Starlette TestClient/httpx deprecation.

This document is implementer evidence, not an independent PASS. A fresh Astra
verification of the frozen remediation commit remains mandatory before the next
GOAL or any release action.
