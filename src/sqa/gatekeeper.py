"""SQA Gatekeeper — runs the rubric against an artifact bundle.

This module hosts the deterministic + regex layers. The LLM analogy critic
lives in agents/sqa_gatekeeper/* and is invoked by the orchestrator. We keep
the two separated so the cheap deterministic checks can short-circuit before
any model call.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from shared.contracts import (
    SOW_SECTION_ORDER,
    BudgetaryEstimate,
    SowDocument,
    SqaFinding,
    SqaReport,
    WbsDocument,
)


class RubricLoadError(Exception):
    """Raised when the rubric YAML cannot be parsed or is structurally invalid."""


def load_rubric(path: Path) -> dict[str, Any]:
    """Load a rubric YAML file and do shallow shape validation."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RubricLoadError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict) or "rules" not in data or "version" not in data:
        raise RubricLoadError(f"Rubric {path} missing required keys 'version' and 'rules'.")
    return data


# ---------------------------------------------------------------------------
# Structural detectors
# ---------------------------------------------------------------------------


def _check_sow_section_order(sow: SowDocument) -> bool:
    actual: list[str] = [s.name for s in sow.sections]
    return actual == list(SOW_SECTION_ORDER)


def _check_assumption_owner_present(plan_assumptions: Iterable[Any]) -> bool:
    return all(
        getattr(a, "owner", None) in {"customer", "vendor", "joint"} for a in plan_assumptions
    )


def _check_be_lineitems_link_wbs(be: BudgetaryEstimate, wbs: WbsDocument) -> list[str]:
    """Return list of line-item indices missing a valid wbsTaskId."""
    valid_ids = {t.id for t in wbs.tasks}
    return [
        f"lineItems[{i}]"
        for i, li in enumerate(be.lineItems)
        if not li.wbsTaskId or li.wbsTaskId not in valid_ids
    ]


def _check_wbs_no_dangling_deps(wbs: WbsDocument) -> list[str]:
    ids = {t.id for t in wbs.tasks}
    bad: list[str] = []
    for t in wbs.tasks:
        for dep in t.dependsOn:
            if dep not in ids:
                bad.append(f"{t.id}->{dep}")
    return bad


# ---------------------------------------------------------------------------
# Regex detector
# ---------------------------------------------------------------------------


def _scan_text_for_pattern(text: str, pattern: str) -> list[int]:
    """Return character offsets of matches for the given pattern."""
    return [m.start() for m in re.finditer(pattern, text)]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def run_deterministic(
    *,
    rubric: dict[str, Any],
    sow: SowDocument | None = None,
    be: BudgetaryEstimate | None = None,
    wbs: WbsDocument | None = None,
    run_id: str,
    opp_id: str,
    corpus_snapshot_id: str,
) -> SqaReport:
    """Run all non-LLM rules and return a partial SqaReport.

    The orchestrator should subsequently merge findings from the LLM analogy
    critic before producing a final pass/fail decision.
    """
    findings: list[SqaFinding] = []

    for rule in rubric.get("rules", []):
        rid: str = rule["id"]
        severity = rule["severity"]
        artifact = rule["artifact"]
        detector = rule["detector"]
        kind = detector["kind"]
        hint = rule.get("remediation_hint")

        if kind == "structural":
            check = detector["spec"]["check"]
            if check == "sow_section_order" and sow is not None:
                if not _check_sow_section_order(sow):
                    findings.append(
                        SqaFinding(
                            ruleId=rid,
                            severity=severity,
                            artifact=artifact,
                            locator="sections",
                            description=rule["description"],
                            remediationHint=hint,
                        )
                    )
            elif check == "be_lineitems_link_wbs" and be is not None and wbs is not None:
                for loc in _check_be_lineitems_link_wbs(be, wbs):
                    findings.append(
                        SqaFinding(
                            ruleId=rid,
                            severity=severity,
                            artifact=artifact,
                            locator=loc,
                            description=rule["description"],
                            remediationHint=hint,
                        )
                    )
            elif check == "wbs_no_dangling_deps" and wbs is not None:
                for loc in _check_wbs_no_dangling_deps(wbs):
                    findings.append(
                        SqaFinding(
                            ruleId=rid,
                            severity=severity,
                            artifact=artifact,
                            locator=loc,
                            description=rule["description"],
                            remediationHint=hint,
                        )
                    )

        elif kind == "regex" and sow is not None:
            pattern = detector["spec"]["pattern"]
            for section in sow.sections:
                hits = _scan_text_for_pattern(section.body, pattern)
                for offset in hits:
                    findings.append(
                        SqaFinding(
                            ruleId=rid,
                            severity=severity,
                            artifact=artifact,
                            locator=f"{section.name}@{offset}",
                            description=rule["description"],
                            remediationHint=hint,
                        )
                    )

        # llm_judge handled outside this function

    passed = not any(f.severity == "blocker" for f in findings)

    return SqaReport(
        oppId=opp_id,
        runId=run_id,
        rubricVersion=rubric["version"],
        corpusSnapshotId=corpus_snapshot_id,
        passed=passed,
        findings=findings,
    )
