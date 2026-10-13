"""Content-addressed snapshots on disk (PLAN_7.2 §6: no S3).

The same body is one file. A second fetch of the same URL with the same bytes
does not create another snapshot.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def save_snapshot(
    root: Path,
    url: str,
    body: bytes,
    *,
    content_type: str | None = None,
    text_hash: str | None = None,
    source_type: str | None = None,
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(body).hexdigest()
    blob = root / "blobs" / digest[:2] / digest
    created = not blob.exists()
    if created:
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(body)
    index = root / "by-url" / hashlib.sha256(url.encode()).hexdigest()
    previous = json.loads(index.read_text()) if index.exists() else None
    repeated = previous is not None and previous.get("content_hash") == digest
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"url": url, "content_hash": digest, "blob_ref": str(blob)}))
    result = {
        "url": url,
        "content_hash": digest,
        "blob_ref": str(blob),
        "created": created and not repeated,
    }
    if content_type and text_hash and source_type and _SHA256.fullmatch(text_hash):
        manifest = json.dumps(
            {
                "content_hash": digest,
                "content_type": content_type,
                "source_type": source_type,
                "text_hash": text_hash,
                "url": url,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        attestation_hash = hashlib.sha256(manifest).hexdigest()
        attestation = root / "attestations" / attestation_hash[:2] / attestation_hash
        if not attestation.exists():
            attestation.parent.mkdir(parents=True, exist_ok=True)
            attestation.write_bytes(manifest)
        result["attestation_ref"] = f"sha256:{attestation_hash}"
    return result


def read_attested_snapshot(
    root: Path,
    url: str,
    content_hash: str,
    *,
    content_type: str,
    text_hash: str,
    source_type: str,
    attestation_ref: str,
) -> bytes | None:
    """Read a blob only when its immutable retrieval attestation agrees."""
    if (
        not isinstance(url, str)
        or not url
        or not _SHA256.fullmatch(content_hash)
        or not _SHA256.fullmatch(text_hash)
        or not attestation_ref.startswith("sha256:")
    ):
        return None
    attestation_hash = attestation_ref.removeprefix("sha256:")
    if not _SHA256.fullmatch(attestation_hash):
        return None
    attestation = root / "attestations" / attestation_hash[:2] / attestation_hash
    blob = root / "blobs" / content_hash[:2] / content_hash
    try:
        manifest = attestation.read_bytes()
        record = json.loads(manifest)
        body = blob.read_bytes()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if hashlib.sha256(manifest).hexdigest() != attestation_hash:
        return None
    if not isinstance(record, dict):
        return None
    if record != {
        "content_hash": content_hash,
        "content_type": content_type,
        "source_type": source_type,
        "text_hash": text_hash,
        "url": url,
    }:
        return None
    if hashlib.sha256(body).hexdigest() != content_hash:
        return None
    return body
