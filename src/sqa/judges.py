"""Layer 2 — rubric-encoded LLM judges.

Iterates rubric rules with `detector.kind == "llm_judge"` and produces
SqaFinding objects. Currently handles two judge shapes:

1. Voice/scope-bullet classification (per-bullet labels)
2. Free-form analogy critic (handled separately in `analogy.py`); rules
   that target the analogy index are skipped here.

This keeps Layer 2 narrowly focused on inline-prompt judges that operate
on the artifact bundle alone (no retrieval).
"""

from __future__ import annotations

from typing import Any

from shared.contracts import SowDocument, SqaFinding

from .llm import LlmClient

_VOICE_SYSTEM = (
    "You are an SQA reviewer for Microsoft US Federal SOWs. "
    "You must classify each scope bullet by voice."
)

_VOICE_SCHEMA = (
    'matching this shape: {"items": [{"index": int, "label": '
    '"MS_ACTION"|"SYSTEM_CAPABILITY"|"MIXED"}]} '
    "where index is the 0-based position of the bullet in the input list."
)


def _scope_bullets(sow: SowDocument) -> list[str]:
    """Return non-empty lines from the scope section, treated as bullets."""
    for s in sow.sections:
        if s.name == "scope":
            return [ln.strip(" -*\t") for ln in s.body.splitlines() if ln.strip(" -*\t")]
    return []


def _scope_guidance_snippet(template_doc: dict[str, Any] | None) -> str:
    """Build an exemplar block from the template's scope section, if any."""
    if not template_doc:
        return ""
    sections = template_doc.get("sections") or []
    target = None
    for s in sections:
        if "scope" in (s.get("title") or "").lower():
            target = s
            break
    if not target:
        return ""
    samples: list[str] = []
    for g in target.get("guidance", []):
        if g.get("role") != "optional_language":
            continue
        text = (g.get("text") or "").strip()
        if text and len(text) <= 240:
            samples.append(f"- {text}")
        if len(samples) >= 8:
            break
    if not samples:
        return ""
    name = template_doc.get("display_name", "this template")
    return (
        "\n\nFor reference, here are exemplar scope-bullet phrasings drawn "
        f"from {name}. Microsoft commits to providing capabilities; the system "
        "is not the actor. Treat these as the canonical voice:\n"
        + "\n".join(samples)
    )


def _run_voice_judge(
    *,
    rule: dict[str, Any],
    sow: SowDocument,
    llm: LlmClient,
    template_doc: dict[str, Any] | None,
) -> list[SqaFinding]:
    bullets = _scope_bullets(sow)
    if not bullets:
        return []

    system = _VOICE_SYSTEM + _scope_guidance_snippet(template_doc)
    user = "Bullets:\n" + "\n".join(f"{i}. {b}" for i, b in enumerate(bullets))
    raw = llm.complete_json(system=system, user=user, schema_hint=_VOICE_SCHEMA)
    items = raw.get("items") or []

    findings: list[SqaFinding] = []
    for item in items:
        try:
            idx = int(item["index"])
            label = str(item["label"])
        except (KeyError, TypeError, ValueError):
            continue
        if label in ("SYSTEM_CAPABILITY", "MIXED") and 0 <= idx < len(bullets):
            findings.append(
                SqaFinding(
                    ruleId=rule["id"],
                    severity=rule["severity"],
                    artifact=rule["artifact"],
                    locator=f"scope#bullet{idx}",
                    description=rule["description"],
                    remediationHint=rule.get("remediation_hint"),
                )
            )
    return findings


def run_llm_judges(
    *,
    rubric: dict[str, Any],
    sow: SowDocument | None,
    llm: LlmClient,
    template_doc: dict[str, Any] | None = None,
) -> list[SqaFinding]:
    """Execute every rubric rule with `kind: llm_judge` that targets the bundle."""
    findings: list[SqaFinding] = []
    if sow is None:
        return findings

    for rule in rubric.get("rules", []):
        detector = rule.get("detector") or {}
        if detector.get("kind") != "llm_judge":
            continue
        spec = detector.get("spec") or {}
        # Analogy critic is dispatched by analogy.py — skip it here.
        if "index" in spec:
            continue
        if spec.get("scope_section_only"):
            findings.extend(
                _run_voice_judge(rule=rule, sow=sow, llm=llm, template_doc=template_doc)
            )
    return findings
