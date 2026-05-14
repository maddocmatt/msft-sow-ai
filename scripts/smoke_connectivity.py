"""Local connectivity smoke test for the deployed Azure resources.

Verifies that DefaultAzureCredential (the developer's Azure CLI session) can
reach every data-plane resource the operator was granted RBAC on.

Run after `az login` and a successful Bicep deployment.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.blob import BlobServiceClient


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _fail(msg: str, exc: BaseException) -> None:
    print(f"  [FAIL] {msg}: {type(exc).__name__}: {exc}")


def check_storage(cred: Any, account_name: str) -> bool:
    print(f"Storage  https://{account_name}.blob.core.windows.net")
    try:
        client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=cred,
        )
        names = [c.name for c in client.list_containers(results_per_page=20)]
        _ok(f"containers: {names}")
        return True
    except Exception as exc:
        _fail("list_containers", exc)
        return False


def check_search(cred: Any, service_name: str) -> bool:
    print(f"Search   https://{service_name}.search.windows.net")
    try:
        client = SearchIndexClient(
            endpoint=f"https://{service_name}.search.windows.net",
            credential=cred,
        )
        stats = client.get_service_statistics()
        counters = stats.get("counters", {})
        idx = counters.get("indexes_count") or counters.get("index_counter") or {}
        _ok(f"counters: indexes={idx}")
        return True
    except Exception as exc:
        _fail("get_service_statistics", exc)
        return False


def check_cosmos(cred: Any, account_name: str) -> bool:
    print(f"Cosmos   https://{account_name}.documents.azure.com")
    try:
        client = CosmosClient(
            url=f"https://{account_name}.documents.azure.com",
            credential=cred,
        )
        db = client.get_database_client("sowai")
        containers = [c["id"] for c in db.list_containers()]
        _ok(f"containers: {containers}")
        return True
    except Exception as exc:
        _fail("list_containers", exc)
        return False


def check_foundry(cred: Any, endpoint: str) -> bool:
    print(f"Foundry  {endpoint}")
    try:
        token = cred.get_token("https://cognitiveservices.azure.com/.default")
        prefix = token.token[:12]
        _ok(f"token acquired (prefix={prefix}..., expires_on={token.expires_on})")
        return True
    except Exception as exc:
        _fail("get_token", exc)
        return False


def main() -> int:
    storage = os.environ.get("SOWAI_STORAGE", "stsowaidevge5xqflpbrmnw")
    search = os.environ.get("SOWAI_SEARCH", "srch-sowai-dev-ge5xqflpbrmnw")
    cosmos = os.environ.get("SOWAI_COSMOS", "cosmos-sowai-dev-ge5xqflpbrmnw")
    foundry = os.environ.get(
        "SOWAI_FOUNDRY",
        "https://aif-sowai-dev-ge5xqflpbrmnw.cognitiveservices.azure.com/",
    )

    cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)

    results = [
        check_storage(cred, storage),
        check_search(cred, search),
        check_cosmos(cred, cosmos),
        check_foundry(cred, foundry),
    ]
    print()
    print(f"Result: {sum(results)}/{len(results)} services reachable")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
