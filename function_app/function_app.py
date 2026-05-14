"""Azure Functions app — exposes /score for the SQA gatekeeper.

Uses the Python v2 programming model. Deployed to Flex Consumption
via Azure Functions Core Tools (`func azure functionapp publish`).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import azure.functions as func
import templates_loader
import yaml
from pydantic import ValidationError

from shared.contracts import BudgetaryEstimate, SowDocument, WbsDocument
from sqa.gatekeeper import RubricLoadError, run_full

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


@app.route(route="templates", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def templates_list(req: func.HttpRequest) -> func.HttpResponse:
    """List all available SOW templates (for the engagement-type picker)."""
    return func.HttpResponse(
        json.dumps({"templates": templates_loader.list_templates()}),
        status_code=200,
        mimetype="application/json",
    )


@app.route(
    route="templates/{template_id}",
    methods=[func.HttpMethod.GET],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def template_detail(req: func.HttpRequest) -> func.HttpResponse:
    """Return the section tree + per-section guidance for one template."""
    tid = req.route_params.get("template_id", "")
    try:
        tmpl = templates_loader.load_template(tid)
    except templates_loader.TemplateNotFound:
        return func.HttpResponse(
            f'{{"error":"template not found","templateId":{tid!r}}}',
            status_code=404,
            mimetype="application/json",
        )
    return func.HttpResponse(json.dumps(tmpl), status_code=200, mimetype="application/json")


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
        # Layer toggles via query string so callers can A/B between layers.
        # Default: deterministic + judges. Analogy off (needs index).
        layers = (req.params.get("layers") or "det,judges").lower()
        template_id = (body.get("templateId") or "").strip() or None
        template_doc: dict[str, Any] | None = None
        if template_id:
            try:
                template_doc = templates_loader.load_template(template_id)
            except templates_loader.TemplateNotFound:
                template_doc = None
        report = run_full(
            rubric=rubric,
            sow=sow,
            be=be,
            wbs=wbs,
            run_id=str(body.get("runId", "")),
            opp_id=str(body.get("oppId", "")),
            corpus_snapshot_id=str(body.get("corpusSnapshotId", "")),
            enable_judges="judges" in layers,
            enable_analogy="analogy" in layers,
            template_doc=template_doc,
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
