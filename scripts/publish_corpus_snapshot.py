"""Publish a corpus snapshot to blob storage for reproducible runs.

Walks the local `corpus/` tree, computes a sha256 for every file (skipping
.gitkeep markers), builds a manifest, and uploads it to the `corpus`
container under `_snapshots/<snapshot_id>.json`. The snapshot_id is the
sha256 of the canonicalized manifest body itself, so identical corpus
states produce identical IDs.

Every SQA run pins this snapshot_id; re-running an opportunity reproduces
the same retrieval set.

Usage:
    python scripts/publish_corpus_snapshot.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"


def hash_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def build_manifest() -> dict:
    files = []
    for p in sorted(CORPUS.rglob("*")):
        if not p.is_file():
            continue
        if p.name == ".gitkeep":
            continue
        rel = p.relative_to(CORPUS).as_posix()
        sha, size = hash_file(p)
        files.append({"path": rel, "sha256": sha, "size": size})

    # Snapshot ID is the hash of the file list (not date/time), so identical
    # corpus content yields identical snapshot IDs.
    files_payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    snapshot_id = "cs_" + hashlib.sha256(files_payload).hexdigest()[:24]

    return {
        "snapshotId": snapshot_id,
        "createdAt": dt.datetime.now(dt.UTC).isoformat(),
        "fileCount": len(files),
        "files": files,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--storage",
        default=os.environ.get("SOWAI_STORAGE", "stsowaidevge5xqflpbrmnw"),
    )
    ap.add_argument("--container", default="corpus")
    ap.add_argument("--prefix", default="_snapshots")
    args = ap.parse_args()

    if not CORPUS.exists():
        raise SystemExit(f"corpus directory not found: {CORPUS}")

    manifest = build_manifest()
    snapshot_id = manifest["snapshotId"]
    blob_path = f"{args.prefix}/{snapshot_id}.json"
    body = json.dumps(manifest, indent=2).encode()

    cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    bsc = BlobServiceClient(
        account_url=f"https://{args.storage}.blob.core.windows.net",
        credential=cred,
    )
    cc = bsc.get_container_client(args.container)
    cc.upload_blob(name=blob_path, data=body, overwrite=True)

    # Also stamp a "latest" pointer so consumers without a pinned ID can
    # discover the most recent snapshot.
    cc.upload_blob(
        name=f"{args.prefix}/_latest.json",
        data=json.dumps({"snapshotId": snapshot_id, "fileCount": manifest["fileCount"]}).encode(),
        overwrite=True,
    )

    print(f"published snapshot {snapshot_id} files={manifest['fileCount']}")
    print(f"  blob: {args.storage}/{args.container}/{blob_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
