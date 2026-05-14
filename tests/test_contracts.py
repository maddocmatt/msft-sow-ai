"""Smoke tests for shared contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.shared.contracts import (
    SOW_SECTION_ORDER,
    BudgetaryEstimate,
    BeLineItem,
    SowDocument,
    SowSection,
)


def _all_sections() -> list[SowSection]:
    return [
        SowSection(name=name, title=name.replace("_", " ").title(), body="lorem ipsum.")
        for name in SOW_SECTION_ORDER
    ]


def test_sow_canonical_order_passes() -> None:
    doc = SowDocument(oppId="opp-1", templateProfile="ms-services-v1", sections=_all_sections())
    assert [s.name for s in doc.sections] == SOW_SECTION_ORDER


def test_sow_out_of_order_fails() -> None:
    sections = _all_sections()
    sections[0], sections[1] = sections[1], sections[0]
    with pytest.raises(ValidationError):
        SowDocument(oppId="opp-1", templateProfile="ms-services-v1", sections=sections)


def test_be_extended_and_total() -> None:
    be = BudgetaryEstimate(
        oppId="opp-1",
        lineItems=[
            BeLineItem(role="Architect", rateUsd=300.0, hours=40, phaseId="p1"),
            BeLineItem(role="Engineer", rateUsd=225.0, hours=120, phaseId="p1"),
        ],
        contingencyPct=0.10,
    )
    assert be.subtotalUsd == pytest.approx(300 * 40 + 225 * 120)
    assert be.totalUsd == pytest.approx(be.subtotalUsd * 1.10)
