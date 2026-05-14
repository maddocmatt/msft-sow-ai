"""Smoke tests for the deterministic SQA gatekeeper."""

from __future__ import annotations

from pathlib import Path

from src.shared.contracts import (
    SOW_SECTION_ORDER,
    BeLineItem,
    BudgetaryEstimate,
    SowDocument,
    SowSection,
    WbsDocument,
    WbsTask,
)
from src.sqa.gatekeeper import load_rubric, run_deterministic

RUBRIC_PATH = Path(__file__).resolve().parents[1] / "sqa" / "rubrics" / "v0.yaml"


def _clean_sow() -> SowDocument:
    return SowDocument(
        oppId="opp-1",
        templateProfile="ms-services-v1",
        sections=[
            SowSection(name=n, title=n.title(), body="finalized content.")
            for n in SOW_SECTION_ORDER
        ],
    )


def _wbs_with(task_id: str = "t1") -> WbsDocument:
    return WbsDocument(
        oppId="opp-1", tasks=[WbsTask(id=task_id, phaseId="p1", name="Task", durationDays=5)]
    )


def test_clean_bundle_passes() -> None:
    rubric = load_rubric(RUBRIC_PATH)
    sow = _clean_sow()
    wbs = _wbs_with("t1")
    be = BudgetaryEstimate(
        oppId="opp-1",
        lineItems=[
            BeLineItem(role="Architect", rateUsd=300.0, hours=10, phaseId="p1", wbsTaskId="t1")
        ],
    )
    report = run_deterministic(
        rubric=rubric,
        sow=sow,
        be=be,
        wbs=wbs,
        run_id="r1",
        opp_id="opp-1",
        corpus_snapshot_id="snap-1",
    )
    assert report.passed, [f.model_dump() for f in report.findings]


def test_placeholder_token_blocks() -> None:
    rubric = load_rubric(RUBRIC_PATH)
    sow = _clean_sow()
    sow.sections[0].body = "intro is TBD pending review."
    report = run_deterministic(
        rubric=rubric,
        sow=sow,
        run_id="r1",
        opp_id="opp-1",
        corpus_snapshot_id="snap-1",
    )
    assert not report.passed
    assert any(f.ruleId == "SOW-PLACEHOLDER-001" for f in report.findings)


def test_dangling_be_wbs_link_blocks() -> None:
    rubric = load_rubric(RUBRIC_PATH)
    sow = _clean_sow()
    wbs = _wbs_with("t1")
    be = BudgetaryEstimate(
        oppId="opp-1",
        lineItems=[
            BeLineItem(
                role="Engineer", rateUsd=200.0, hours=10, phaseId="p1", wbsTaskId="does-not-exist"
            )
        ],
    )
    report = run_deterministic(
        rubric=rubric,
        sow=sow,
        be=be,
        wbs=wbs,
        run_id="r1",
        opp_id="opp-1",
        corpus_snapshot_id="snap-1",
    )
    assert not report.passed
    assert any(f.ruleId == "BE-WBS-LINK-001" for f in report.findings)
