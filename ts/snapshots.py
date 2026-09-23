"""Content-addressed snapshots on disk (PLAN_7.2 §6: no S3).

The same body is one file. A second fetch of the same URL with the same bytes
does not create another snapshot.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def save_snapshot(root: Path, url: str, body: bytes) -> dict:
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
    return {"url": url, "content_hash": digest, "blob_ref": str(blob), "created": created and not repeated}
