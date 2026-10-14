# Independent release re-verification — 96550ff

Date: 2026-10-14 UTC, approximately 00:42 UTC.
Verifier: `astra-verifier`.
Frozen candidate: `96550ff131ad9852d85ae2470e79799d86d6e0b5`.
Branch: `feat/thin-signals-reliability-20261012`.
Release GOAL: `g-277a6c4d68e2`, criterion C05.

## Verdict

**C05 PASS. No scoped P0/P1/P2 finding remains.** The original independent
origin counterexample is closed without removing legitimate explicit-origin
promotion. The full repository suite passes **465 tests**. Production health,
public UI availability, exact mirror/deployment identity and the targeted
security checks pass.

This is a bounded re-verification of `4074e51..96550ff`, incorporating the
direct unchanged release evidence in
`reports/ASTRA_RELEASE_VERIFICATION_4074E51_2026-10-14.md`. That historical
FAIL report remains immutable; this report supersedes its release disposition
only for the new exact SHA. The reviewer did not implement the correction.

## Findings closed

### Previous P1: document DOI used as an independent organization origin

The runtime change removes the DOI fallback from `_explicit_origin` in
`ts/review/integration.py`. Only an explicit organization/laboratory identifier
is returned; absent origin identity now returns `None`. DOI remains document
metadata and no longer supplies independent-origin credit to the arbiter.

The original independent differential was rerun through the real
`CandidateEvidenceProvider` and `run_review` with unchanged typed test fixtures:

| Source metadata | Adapter origins | Result |
|---|---|---|
| Distinct explicit RORs | Three distinct RORs | PROMOTE / all_critical_objections_resolved |
| One explicit lab on every source | Same ROR for all | HOLD / unresolved_critical |
| No explicit origins, distinct DOIs retained | `None`, `None`, `None` | HOLD / unresolved_critical |

All five role/arbiter states were `succeeded` in each case. Thus the safe HOLD
comes from evidence semantics, not a failed model, malformed response or
incomplete round. The committed regression additionally exercises
`attach_candidate_review` and asserts unknown origins, successful role states
and HOLD. No live model requests were made.

### Previous P3: public UI fallback described as API health

The release receipt now explicitly distinguishes the public Streamlit UI from
the private loopback API. Public health-shaped fallback pages are no longer
presented as API-health evidence. Direct API `/health` and `/ready` checks
returned healthy JSON during this re-verification.

## Independent checks

| Check | Observed result |
|---|---|
| Local HEAD | `96550ff131ad9852d85ae2470e79799d86d6e0b5` |
| VM232 `/opt/thin-signals` HEAD | Same exact SHA |
| SourceCraft named feature branch | Same exact SHA |
| Public GitHub named feature branch | Same exact SHA |
| Local and VM worktree before report | Clean |
| Author / committer time | Both `2026-10-14T00:39:09Z` |
| Ancestry | `4074e51` is an ancestor of `96550ff` |
| GitHub historical main | Unchanged `0c1fdd37cd95da5013ef27237b3657637601cf32` |
| SourceCraft historical main | Unchanged `f56f6ff57e4f4b83ae7c2e9dbff36cb238e0ade5` |
| Full suite | **465 passed**, 1 existing Starlette warning, 15.90 s |
| Ruff: ts ui scripts docs/presentation | PASS |
| LivingSet | OK requirements=52 waves=19 forks=13 |
| Delta whitespace | `git diff --check 4074e51..96550ff` PASS |
| Original origin differential | All three expected outcomes reproduced |
| Review evaluation | Exact committed JSON and rendered Markdown equality |
| Added-diff credential-pattern scan | 287 added lines, zero matches in six categories |
| Production research Compose parse | PASS |
| Quick-deploy Compose parse | PASS with existing host env-file directory |
| Public UI | HTTPS HTTP 200, TLS verification result 0 |
| Private API health | `{"ok":true}` |
| Private API readiness | `{"ok":true,"database":"ready"}` |
| Private Streamlit health | `ok` |

The repository delta contains only the removed fallback/docstring correction,
its regression test, the updated release receipt and the historical failure
report. No dependencies, credentials, transport, authorization, image pins,
snapshot formats, scoring rules or production activation budgets changed.

The credential scan covered private-key headers, OpenAI-style keys, classic
GitHub tokens, GitHub fine-grained tokens, URL credentials and AWS access-key
patterns. It is a bounded regression check, not a comprehensive secret audit.
Credential consumers read authorized file paths without revealing values.

The passing full-suite command was:

```bash
TS_DISABLE_DOTENV=1 \
TS_DATABASE_URL=postgresql+psycopg://ts@127.0.0.1:55432/thin_signals_test_codex_20261013_r2 \
TS_PG_PASSWORD_FILE=/opt/thin-signals/.secrets/pg_password \
TS_OPENROUTER_KEY_FILE='' TS_GPT_RESEARCHER_ENABLED=false \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

The exact disposable database was confirmed present before execution. No
production database tests, database creation, deletion or schema changes were
performed. The test database was retained as requested.

## Runtime and retained release evidence

On VM232, API, UI, research, Docker, NetBird and agi-sing-box are all active
and enabled. PostgreSQL, SearXNG and GPT Researcher containers remain healthy
with loopback-only published ports. No failed systemd unit was present.
The production drop-in still hashes to
`cb33494e38fc534e82054aa5075990ec64afaab5a4c7d48d838674ca30030b87`.

The repeated resource sample showed approximately 10.5 GiB available RAM,
103 GiB available disk, load averages `0.10/0.04/0.01` and 8 hours 15 minutes
uptime. This establishes current health, not production load capacity.

The immediately preceding independent audit directly verified the retained
PVE snapshots and database archive/hash, the activation rollback journal,
current research image digests and hardening, both saved canaries, all ten
persisted review events and 190/190 referenced source snapshot attestations.
This narrow correction does not mutate those historical records. Its saved
canaries still mean narrow 2 admitted + 5 potential + 8 near misses, and wide
9 admitted candidates across 13 themes; both review verdicts were HOLD.
Those runs are not presented as new live executions of the corrected SHA.

Review evaluation recomputation retains result digest
`66de648ca54cfd9b33e405a720f7dec00051d409f0c18f42f45a8cd19cc1e0eb`.
The authored 16-case fixture metrics remain P/R/exact/stability 1.0, with no
unsafe fixture acceptances. This does not establish live-model scientific
accuracy, external adjudication or a ten-promoted-signal outcome.

Compose quick-deploy validation consumed the existing SearXNG env file via
`TS_SECRETS_DIR=/etc/thin-signals-research`; it verifies parsing only, not
quick-deploy secret readiness. Public HTTP was checked through the operator
host's network path, not from an independent geographic monitor. Historical
no-force-push statements are corroborated by preserved ancestry and unchanged
main refs; server reflogs were not available for a forensic audit.

## Disposition

**VERIFIED:** the correction, independent origin differential, full-suite and
static gates, exact dual-remote/VM/local SHA, current production health,
provenance boundaries and public UI availability.

**PASS:** release C05 for frozen `96550ff` with the explicit limits above.
The only repository mutation by this verifier is this report. No commits,
pushes, deployments, service restarts, live model calls or production writes
were made. GOAL acceptance commands use the independent `astra-verifier`
identity and do not expand release authority.

### Actual GOAL command results

- `GOAL_AGENT=astra-verifier goalctl crit g-277a6c4d68e2 C05 PASS <this report>`:
  accepted, 5/5 criteria PASS.
- `goalctl checkpoint`: accepted as checkpoint 3, `meaningful=true`,
  `criterion_gain=1`, `evidence_gain=3`, no stop instruction.
- `GOAL_AGENT=astra-verifier goalctl verify g-277a6c4d68e2 pass ...`:
  **rejected** with exact response
  `{"ok": false, "error": "verifier token required"}`.

After that initial rejection, the kernel remained `IN_PROGRESS`,
`completed=false`, `verified=false`, `verified_by=null`, with C01–C05 PASS.
The independent verifier did not acquire a token, change identity or bypass
the authorization requirement.

The operator's existing opaque credential consumer subsequently completed the
already-issued independent PASS through the authorized verifier-token path.
A fresh read-only `goalctl get g-277a6c4d68e2` independently confirmed:

```json
{"status":"VERIFIED","completed":true,"verified":true,"verified_by":"astra-verifier","criteria":{"C01":"PASS","C02":"PASS","C03":"PASS","C04":"PASS","C05":"PASS"}}
```

**Final disposition: GOAL VERIFIED, 5/5 PASS, by `astra-verifier`.** This
receipt preserves the first rejection and the subsequent authorized completion.
No token was exposed to this verifier; this follow-up only read GOAL state and
updated this report. It did not invoke `verify` again or modify product code.
