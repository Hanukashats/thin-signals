# VM230 `agi-thin-signals` — отчёт о создании (2026-09-23)

Исполнитель: cursor-agent на VM101 через SSH к Home-PVE (ключ P0005 из `/root/private-access/hanukaSEC`). Все шаги плана Ш0–Ш5 выполнены, кроме NetBird (нужен setup-key оператора).

## Ш0. Доступ и инвентарь Home-PVE

- `Home-PVE`, pve-manager 9.1.4, kernel 6.17.4-2-pve, 24 vCPU, 86 GB RAM (**~81 GB уже committed**: VM102 openwrt 3 GB, VM200 AiSpase 45 GB, VM220 AGISpace-v2.0 32 GB → свободно ~13 GB).
- Storage: `vmstore` (ZFS 1.86 TB, 707 GB free, единственный с `content images`); `local-zfs` — только rootdir; `local` — vztmpl.
- Bridges: `vmbr0` 192.168.5.0/24 (gw .1), `vmbr1` 192.168.3.0/24, `vmbr2` 11.11.11.0/24.
- VMID 230 свободен; IP 192.168.5.230 свободен (ping).
- Cloud image `noble-server-cloudimg-amd64.img` скачан в `/var/lib/vz/template/iso/`, `SHA256SUMS: OK`.

## Ш1. Создание VM (команды, воспроизводимо)

```bash
qm create 230 --name agi-thin-signals --ostype l26 --machine q35 --bios seabios \
  --cores 4 --sockets 1 --cpu host --memory 8192 --balloon 4096 \
  --net0 virtio,bridge=vmbr0,firewall=0 --scsihw virtio-scsi-single \
  --serial0 socket --vga serial0 --agent enabled=1,fstrim_cloned_disks=1 --tags thin-signals,hackathon,agi
qm set 230 --scsi0 vmstore:0,import-from=/var/lib/vz/template/iso/noble-server-cloudimg-amd64.img,discard=on,iothread=1,ssd=1
qm set 230 --ide2 vmstore:cloudinit --boot order=scsi0
qm set 230 --ciuser ubuntu --sshkeys /root/ts230-keys.pub \
  --ipconfig0 ip=192.168.5.230/24,gw=192.168.5.1 --nameserver 192.168.5.1 --searchdomain lan --ciupgrade 0
qm resize 230 scsi0 80G && qm cloudinit update 230 && qm start 230
qm snapshot 230 fresh-cloudinit
```

Отклонение от плана: RAM 8 GB вместо 12 (лимит хоста); storage `vmstore` (local-zfs не хранит images).

## Ш2. Bootstrap — `scripts/vm230-bootstrap.sh`

Docker 29.8.1 + compose v5.5.1 (official repo), NetBird 0.79.0 (official repo, не подключён), qemu-guest-agent, ufw (22/8000/8501 из LAN+mesh), user `agent` (sudo NOPASSWD, docker), PasswordAuthentication no, unattended security upgrades. Первый прогон упал на `usermod` с двумя логинами — исправлено, повторный прогон чистый.

## Ш3. Перенос

- `git clone` SourceCraft → `/opt/thin-signals` (`9d6f3f1`, dirty 0). `.secrets/` rsync с VM101 (0700).
- `/opt/thin-signals-archive/`: inbox (4 zip + 2 PDF + XLSX), 7 skills бэкенда, AGENTS.md + rules; `SHA256SUMS` 54 файла.
- `.venv` + `pip install -e .[dev,api,ui]` → `pytest`: **39 passed**; `check_living_links.py`: OK (43 req / 8 waves / 12 forks).
- `docker compose --profile laptop up -d pg` → `thin-signals-pg-1 healthy`, `CREATE EXTENSION vector` → 0.8.6.

## Egress (ADR 007 бэкенда) — не было в плане, потребовалось

С домашнего IP `109.195.243.128` OpenRouter отвечает `Access denied by security policy`. Установлен официальный sing-box 1.13.16 (бинарь = VM101, sha `9069f805…`), конфиг выведен из VM101: те же outbounds Amsterdam-1/2, `bind_interface eth0`, inbounds `mixed-local`, `mixed-docker0`, TUN `agi-tun0`. Rule-set сервер `212.34.145.238:2088` недоступен с обоих хостов → rule-sets положены локально из официальных SagerNet `sing-geosite`/`sing-geoip`. Результат: egress `144.124.252.222`, ya.ru напрямую (302), OpenRouter ZDR-запрос `qwen/qwen3.6-35b-a3b` → provider Venice, OK. Сервис enabled. Откат: `systemctl disable --now agi-sing-box`.

## Ш4–Ш5

- `scripts/git-hooks/pre-push` (pytest + links), `scripts/install-hooks.sh` → `core.hooksPath`.
- `docs/ops/VM230.md`, `docs/ops/hosts.yaml`, STATUS, secrets.paths, handoff обновлены.
- Snapshot `bootstrapped` после Ш3.

## Осталось оператору

1. NetBird setup-key для VM230 (`ssh vm230 'sudo netbird up --setup-key <key>'`), после чего убрать ProxyJump.
2. Отдельный OpenRouter-ключ `thin-signals` (сейчас dev-копия ключа бэкенда, лимит $100).
3. Шаблон презентации (TZ-14) — по-прежнему не получен.
