# Upstream audit: GPT Researcher and OpenAlex

Date: 2026-10-12. Scope: W10 inputs only; no product adapter was activated and
no production secret or database was used.

## GPT Researcher

| Field | Verified value |
|---|---|
| Repository | `https://github.com/assafelovic/gpt-researcher` |
| Release | `v3.7.0` |
| Exact source | `0957c301ed06c2a5857b834358c7227c739041d4` |
| License | Apache-2.0 in the pinned tree |
| Local image | `thin-signals/gpt-researcher:3.7.0-0957c301` |
| Local endpoint | `127.0.0.1:28000`, not public |
| Retriever | private SearXNG over Docker DNS |
| Readiness probe | `GET /.well-known/agent-discovery.json` |

Primary references:

- release: <https://github.com/assafelovic/gpt-researcher/releases/tag/v3.7.0>
- pinned tree: <https://github.com/assafelovic/gpt-researcher/tree/0957c301ed06c2a5857b834358c7227c739041d4>
- pinned server contract: <https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/backend/server/app.py>
- pinned license: <https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/LICENSE>

The exact pinned FastAPI model requires `task`, `report_type`, `report_source`,
`tone`, `repo_name`, `branch_name`, and optionally `headers`; its default
`generate_in_background=true` returns only a message and `research_id`.
Synchronous `POST /report/` (`generate_in_background=false`) returns `report`,
`research_id`, `research_information.source_urls`, reported costs, visited URLs
and generated file paths. Raw research-source bodies are intentionally omitted
by upstream. The pinned service has no dedicated `/health`; the discovery
document is the bounded readiness endpoint already used by operations.

W10 decision: call only synchronous `POST /report/` inside the product's own
deadline/cost boundary, feature-off by default. Treat report prose and URLs as
untrusted leads. Re-fetch, classify and preserve source evidence through Thin
Signals before it can affect a claim. Never publish this loopback service or
persist upstream prompts/reasoning in the public activity view.

Rollback is configuration-only: disable the adapter flag and keep the existing
typed connectors. No GPT Researcher fork or schema migration is required.

## OpenAlex

Official current documentation reviewed:

- authentication and budgets: <https://help.openalex.org/api/authentication/>
- API overview: <https://help.openalex.org/api/>
- errors and retry behavior: <https://help.openalex.org/api/errors/>
- paging: <https://help.openalex.org/api/paging/>
- deprecations: <https://help.openalex.org/api/deprecations/>
- Works attributes: <https://help.openalex.org/data/works/attributes/>
- Authorships: <https://help.openalex.org/data/authorships/>

Current documentation allows small anonymous use but gives a materially larger
budget to a free API key. HTTP 429 can mean daily-budget exhaustion or request
rate pressure; response headers expose remaining credits and reset information.
The retired `mailto` polite-pool convention must not be used as authentication.
Use `per_page=100` where suitable, batch stable IDs, request only needed fields,
and apply bounded exponential backoff inside the inherited global deadline.

W10 decision: a host-only key file, stable OpenAlex Work/DOI identity,
authorship/institution/ROR, chronology, OA location and retraction metadata.
OpenAlex, Crossref and SearXNG views of one Work remain one origin. OpenAlex is
role-specific enrichment, not an independent vote and not a mirror fallback for
claim verification.

OpenAlex remains an ordinary typed connector, not a separately activated agent.
This increment does not add key handling: the official anonymous allowance is
enough for the bounded search contract, while any later scale-up must add a
host-only bearer credential as a separate operational change. Rollback is the
OpenAlex enrichment commit revert; stored historical runs remain readable.

### Implemented branch contract

The reliability branch implements `openalex-work-0.1` against the current
official Work schema. It requests only `id`, DOI, title/abstract, publication
date, type, authorships/institutions, OA status, `is_retracted` and bounded
reference count. Stable Work and DOI aliases deduplicate copies; only explicit
ROR values become origin IDs. Raw affiliation strings and unknown response
fields are discarded. `is_retracted=false` is serialized as `not_flagged`, not
as proof of a complete retraction screen; `erratum`/`retraction` describe the
record type and do not silently mark a referenced target.

Official contracts used:

- <https://help.openalex.org/data/works/attributes/>
- <https://help.openalex.org/data/authorships/>
- <https://help.openalex.org/data/locations/>
- <https://help.openalex.org/api/authentication/>

A one-result anonymous API canary on 2026-10-12 returned a canonical Work ID,
DOI, one ROR affiliation and typed chronology/access/integrity roles through the
new parser. It changed no production state and used no secret.
