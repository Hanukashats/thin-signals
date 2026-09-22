# Host integration and companion detection

The portable contract is the open Agent Skills directory format: `SKILL.md` plus optional `references/`, `scripts/`, `assets/`, and host metadata.

## Hermes

Hermes loads local skills from `~/.hermes/skills/` and progressively loads referenced files. Prefer Hermes-native installation from a published skill source when available; local copy remains valid.

After installation, verify with the host's skill list/check command and start/refresh the session as required by the installed Hermes version.

## OpenAI Codex

Current Codex code can discover user skills under `~/.agents/skills/` and retains `$CODEX_HOME/skills` (`~/.codex/skills` by default) for backward compatibility. Codex's bundled skill installer still uses `$CODEX_HOME/skills` in current builds.

This package's installer defaults to the managed `$CODEX_HOME/skills` path for compatibility and exposes `--dest ~/.agents/skills` when the user intentionally prefers the newer shared Agent Skills location. Do not install duplicate copies in both roots unless the user understands precedence/duplicate behavior.

## Claude Code and other hosts

Use the host's documented Agent Skills directory and copy the entire `product-opportunity-lab/` directory there. If using the full source package rather than the skill-only archive, its repo-level `tools/install.py --host generic --dest <skills-directory>` helper can perform the copy safely.

## Companion semantics

Optional companions are specialists/sensors, not decision authorities. Detect them by capability/name only when already installed. Never auto-install a companion because a workflow mentions it.

Normalize companion findings into the evidence ledger and apply this skill's claim mapping, gates, evidence maturity, and readiness rules.

## Tool adaptation

Refer to capabilities, not fixed tool names:
- current web/search/browser for market facts;
- filesystem for evidence/run artifacts;
- deterministic Python helpers when available;
- subagents only when supported;
- connected/private sources only when authorized.

Missing companions or subagents should degrade breadth, not break the workflow.
