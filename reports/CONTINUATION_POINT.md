# CONTINUATION POINT — operator UI, 2026-09-29

Status before implementation:

- Canonical checkout `/opt/thin-signals`, `main` / `origin/main` at `ea265eb`.
- Latest functional UI code is from `0807419`; later commits are rollback/report/presentation documentation.
- Public path `https://tsignal.aispaces.ru` is healthy and proxies to Streamlit on `127.0.0.1:8501`; API is `127.0.0.1:8095`.
- Current UI is stock Streamlit, without the approved AGI Space dusk treatment or logo.
- Current `/v1/runs/latest` is an inconsistent stale `mine-1g` result from reverted commit `09e8888`: 15 rows, counter `admitted=1`, `shortfall=0`, no signal label. It must not be presented as the current method result or deleted silently.
- Three existing untracked evidence paths in `/opt/thin-signals/reports/` belong to the current owner and are untouched.
- GOAL ownership remains `project=thin-signals agent=cursor-bk2`; this increment does not claim or take that card.
- A separate Cursor writer was observed and allowed to finish. It left no tracked UI change; this work proceeds in isolated worktree/branch `fix/dusk-operator-ui-1790714202`.

Continuation increment:

1. Add a tested consistency guard for automatically loaded saved runs.
2. Apply the approved dusk tokens and official AGI Space logo without changing scoring.
3. Reduce the long report by progressive disclosure for reasoning, unread items, sources, exclusions, and card detail.
4. Preserve Russian labels, honest shortfall, viewer-without-login, export, and admin gate.
5. Run focused RED/GREEN tests, full pytest, links, scoped Ruff, browser desktop/mobile smoke.
6. Integrate only after reconciling `main`, then commit/push, restart UI only, and verify public health and screenshots.
