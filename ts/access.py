"""Two roles for the screens. Password hashes live in a host file, never in git."""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

import yaml

ADMINS = ("admin", "hanuka", "yana")
VIEWERS = ("user1", "user2", "user3")
ROSTER = {name: "admin" for name in ADMINS} | {name: "viewer" for name in VIEWERS}


def hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, salt_hex, digest_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    if kind != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest, expected)


def load_accounts(path: Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    users = data.get("users") or {}
    if not isinstance(users, dict):
        raise TypeError("accounts file has no users map")
    return users


def role_for(accounts: dict, username: str, password: str) -> str | None:
    row = accounts.get((username or "").strip())
    if not isinstance(row, dict):
        return None
    role = row.get("role")
    if role not in ("admin", "viewer"):
        return None
    if not verify_password(password or "", str(row.get("password_hash") or "")):
        return None
    return role


def can_admin(role: str | None) -> bool:
    return role == "admin"
