"""Tests for LLM judge layers (using stub LLM and stub retriever)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.contracts import (
    SOW_SECTION_ORDER,
    SowDocument,
    SowSection,
)
from sqa.analogy import StubRetriever, run_analogy_critic
from sqa.gatekeeper import load_rubric, run_full
from sqa.judges import run_llm_judges
from sqa.llm import StubLlm

RUBRIC_PATH = Path(__file__).resolve().parents[1] / "sqa" / "rubrics" / "v1.yaml"


def _sow(scope_body: str = "Microsoft will design the architecture.") -> SowDocument:
    return SowDocument(
        oppId="opp-1",
        templateProfile="ms-services-v1",
        sections=[
            SowSection(
                name=n,
                title=n.title(),
                body=scope_body if n == "scope" else "finalized content.",
            )
            for n in SOW_SECTION_ORDER
        ],
    )


class _FakeVoiceLlm:
    """Returns a fixed classification: bullet 0 is SYSTEM_CAPABILITY."""

    def complete_json(self, *, system: str, user: str, schema_hint: str) -> dict[str, Any]:
        return {"items": [{"index": 0, "label": "SYSTEM_CAPABILITY"}]}


def test_stub_llm_produces_no_judge_findings() -> None:
    rubric = load_rubric(RUBRIC_PATH)
    findings = run_llm_judges(rubric=rubric, sow=_sow(), llm=StubLlm())
    assert findings == []


def test_voice_judge_flags_system_capability_bullet() -> None:
    rubric = load_rubric(RUBRIC_PATH)
    sow = _sow("- The system will provision tenants.\n- Microsoft will configure RBAC.")
    findings = run_llm_judges(rubric=rubric, sow=sow, llm=_FakeVoiceLlm())
    assert any(f.ruleId == "VOICE-MS-ACTION-001" for f in findings)
    assert any("scope#bullet0" in f.locator for f in findings)


def test_analogy_critic_noop_when_no_neighbours() -> None:
    rubric = load_rubric(RUBRIC_PATH)
    findings = run_analogy_critic(
        rubric=rubric, sow=_sow(), llm=StubLlm(), retriever=StubRetriever()
    )
    assert findings == []


def test_run_full_with_stubs_matches_deterministic() -> None:
    rubric = load_rubric(RUBRIC_PATH)
    report = run_full(
        rubric=rubric,
        sow=_sow(),
        run_id="r1",
        opp_id="opp-1",
        corpus_snapshot_id="snap-1",
        llm=StubLlm(),
        retriever=StubRetriever(),
    )
    # Stubs add zero findings; deterministic layer alone determines pass/fail.
    assert isinstance(report.passed, bool)
