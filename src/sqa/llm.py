"""LLM client abstraction for SQA judges.

Two implementations:

- `StubLlm` — deterministic, never calls a network. Used in tests and as the
  default when no Foundry/AOAI deployment is configured.
- `AzureOpenAIChat` — Azure OpenAI / Foundry chat completion against a named
  deployment using `DefaultAzureCredential` (no API keys).

Both expose the same `complete_json(system, user, schema_hint)` signature,
returning a parsed `dict[str, Any]`. The stub returns
`{"items": [], "_stub": True}` so judges short-circuit cleanly when no model
is wired.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol


class LlmClient(Protocol):
    def complete_json(self, *, system: str, user: str, schema_hint: str) -> dict[str, Any]: ...


class StubLlm:
    """No-op client; returns an empty result so judges add zero findings."""

    def complete_json(self, *, system: str, user: str, schema_hint: str) -> dict[str, Any]:
        return {"items": [], "_stub": True}


class AzureOpenAIChat:
    """Azure OpenAI / Foundry chat completion via DefaultAzureCredential.

    Lazy-imports azure-identity and httpx so test envs without those deps
    can still import this module.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        api_version: str = "2024-10-21",
        timeout_s: float = 30.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.deployment = deployment
        self.api_version = api_version
        self.timeout_s = timeout_s

    def _token(self) -> str:
        from azure.identity import DefaultAzureCredential

        cred = DefaultAzureCredential()
        return cred.get_token("https://cognitiveservices.azure.com/.default").token

    def complete_json(self, *, system: str, user: str, schema_hint: str) -> dict[str, Any]:
        import httpx

        url = (
            f"{self.endpoint}/openai/deployments/{self.deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )
        sys_msg = system + "\n\nRespond ONLY with valid JSON " + schema_hint
        body = {
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self._token()}"}
        with httpx.Client(timeout=self.timeout_s) as c:
            r = c.post(url, json=body, headers=headers)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        result: dict[str, Any] = json.loads(content)
        return result


def from_env() -> LlmClient:
    """Construct a client from environment.

    SOWAI_LLM_MODE = "azure" | "stub" (default: stub)
    SOWAI_FOUNDRY_ENDPOINT = e.g. https://aif-sowai-dev-ge5xqflpbrmnw.cognitiveservices.azure.com/
    SOWAI_LLM_DEPLOYMENT  = name of the chat deployment (e.g. gpt-4o-mini)
    """
    mode = os.environ.get("SOWAI_LLM_MODE", "stub").lower()
    if mode != "azure":
        return StubLlm()
    endpoint = os.environ.get("SOWAI_FOUNDRY_ENDPOINT")
    deployment = os.environ.get("SOWAI_LLM_DEPLOYMENT")
    if not endpoint or not deployment:
        return StubLlm()
    return AzureOpenAIChat(endpoint=endpoint, deployment=deployment)


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class StubEmbedder:
    """Deterministic dummy embedder; returns zero vectors of fixed dim."""

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]


class AzureOpenAIEmbed:
    """Azure OpenAI embeddings via DefaultAzureCredential."""

    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        api_version: str = "2024-10-21",
        timeout_s: float = 30.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.deployment = deployment
        self.api_version = api_version
        self.timeout_s = timeout_s

    def _token(self) -> str:
        from azure.identity import DefaultAzureCredential

        cred = DefaultAzureCredential()
        return cred.get_token("https://cognitiveservices.azure.com/.default").token

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        url = (
            f"{self.endpoint}/openai/deployments/{self.deployment}"
            f"/embeddings?api-version={self.api_version}"
        )
        headers = {"Authorization": f"Bearer {self._token()}"}
        with httpx.Client(timeout=self.timeout_s) as c:
            r = c.post(url, json={"input": texts}, headers=headers)
            r.raise_for_status()
            data = r.json()["data"]
        return [list(item["embedding"]) for item in data]


def embedder_from_env() -> Embedder:
    """SOWAI_EMBED_DEPLOYMENT (+ SOWAI_FOUNDRY_ENDPOINT, SOWAI_LLM_MODE=azure)."""
    mode = os.environ.get("SOWAI_LLM_MODE", "stub").lower()
    endpoint = os.environ.get("SOWAI_FOUNDRY_ENDPOINT")
    deployment = os.environ.get("SOWAI_EMBED_DEPLOYMENT")
    if mode != "azure" or not endpoint or not deployment:
        return StubEmbedder()
    return AzureOpenAIEmbed(endpoint=endpoint, deployment=deployment)
