"""Seed the `idx-rejection-samples` index used by the analogy critic.

(Re)creates the index with a vector `embedding` field (HNSW), embeds each
sample with the configured Azure OpenAI embedding deployment, and uploads.

Env:
  SOWAI_SEARCH             AI Search service short name
  SOWAI_FOUNDRY_ENDPOINT   Azure OpenAI / Foundry endpoint
  SOWAI_EMBED_DEPLOYMENT   Embedding deployment (e.g. text-embedding-3-small)
  SOWAI_LLM_MODE           Set to "azure" to enable real embeddings

Auth: DefaultAzureCredential. Caller must have:
  - Search Service Contributor (to create index)
  - Search Index Data Contributor (to upload docs)
  - Cognitive Services OpenAI User (to call embeddings)
"""

from __future__ import annotations

import os
import sys

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from sqa.llm import embedder_from_env

INDEX_NAME = "idx-rejection-samples"
EMBED_DIM = 1536  # text-embedding-3-small

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


def _build_index() -> SearchIndex:
    fields: list[SearchField] = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(
            name="category", type=SearchFieldDataType.String, filterable=True, facetable=True
        ),
        SimpleField(
            name="section", type=SearchFieldDataType.String, filterable=True, facetable=True
        ),
        SearchableField(name="text", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBED_DIM,
            vector_search_profile_name="hnsw-default",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-cfg")],
        profiles=[
            VectorSearchProfile(name="hnsw-default", algorithm_configuration_name="hnsw-cfg")
        ],
    )
    return SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)


def _recreate_index(endpoint: str, cred: DefaultAzureCredential) -> None:
    client = SearchIndexClient(endpoint=endpoint, credential=cred)
    existing = {i.name for i in client.list_indexes()}
    if INDEX_NAME in existing:
        client.delete_index(INDEX_NAME)
        print(f"deleted existing index '{INDEX_NAME}'")
    client.create_index(_build_index())
    print(f"created index '{INDEX_NAME}' with vector field (dim={EMBED_DIM})")


def _upload(endpoint: str, cred: DefaultAzureCredential) -> None:
    embedder = embedder_from_env()
    vectors = embedder.embed([s["text"] for s in SAMPLES])
    docs = [{**s, "embedding": v} for s, v in zip(SAMPLES, vectors, strict=True)]
    client = SearchClient(endpoint=endpoint, index_name=INDEX_NAME, credential=cred)
    result = client.upload_documents(documents=docs)
    succeeded = sum(1 for r in result if r.succeeded)
    print(f"uploaded {succeeded}/{len(docs)} samples (embedder={type(embedder).__name__})")


def main() -> None:
    endpoint = _service_endpoint()
    cred = DefaultAzureCredential()
    _recreate_index(endpoint, cred)
    _upload(endpoint, cred)


if __name__ == "__main__":
    main()
