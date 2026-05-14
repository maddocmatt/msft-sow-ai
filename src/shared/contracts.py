"""Pydantic contracts for the SOW AI pipeline.

Modeled on the DOI MVP's strict-contract approach (see C:\\doi-mvp\\src\\shared\\contracts.py).
The point is: every artifact a drafter produces must round-trip through these models so the
SQA Gatekeeper has a structured target to validate, not free-form prose.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

Severity = Literal["info", "minor", "major", "blocker"]


class CorpusCitation(BaseModel):
    """Pointer to a chunk in the grounding corpus. Mirrors DOI's FadCitation."""

    source: Literal["won_deal", "clause", "rate_card", "rejection_sample"]
    docId: str
    chunkId: str
    page: int | None = Field(default=None, ge=1)


class GroundedClaim(BaseModel):
    text: str
    citations: list[CorpusCitation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Opportunity intake
# ---------------------------------------------------------------------------


class OpportunityBrief(BaseModel):
    oppId: str
    customerName: str
    industry: str | None = None
    archetype: str | None = Field(
        default=None,
        description=(
            "e.g. 'AI agent enablement', 'Azure landing zone', 'Data platform modernization'"
        ),
    )
    summary: str
    desiredOutcomes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    timelineWeeks: int | None = Field(default=None, ge=1)
    budgetCeilingUsd: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Solution plan (Solution Architect output, shared by all drafters)
# ---------------------------------------------------------------------------


class Assumption(BaseModel):
    id: str
    text: str
    owner: Literal["customer", "vendor", "joint"]


class Risk(BaseModel):
    id: str
    text: str
    likelihood: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation: str


class Phase(BaseModel):
    id: str
    name: str
    objective: str
    durationWeeks: int = Field(ge=1)


class SolutionPlan(BaseModel):
    oppId: str
    archetype: str
    narrative: GroundedClaim
    phases: list[Phase]
    assumptions: list[Assumption]
    risks: list[Risk]
    referenceDealIds: list[str] = Field(
        default_factory=list,
        description="Past won-deal IDs the architect leaned on. Used by SQA for analogy.",
    )


# ---------------------------------------------------------------------------
# SOW
# ---------------------------------------------------------------------------

SOW_SECTION_ORDER: list[str] = [
    "background",
    "objectives",
    "scope",
    "out_of_scope",
    "approach",
    "deliverables",
    "assumptions",
    "roles_and_responsibilities",
    "schedule",
    "fees_and_payment",
    "terms",
]

SowSectionName = Literal[
    "background",
    "objectives",
    "scope",
    "out_of_scope",
    "approach",
    "deliverables",
    "assumptions",
    "roles_and_responsibilities",
    "schedule",
    "fees_and_payment",
    "terms",
]


class SowSection(BaseModel):
    name: SowSectionName
    title: str
    body: str
    claims: list[GroundedClaim] = Field(default_factory=list)


class SowDocument(BaseModel):
    oppId: str
    templateProfile: str = Field(
        description="Identifier of the template-profile this draft was rendered against."
    )
    sections: list[SowSection]

    @field_validator("sections")
    @classmethod
    def validate_section_order(cls, sections: list[SowSection]) -> list[SowSection]:
        actual = [s.name for s in sections]
        if actual != SOW_SECTION_ORDER:
            raise ValueError(
                "SOW sections must exactly match canonical order: " + ", ".join(SOW_SECTION_ORDER)
            )
        return sections


# ---------------------------------------------------------------------------
# Budgetary Estimate
# ---------------------------------------------------------------------------


class BeLineItem(BaseModel):
    role: str
    rateUsd: float = Field(ge=0)
    hours: float = Field(ge=0)
    phaseId: str
    wbsTaskId: str | None = Field(
        default=None,
        description="Required at SQA-pass time; allowed null while drafts are in flight.",
    )

    @property
    def extendedUsd(self) -> float:
        return round(self.rateUsd * self.hours, 2)


class BudgetaryEstimate(BaseModel):
    oppId: str
    currency: Literal["USD"] = "USD"
    lineItems: list[BeLineItem]
    contingencyPct: float = Field(default=0.10, ge=0, le=0.5)

    @property
    def subtotalUsd(self) -> float:
        return round(sum(li.extendedUsd for li in self.lineItems), 2)

    @property
    def totalUsd(self) -> float:
        return round(self.subtotalUsd * (1 + self.contingencyPct), 2)


# ---------------------------------------------------------------------------
# WBS
# ---------------------------------------------------------------------------


class WbsTask(BaseModel):
    id: str
    phaseId: str
    name: str
    durationDays: int = Field(ge=1)
    dependsOn: list[str] = Field(default_factory=list)
    raci: dict[str, Literal["R", "A", "C", "I"]] = Field(default_factory=dict)


class WbsDocument(BaseModel):
    oppId: str
    tasks: list[WbsTask]


# ---------------------------------------------------------------------------
# SQA report
# ---------------------------------------------------------------------------


class SqaFinding(BaseModel):
    ruleId: str
    severity: Severity
    artifact: Literal["sow", "be", "wbs", "collateral", "plan"]
    locator: str = Field(
        description="Section name, line number, or cell reference depending on artifact."
    )
    description: str
    remediationHint: str | None = None


class SqaReport(BaseModel):
    oppId: str
    runId: str
    rubricVersion: str
    corpusSnapshotId: str
    passed: bool
    findings: list[SqaFinding] = Field(default_factory=list)

    @field_validator("passed")
    @classmethod
    def passed_implies_no_blockers(cls, passed: bool, info) -> bool:
        findings: list[SqaFinding] = info.data.get("findings", []) or []
        if passed and any(f.severity == "blocker" for f in findings):
            raise ValueError("Cannot mark passed=True while blocker findings exist.")
        return passed
