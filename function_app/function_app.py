"""Azure Functions app — exposes /score for the SQA gatekeeper.

Uses the Python v2 programming model. Deployed to Flex Consumption
via Azure Functions Core Tools (`func azure functionapp publish`).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import azure.functions as func
import yaml
from pydantic import ValidationError

from shared.contracts import BudgetaryEstimate, SowDocument, WbsDocument
from sqa.gatekeeper import RubricLoadError, run_deterministic

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Rubric is bundled with the deployment package.
_RUBRIC_PATH = Path(__file__).parent / "rubrics" / "v1.yaml"
_RUBRIC_CACHE: dict[str, Any] | None = None


def _get_rubric() -> dict[str, Any]:
    global _RUBRIC_CACHE
    if _RUBRIC_CACHE is None:
        try:
            _RUBRIC_CACHE = yaml.safe_load(_RUBRIC_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RubricLoadError(f"Failed to load rubric at {_RUBRIC_PATH}: {exc}") from exc
    return _RUBRIC_CACHE


@app.route(route="health", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse('{"status":"ok"}', mimetype="application/json")


@app.route(route="score", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.ANONYMOUS)
def score(req: func.HttpRequest) -> func.HttpResponse:
    """Run the deterministic SQA gatekeeper against an artifact bundle.

    Expected body:
        {
          "runId": "...",
          "oppId": "...",
          "corpusSnapshotId": "...",
          "sow":  { ... SowDocument ... },
          "be":   { ... BudgetaryEstimate ... },
          "wbs":  { ... WbsDocument ... }
        }
    """
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            '{"error":"invalid JSON body"}', status_code=400, mimetype="application/json"
        )

    try:
        sow = SowDocument.model_validate(body["sow"])
        be = BudgetaryEstimate.model_validate(body["be"])
        wbs = WbsDocument.model_validate(body["wbs"])
    except (KeyError, ValidationError) as exc:
        return func.HttpResponse(
            f'{{"error":"contract validation failed","detail":{str(exc)!r}}}',
            status_code=422,
            mimetype="application/json",
        )

    try:
        rubric = _get_rubric()
        report = run_deterministic(
            rubric=rubric,
            sow=sow,
            be=be,
            wbs=wbs,
            run_id=str(body.get("runId", "")),
            opp_id=str(body.get("oppId", "")),
            corpus_snapshot_id=str(body.get("corpusSnapshotId", "")),
        )
    except RubricLoadError as exc:
        logging.exception("rubric load failed")
        return func.HttpResponse(
            f'{{"error":"rubric load failed","detail":{str(exc)!r}}}',
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        report.model_dump_json(),
        status_code=200,
        mimetype="application/json",
    )


# Hint for local debug only.
if __name__ == "__main__":
    logging.info("rubric=%s exists=%s", _RUBRIC_PATH, _RUBRIC_PATH.exists())
    os.environ.setdefault("FUNCTIONS_WORKER_RUNTIME", "python")
