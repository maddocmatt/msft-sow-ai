"""Section polish — rewrites architect prose to comply with SOW voice + rubric.

Returns the rewritten text plus a per-change rationale so the UI can render
a side-by-side diff with the WHY behind each edit.

The LLM does the rewriting; this module assembles the prompt and parses the
strict-JSON response. Falls back to a structured no-op when no LLM is wired
(the StubLlm path) so the UI surface still functions in dev.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# function_app/ ships sqa/ + shared/ as siblings; add self to path for direct import
sys.path.insert(0, str(Path(__file__).parent))

import templates_loader  # noqa: E402
from sqa.llm import LlmClient, from_env  # noqa: E402

_RUBRIC_HINTS = """
Banned hedges (rewrite to deterministic Microsoft-as-actor language):
  may, might, should, could, possibly, potentially, generally, typically, where applicable
Required voice in scope/deliverables:
  "Microsoft will <verb> ..." — verbs: deliver, produce, provide, conduct, configure, develop, document, perform, design, implement
Banned tokens:
  TBD, [TBD], [insert ...], placeholders inherited from the template (red text)
Out-of-scope sections must open with a definitive negation, not a hedge.
Assumptions need an owner (customer / vendor / joint).
"""


def _build_prompt(
    *,
    body: str,
    template_id: str | None,
    section_title: str,
    subheading: str | None,
) -> tuple[str, str]:
    """Return (system, user) prompts for the polish call."""
    guidance_block = ""
    if template_id:
        try:
            tmpl = templates_loader.load_template(template_id)
        except templates_loader.TemplateNotFound:
            tmpl = None
        if tmpl:
            # Find the matching section (substring match on title)
            needle = section_title.lower()
            match = None
            for s in tmpl.get("sections", []):
                if needle in (s.get("title") or "").lower() or (
                    s.get("title", "").lower() in needle
                ):
                    match = s
                    break
            if match:
                items = match.get("guidance", [])
                if subheading:
                    sl = subheading.lower()
                    items = [
                        g
                        for g in items
                        if sl in (g.get("subheading") or "").lower()
                    ] or items
                # Cap context size
                items = items[:25]
                lines = []
                for g in items:
                    role = g.get("role", "")
                    text = (g.get("text") or "").strip().replace("\n", " ")[:200]
                    if role == "instruction":
                        lines.append(f"- INSTRUCTION (must not appear in output): {text}")
                    elif role == "placeholder":
                        lines.append(f"- PLACEHOLDER (must be replaced or removed): {text}")
                    elif role == "optional_language":
                        lines.append(f"- SUGGESTED LANGUAGE (prefer this phrasing): {text}")
                if lines:
                    guidance_block = (
                        "\nTemplate guidance for this section:\n" + "\n".join(lines) + "\n"
                    )

    system = (
        "You are an SOW (Statement of Work) Quality Assurance editor for Microsoft "
        "Federal Services. You rewrite architect prose to strictly comply with the "
        "Microsoft Federal SOW voice and template guidance.\n\n"
        f"{_RUBRIC_HINTS}\n"
        "Rules for your output:\n"
        "1. Preserve the architect's intent. Do not add new commitments, deliverables, "
        "or numbers. Do not invent dates, prices, or roles.\n"
        "2. Tighten language. Convert passive/hedged language to active "
        "Microsoft-as-actor sentences using canonical verbs.\n"
        "3. Remove any leftover template instruction text or unfilled placeholders. "
        "If a placeholder cannot be replaced from context, leave a clear marker like "
        "[CUSTOMER NAME] for the architect to fill.\n"
        "4. For each substantive edit, emit a change record with before/after spans "
        "and a one-sentence WHY explaining which rule or guidance drove it.\n"
        "5. If the input is already clean, return it unchanged with an empty changes list.\n"
    )

    user = (
        f"Section: {section_title}"
        + (f" > {subheading}" if subheading else "")
        + f"\n{guidance_block}\nArchitect draft:\n---\n{body}\n---\n"
        "Return JSON with this shape:\n"
        "{\n"
        '  "rewritten": "<polished full section text>",\n'
        '  "summary": "<one sentence describing the overall edit>",\n'
        '  "changes": [\n'
        "    {\n"
        '      "before": "<exact substring from the draft>",\n'
        '      "after":  "<the replacement substring>",\n'
        '      "rule":   "<short rule code, e.g. VOICE-MS-ACTION, BANNED-HEDGE, '
        'PLACEHOLDER, REMOVED-INSTRUCTION>",\n'
        '      "why":    "<one sentence rationale>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Each change.before MUST be an exact substring of the original draft."
    )
    return system, user


def polish_section(
    *,
    body: str,
    template_id: str | None,
    section_title: str,
    subheading: str | None = None,
    llm: LlmClient | None = None,
) -> dict[str, Any]:
    """Run the polish pipeline. Returns a dict ready to JSON-serialize for the API."""
    body = body or ""
    if not body.strip():
        return {
            "rewritten": "",
            "summary": "Empty input — nothing to polish.",
            "changes": [],
            "model": "noop",
        }

    client = llm or from_env()
    system, user = _build_prompt(
        body=body,
        template_id=template_id,
        section_title=section_title,
        subheading=subheading,
    )
    schema_hint = (
        '{ "rewritten": string, "summary": string, '
        '"changes": [{"before": string, "after": string, "rule": string, "why": string}] }'
    )
    try:
        result = client.complete_json(system=system, user=user, schema_hint=schema_hint)
    except Exception as exc:  # noqa: BLE001 — surface failure to caller
        return {
            "rewritten": body,
            "summary": f"Polish failed: {type(exc).__name__}: {exc}",
            "changes": [],
            "error": str(exc),
            "model": os.environ.get("SOWAI_LLM_DEPLOYMENT", "unknown"),
        }

    if result.get("_stub"):
        return {
            "rewritten": body,
            "summary": "LLM stub — no real polish performed (set SOWAI_LLM_MODE=azure).",
            "changes": [],
            "model": "stub",
        }

    rewritten = (result.get("rewritten") or body).strip()
    raw_changes = result.get("changes") or []
    changes: list[dict[str, Any]] = []
    for c in raw_changes:
        if not isinstance(c, dict):
            continue
        before = (c.get("before") or "").strip()
        after = (c.get("after") or "").strip()
        if not before and not after:
            continue
        changes.append(
            {
                "before": before,
                "after": after,
                "rule": (c.get("rule") or "POLISH").strip(),
                "why": (c.get("why") or "").strip(),
            }
        )

    return {
        "rewritten": rewritten,
        "summary": (result.get("summary") or "").strip(),
        "changes": changes,
        "model": os.environ.get("SOWAI_LLM_DEPLOYMENT", "unknown"),
    }
