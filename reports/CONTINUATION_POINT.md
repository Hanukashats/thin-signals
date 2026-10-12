# CONTINUATION POINT — home VM232 recovery, 2026-10-12

This checkpoint records observed state before the local research-contour
increment. It supersedes the operational parts of the older VM101/VM231
checkpoint without rewriting historical release evidence.

## Verified reality

- Canonical product history is SourceCraft `shats123/thin-signals`; local
  `main` is `e53cf9502c89140b6fe4c1a8358eac62fb3c6ede`.
- The recovered deployment is VM232 `agi-thin-signals-v2-u2604`, Ubuntu
  26.04.1 LTS, `192.168.5.232`, 4 vCPU, 12 GiB RAM and a 120 GiB
  `local-zfs` disk. It is enabled for Proxmox autostart.
- VM232 runs branch `chore/home-pve-vm232-ubuntu26-20261012` at
  `6c3c05dffad966fa2c90057bff92bca6ac7733d2`; the branch name differs from
  SourceCraft's historical VM231 branch but the commit is identical.
- PostgreSQL, API, UI and host sing-box are active and enabled. Listeners are
  loopback-only: PostgreSQL `55432`, API `8095`, UI `8501`.
- Public `https://tsignal.aispaces.ru/` is served through Caddy on OpenWrt and
  reached the VM232 application at the start of this increment.
- The application talks directly to OpenRouter using a host-only key file and
  enforces the approved ZDR/data-collection policy. VM232 has its own sing-box
  egress; it does not depend on VM101 LiteLLM.
- `TS_SEARXNG_URL` is configured as `http://127.0.0.1:28088`, but nothing was
  listening there. GPT Researcher was also absent. Those two facts are the
  exact continuation point for this increment.
- VM104 `kingston-recovery` is stopped and `onboot=0`; it consumes no running
  CPU or RAM. VM233 NetBird was reduced from 4 GiB to 2 GiB and its dashboard
  and API recovered after the isolated guest reboot.

## Repository state preserved

- `/opt/thin-signals` has four pre-existing untracked evidence paths. They are
  operator-owned and remain untouched.
- Work for this increment is isolated in branch
  `chore/vm232-local-research-1791810532`, based on the verified VM recovery
  commit `6c3c05d`.
- GitHub authentication and the exact Thin Signals mirror are not available on
  VM101. No GitHub repository is created or pushed until the operator confirms
  the exact destination and a repository-scoped credential exists.
- Git/system timestamps will not be falsified. The canonical organizer
  deadline in `00_START_HERE_HANDOFF_RU.md` is 2026-09-29 23:59 MSK; the latest
  voice transcript may have said 9 September and therefore cannot override
  that exact written value without clarification.

## Upstream audit snapshot

- SearXNG: official image `searxng/searxng`, version
  `2026.9.18-12df7aed6`, revision
  `12df7aed60b2705c00f42d805d8d36fd43a846c2`, amd64 digest
  `sha256:31e3ca5e206ef71b148773e196cc575dc9c866d4f5047c8a7038a45c38bd4578`,
  AGPL-3.0-or-later.
- GPT Researcher: official repository
  `https://github.com/assafelovic/gpt-researcher`, release `v3.7.0`, commit
  `0957c301ed06c2a5857b834358c7227c739041d4`, Apache-2.0 repository license.
  The Docker Hub `latest` image was inspected and rejected: it is an old
  0.12.8 build from 2025-03-13 despite its mutable tag. The release source must
  be built locally and tagged immutably.
- Upstream GPT Researcher has no lockfile and its Dockerfile installs ranged
  dependencies. The exact source commit and resulting local image ID/digest
  must both be recorded after the build; this residual dependency risk is not
  hidden.
- The local prompt-injection scanner timed out while scanning upstream text.
  Upstream content remains untrusted data; only the operator-authorized,
  typed deployment actions below may be performed.

## Authorized continuation

1. Add loopback-only SearXNG and GPT Researcher containers on VM232 with
   restart-on-boot, bounded resources, host-only secrets and health checks.
2. Point Thin Signals only to the local SearXNG instance and verify a live
   candidate search. Keep GPT Researcher as a separate research adapter until
   its promotion contract is approved.
3. Specify the researcher/critic/defender method with a deterministic arbiter,
   evidence ledger, timing/cost metrics and a disabled-by-default feature flag.
   Do not implement or activate that method without the operator's separate
   command.
4. Commit and push the reviewed branch to SourceCraft. Treat the GitHub mirror
   and any historical timestamp wording as explicit external gates.

## Rollback boundary

- Removing the local research Compose stack and restoring the previous API
  drop-in returns VM232 to the pre-increment state; PostgreSQL data is not
  touched.
- Existing Thin Signals API/UI and public routing are verified before and after
  the change. A failed research container must not take either service down.
