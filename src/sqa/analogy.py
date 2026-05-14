"""Layer 3 — analogy critic.

Retrieves the k-nearest historical SQA rejections from the rejection-samples
search index, then asks the LLM whether those same rejection reasons apply to
the current draft. Falls back to a stub retriever (returns no neighbours) when
no AI Search endpoint is configured, in which case the layer is a no-op.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from shared.contracts import SowDocument, SqaFinding

from .llm import Embedder, LlmClient, StubEmbedder, embedder_from_env

_ANALOGY_SYSTEM = (
    "You compare a candidate Microsoft Federal SOW excerpt to historical "
    "rejection samples. For each historical rejection that would still apply "
    "to the candidate, emit a finding."
)

_ANALOGY_SCHEMA = (
    'matching this shape: {"items": [{"reason": str, "locator": str}]} '
    "where locator is a SOW section name plus optional anchor."
)


class Retriever(Protocol):
    def topk(self, *, index: str, query: str, k: int) -> list[dict[str, Any]]: ...


class StubRetriever:
    """Returns no neighbours; analogy critic becomes a no-op."""

    def topk(self, *, index: str, query: str, k: int) -> list[dict[str, Any]]:
        return []


class AzureSearchRetriever:
    """Azure AI Search vector retriever (uses an embedder for the query).

    Falls back to keyword search if no embedder is provided. Uses
    DefaultAzureCredential.
    """

    def __init__(
        self,
        *,
        service_name: str,
        embedder: Embedder | None = None,
        vector_field: str = "embedding",
    ) -> None:
        self.service_name = service_name
        self.embedder = embedder
        self.vector_field = vector_field

    def topk(self, *, index: str, query: str, k: int) -> list[dict[str, Any]]:
        from azure.identity import DefaultAzureCredential
        from azure.search.documents import SearchClient

        client = SearchClient(
            endpoint=f"https://{self.service_name}.search.windows.net",
            index_name=index,
            credential=DefaultAzureCredential(),
        )
        if self.embedder is not None and not isinstance(self.embedder, StubEmbedder):
            from azure.search.documents.models import VectorizedQuery

            vec = self.embedder.embed([query])[0]
            vq = VectorizedQuery(vector=vec, k_nearest_neighbors=k, fields=self.vector_field)
            results = client.search(search_text=None, vector_queries=[vq], top=k)
        else:
            results = client.search(search_text=query, top=k)
        return [dict(r) for r in results]


def retriever_from_env() -> Retriever:
    name = os.environ.get("SOWAI_SEARCH")
    if not name:
        return StubRetriever()
    return AzureSearchRetriever(service_name=name, embedder=embedder_from_env())


def run_analogy_critic(
    *,
    rubric: dict[str, Any],
    sow: SowDocument | None,
    llm: LlmClient,
    retriever: Retriever,
) -> list[SqaFinding]:
    if sow is None:
        return []

    rule = next(
        (
            r
            for r in rubric.get("rules", [])
            if (r.get("detector") or {}).get("kind") == "llm_judge"
            and "index" in ((r.get("detector") or {}).get("spec") or {})
        ),
        None,
    )
    if rule is None:
        return []

    spec = rule["detector"]["spec"]
    index = spec["index"]
    top_k = int(spec.get("topK", 5))

    # Compose a compact query from the SOW; in practice we'd embed this.
    query = "\n".join(f"{s.name}: {s.body[:300]}" for s in sow.sections)
    neighbours = retriever.topk(index=index, query=query, k=top_k)
    if not neighbours:
        return []

    user = (
        "Candidate SOW:\n"
        + query
        + "\n\nHistorical rejections (top "
        + str(len(neighbours))
        + "):\n"
        + "\n---\n".join((n.get("text") or n.get("content") or str(n))[:600] for n in neighbours)
    )
    raw = llm.complete_json(system=_ANALOGY_SYSTEM, user=user, schema_hint=_ANALOGY_SCHEMA)
    items = raw.get("items") or []

    findings: list[SqaFinding] = []
    for item in items:
        reason = str(item.get("reason", "")).strip()
        locator = str(item.get("locator", "sow")).strip() or "sow"
        if not reason:
            continue
        findings.append(
            SqaFinding(
                ruleId=rule["id"],
                severity=rule["severity"],
                artifact=rule["artifact"],
                locator=locator,
                description=reason,
                remediationHint=rule.get("remediation_hint"),
            )
        )
    return findings
