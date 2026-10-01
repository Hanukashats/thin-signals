# Persistent services on VM101

The public deployment is served from `/opt/thin-signals`. PostgreSQL stays in the existing Docker Compose service; API and UI use the versioned systemd units in `deploy/systemd/`.

Install or refresh after a verified fast-forward of `main`:

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
