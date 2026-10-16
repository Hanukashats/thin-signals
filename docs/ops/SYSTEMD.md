# Persistent services on VM101

The public deployment is served from `/opt/thin-signals`. PostgreSQL stays in the existing Docker Compose service; API and UI use the versioned systemd units in `deploy/systemd/`.

Before deploying 7.7, take a private `pg_dump -Fc` and restore it into a disposable
database; verify the run count. Save the previous Git SHA. Pause API/UI while
fast-forwarding `main`, migrating and bootstrapping. Existing production data and
the four operator-owned untracked evidence paths must remain intact.

After the verified fast-forward, run from `/opt/thin-signals` as the host operator.
Only the database credential is read by native application settings; never print
it or source the complete `.env`:

```bash
export TS_DISABLE_DOTENV=1
export TS_ROOT=/opt/thin-signals
export TS_DATABASE_URL=postgresql+psycopg://ts@127.0.0.1:55432/thin_signals
export TS_PG_PASSWORD_FILE=/opt/thin-signals/.secrets/pg_password
.venv/bin/alembic upgrade head
.venv/bin/python -c 'from ts.db import session_factory; from ts.workspace import bootstrap_workspace; s=session_factory()(); x=bootstrap_workspace(s); print({"revision":x["revision"], "run_id":(x["run"] or {}).get("run_id")}); s.close()'
```

Migration `b614ca27e802` adds only the `workspace` table. Explicit bootstrap
chooses the latest compatible completed parent with retrieved sources; it is a
no-op when a workspace exists. API reads never bootstrap or publish history.
An empty database stays an honest empty live result with the archive available.

Install or refresh services:

```bash
sudo install -m 0644 deploy/systemd/thin-signals-api.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/thin-signals-ui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable thin-signals-api.service thin-signals-ui.service
sudo systemctl restart thin-signals-api.service
curl -fsS http://127.0.0.1:8095/ready
sudo systemctl restart thin-signals-ui.service
```

Verify:

```bash
systemctl is-enabled thin-signals-api.service thin-signals-ui.service
systemctl is-active thin-signals-api.service thin-signals-ui.service
curl -fsS http://127.0.0.1:8095/health
curl -fsS http://127.0.0.1:8095/v1/workspace/latest
curl -fsSI http://127.0.0.1:8501/_stcore/health
curl -fsSI https://tsignal.aispaces.ru
```

The services use separate systemd dynamic identities, bind only to loopback and
restart on failure. Secrets are passed with `LoadCredential=` from host-only
files; writable state/cache directories are created by systemd. The units set
`TS_DISABLE_DOTENV=1`, so production never imports arbitrary values from the
checkout's `.env`. Do not put secret values into unit files or Git.

Rollback:

1. Revert the release commit, or fast-forward `/opt/thin-signals` to a reviewed
   rollback commit. Never rewrite the shared branch with `reset --hard`.
2. Restart only `thin-signals-api.service` and `thin-signals-ui.service`.
3. Re-run the local and public health checks above. PostgreSQL is not restarted for a UI/API rollback.

Keep the additive workspace table during code rollback; older code ignores it.
Do not downgrade/drop that table or restore over live data as a routine rollback.
After forward recovery, restart and compare the workspace revision, Run ID,
archive query/hash and ordered result IDs with the saved pre-restart snapshot.
