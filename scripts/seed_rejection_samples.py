"""Seed the `idx-rejection-samples` index used by the analogy critic.

Creates the index if missing, then uploads a small corpus of historical SOW
rejection patterns. Run once to bootstrap; safe to re-run (uses upload/merge).

Env:
  SOWAI_SEARCH  AI Search service short name (e.g. srch-sowai-dev-...)

Auth: DefaultAzureCredential. Caller must have:
  - Search Service Contributor (to create index)
  - Search Index Data Contributor (to upload docs)
"""

from __future__ import annotations

import os
import sys

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)

INDEX_NAME = "idx-rejection-samples"

SAMPLES: list[dict[str, str]] = [
    {
        "id": "rej-001",
        "category": "voice",
        "section": "scope",
        "text": (
            "Bullet read 'The platform will automatically scale workloads.' "
            "Rejected: scope must describe Microsoft activities, not finished "
            "system capabilities. Rewrite as 'Microsoft will configure "
            "autoscaling for the workload tiers identified in the design.'"
        ),
    },
    {
        "id": "rej-002",
        "category": "deliverables",
        "section": "deliverables",
        "text": (
            "Deliverables listed as 'production-ready system'. Rejected: "
            "deliverables must be discrete, named artifacts (design document, "
            "deployed infrastructure, runbook). 'Production-ready' is a "
            "qualitative outcome, not a deliverable."
        ),
    },
    {
        "id": "rej-003",
        "category": "assumptions",
        "section": "assumptions",
        "text": (
            "Assumption stated 'Customer will provide all required access in "
            "a timely manner.' Rejected: assumptions must be specific and "
            "testable. Replace with named roles, named environments, and a "
            "concrete SLA window (e.g. within 5 business days of kickoff)."
        ),
    },
    {
        "id": "rej-004",
        "category": "out_of_scope",
        "section": "out_of_scope",
        "text": (
            "Out-of-scope section was empty. Rejected: every fixed-fee SOW "
            "must enumerate exclusions. Common exclusions: data migration "
            "from legacy systems, third-party license procurement, custom "
            "application development, ongoing operations beyond go-live."
        ),
    },
    {
        "id": "rej-005",
        "category": "schedule",
        "section": "schedule",
        "text": (
            "Schedule had no milestone gates. Rejected: schedule must include "
            "named milestones with acceptance criteria (e.g. 'Design review "
            "complete: signed-off design document received from customer')."
        ),
    },
    {
        "id": "rej-006",
        "category": "fees",
        "section": "fees_and_payment",
        "text": (
            "Fees described as time-and-materials with no cap. Rejected: "
            "Microsoft Federal SOWs require either fixed-fee or T&M with a "
            "not-to-exceed ceiling and named change-order procedure."
        ),
    },
]


def _service_endpoint() -> str:
    name = os.environ.get("SOWAI_SEARCH")
    if not name:
        sys.exit("SOWAI_SEARCH env var not set")
    return f"https://{name}.search.windows.net"


def _ensure_index(endpoint: str, cred: DefaultAzureCredential) -> None:
    client = SearchIndexClient(endpoint=endpoint, credential=cred)
    existing = {i.name for i in client.list_indexes()}
    if INDEX_NAME in existing:
        print(f"index '{INDEX_NAME}' already exists")
        return
    fields: list[SearchField] = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(
            name="category", type=SearchFieldDataType.String, filterable=True, facetable=True
        ),
        SimpleField(
            name="section", type=SearchFieldDataType.String, filterable=True, facetable=True
        ),
        SearchableField(name="text", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
    ]
    client.create_index(SearchIndex(name=INDEX_NAME, fields=fields))
    print(f"created index '{INDEX_NAME}'")


def _upload(endpoint: str, cred: DefaultAzureCredential) -> None:
    client = SearchClient(endpoint=endpoint, index_name=INDEX_NAME, credential=cred)
    result = client.upload_documents(documents=SAMPLES)
    succeeded = sum(1 for r in result if r.succeeded)
    print(f"uploaded {succeeded}/{len(SAMPLES)} samples")


def main() -> None:
    endpoint = _service_endpoint()
    cred = DefaultAzureCredential()
    _ensure_index(endpoint, cred)
    _upload(endpoint, cred)


if __name__ == "__main__":
    main()
