"""Publish a rubric YAML to Cosmos `rubric_versions` for reproducibility.

Reads `sqa/rubrics/<version>.yaml`, computes a sha256 of the raw bytes, and
upserts a document keyed by the rubric's semantic `version` field. The
gatekeeper records this `version` on every SqaReport so that any past run
can re-load its exact rubric from Cosmos.

Usage:
    python scripts/publish_rubric.py                # publishes v1.yaml
    python scripts/publish_rubric.py --file v0.yaml
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

ROOT = Path(__file__).resolve().parent.parent
RUBRICS = ROOT / "sqa" / "rubrics"


def load(path: Path) -> tuple[dict[str, Any], str, bytes]:
    raw = path.read_bytes()
    body = yaml.safe_load(raw)
    if not isinstance(body, dict) or "version" not in body:
        raise SystemExit(f"{path} missing top-level `version` field")
    return body, str(body["version"]), raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="v1.yaml", help="Rubric file in sqa/rubrics/")
    ap.add_argument(
        "--cosmos",
        default=os.environ.get("SOWAI_COSMOS", "cosmos-sowai-dev-ge5xqflpbrmnw"),
    )
    ap.add_argument("--database", default="sowai")
    ap.add_argument("--container", default="rubric_versions")
    args = ap.parse_args()

    path = RUBRICS / args.file
    if not path.exists():
        raise SystemExit(f"rubric not found: {path}")

    body, version, raw = load(path)
    sha = hashlib.sha256(raw).hexdigest()
    rule_count = len(body.get("rules", []))

    doc = {
        "id": version,
        "version": version,
        "sha256": sha,
        "ruleCount": rule_count,
        "publishedAt": dt.datetime.now(dt.UTC).isoformat(),
        "sourceFile": f"sqa/rubrics/{args.file}",
        "rubric": body,
    }

    cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    client = CosmosClient(
        url=f"https://{args.cosmos}.documents.azure.com",
        credential=cred,
    )
    container = client.get_database_client(args.database).get_container_client(args.container)
    container.upsert_item(doc)

    print(f"published rubric {version} sha256={sha[:12]}... rules={rule_count}")
    print(f"  cosmos: {args.cosmos}/{args.database}/{args.container}/{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
