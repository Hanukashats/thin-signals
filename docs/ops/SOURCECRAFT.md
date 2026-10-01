# SourceCraft access (no secrets)

LivingSet **7.6**. Hosting: [SourceCraft](https://sourcecraft.dev) (Yandex). SourceCraft is canonical; the required GitHub mirror is not configured on VM101 as of 2026-10-01 and must not be claimed until its exact repository and dedicated credential are verified.

## Credentials (SEC canon)

| Назначение | Файл в `D:\WORK\SEC` | Примечание |
|---|---|---|
| SSH Authentication | `id_ed25519_sourcecraft` / `.pub` | https://sourcecraft.dev/me/ssh |
| SSH Signing (future) | `id_ed25519_sourcecraft_sign` / `.pub` | UI signing slot may be absent |
| **API / CLI PAT (full access)** | **`SOURCECRAFT_API_PAVEL.txt`** | Канон для агентов; full management. Env alias: `SOURCECRAFT_TOKEN` |

Не коммитить PAT. Не писать значение PAT в LivingSet, чат, AgentMemory. В плане хранится **только путь** к файлу.

## Agent load (Windows)

```powershell
$env:SOURCECRAFT_TOKEN = (Get-Content -LiteralPath 'D:\WORK\SEC\SOURCECRAFT_API_PAVEL.txt' -Raw).Trim()
$env:GIT_SSH_COMMAND = 'ssh -i D:/WORK/SEC/id_ed25519_sourcecraft -o IdentitiesOnly=yes'
src auth status
ssh -T -o IdentitiesOnly=yes -i D:/WORK/SEC/id_ed25519_sourcecraft git@ssh.sourcecraft.dev
```

Clone/push:

```text
git@ssh.sourcecraft.dev:<org_slug>/<repo_slug>.git
```

## CLI

Installed: `src` v0.0.103 → `%LOCALAPPDATA%\Programs\src\src.exe`

```powershell
$env:SOURCECRAFT_TOKEN = (Get-Content -LiteralPath 'D:\WORK\SEC\SOURCECRAFT_API_PAVEL.txt' -Raw).Trim()
src auth status
src repo create <org> --slug thin-signals --visibility private --default-branch main
```

Docs: https://sourcecraft.dev/portal/docs/en/sourcecraft/operations/cli-quickstart  
API: `Authorization: Bearer $SOURCECRAFT_TOKEN` → https://api.sourcecraft.tech/

## Status

- PAT path recorded in LivingSet: `D:\WORK\SEC\SOURCECRAFT_API_PAVEL.txt` (2026-09-18).
- On VM101 the same PAT file is `/opt/thin-signals/.secrets/SOURCECRAFT_API_PAVEL.txt` (mode 600, gitignored). Value is not in git.
- API check 2026-09-19: `GET /user` 200, username `shats123`. Personal org slug `shats123`.
- Repo created 2026-09-19: private `https://sourcecraft.dev/shats123/thin-signals`, empty, default branch `main`.
- Push auth that works: HTTPS `https://git@git.sourcecraft.dev/shats123/thin-signals.git` with `GIT_ASKPASS=/opt/thin-signals/.secrets/git-askpass.sh`. PAT is the password. `git ls-remote` returned 0.
- SSH key generated at `/opt/thin-signals/.secrets/id_ed25519_sourcecraft`. Public API has no method to register it (swagger has no ssh path; POST `/user/ssh-keys` is 405). `ssh -T` returns `Permission denied (publickey)` until the public key is added in the UI.
