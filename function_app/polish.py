"""Section polish — rewrites architect prose to comply with SOW voice + rubric.

Returns the rewritten text plus a per-change rationale so the UI can render
a side-by-side diff with the WHY behind each edit.

The LLM does the rewriting; this module assembles the prompt and parses the
strict-JSON response. Falls back to a structured no-op when no LLM is wired
(the StubLlm path) so the UI surface still functions in dev.
"""

from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# function_app/ ships sqa/ + shared/ as siblings; add self to path for direct import
sys.path.insert(0, str(Path(__file__).parent))

import templates_loader  # noqa: E402
from sqa.llm import LlmClient, from_env  # noqa: E402

_RUBRIC_PATH = Path(__file__).parent / "rubrics" / "v1.yaml"


@lru_cache(maxsize=1)
def _rubric_hints() -> str:
    """Build a concise hint block from the live rubric YAML.

    Pulls the actual banned-token regexes and canonical verb list so the polish
    prompt stays in lockstep with the deterministic rubric — no hand-maintained
    duplicate to drift out of sync.
    """
    try:
        rubric = yaml.safe_load(_RUBRIC_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return _FALLBACK_HINTS

    banned_terms: set[str] = set()
    canonical_verbs: list[str] = []
    out_of_scope_phrase: str | None = None
    scope_openings: list[str] = []

    for rule in rubric.get("rules", []):
        rid = rule.get("id", "")
        det = rule.get("detector", {}) or {}
        spec = det.get("spec", {}) or {}
        if rid.startswith("BANNED-") and det.get("kind") == "regex":
            for term in _terms_from_regex(spec.get("pattern", "")):
                banned_terms.add(term)
        if rid == "VOICE-CANONICAL-VERBS-001":
            canonical_verbs = list(spec.get("canonical_verbs", []))
        if rid == "OUT-OF-SCOPE-OPENING-001":
            for p in spec.get("any_of", []) or []:
                # Strip flag markers and \b for human reading
                cleaned = re.sub(r"\(\?i\)|\\b", "", p).strip()
                out_of_scope_phrase = cleaned
                break
        if rid == "SCOPE-OPENING-001":
            for p in spec.get("any_of", []) or []:
                cleaned = re.sub(r"\(\?i\)|\\b|[\\\\()]", "", p).strip()
                if cleaned and len(cleaned) < 120:
                    scope_openings.append(cleaned)

    parts: list[str] = []
    if banned_terms:
        parts.append(
            "Banned tokens (rewrite or remove every occurrence):\n  "
            + ", ".join(sorted(banned_terms))
        )
    parts.append(
        "Banned hedges (rewrite to deterministic Microsoft-as-actor language):\n  "
        "may, might, should, could, possibly, potentially, generally, typically, "
        "where applicable, as appropriate, when feasible"
    )
    if canonical_verbs:
        parts.append(
            "Canonical verbs for scope/approach (prefer these):\n  "
            + ", ".join(canonical_verbs)
        )
    parts.append(
        "Voice rule: scope bullets describe what MICROSOFT does, not what the "
        "delivered system does. Use 'Microsoft will <verb> ...' not 'The system "
        "will <verb> ...'."
    )
    if out_of_scope_phrase:
        parts.append(
            "Out-of-scope sections must include the canonical disclaimer:\n  "
            + out_of_scope_phrase
        )
    if scope_openings:
        parts.append(
            "Scope sections should open with one of these canonical framings:\n  - "
            + "\n  - ".join(scope_openings[:3])
        )
    parts.append(
        "Assumptions must each declare an owner (customer | vendor | joint)."
    )
    return "\n\n".join(parts)


def _terms_from_regex(pattern: str) -> list[str]:
    """Best-effort extraction of human-readable terms from a regex banned-token pattern."""
    if not pattern:
        return []
    # Pull alternation groups like (tbd|to be determined) or (insert|enter|...)
    terms: list[str] = []
    for grp in re.findall(r"\(([^()|]+(?:\|[^()|]+)+)\)", pattern):
        for t in grp.split("|"):
            t = t.strip()
            if 1 <= len(t) <= 40 and not any(ch in t for ch in "\\[]^$?+*{}"):
                terms.append(t)
    return terms


_FALLBACK_HINTS = (
    "Banned hedges: may, might, should, could, possibly, potentially, "
    "generally, typically, where applicable.\n"
    "Use 'Microsoft will <verb> ...' with verbs: design, review, create, "
    "perform, deploy, deliver, document, assess, build."
)


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
        "Federal Services. You aggressively rewrite architect prose to strictly "
        "comply with the Microsoft Federal SOW voice and template guidance.\n\n"
        f"{_rubric_hints()}\n\n"
        "TRANSFORMATIONS YOU MUST APPLY (every occurrence):\n"
        "A. Replace passive/abstract sentence subjects with 'Microsoft'.\n"
        "   - 'This engagement focuses on X' -> 'Microsoft will <verb> X'.\n"
        "   - 'The objective of this engagement is to support Y' -> "
        "'Microsoft will <verb> Y' (use a canonical verb, e.g. assist, deliver, "
        "design).\n"
        "   - 'The system will X' -> 'Microsoft will X' (scope describes what "
        "Microsoft does, not what the delivered system does).\n"
        "B. Convert noun-phrase scope/deliverable bullets to active "
        "'Microsoft will <verb> ...' sentences. Examples:\n"
        "   - 'Decomposition and hardening of the pipeline ...' -> "
        "'Microsoft will decompose and harden the pipeline ...'.\n"
        "   - 'Systematic generation quality assurance through best-of-N ...' -> "
        "'Microsoft will perform generation quality assurance through best-of-N "
        "...'.\n"
        "   - 'Infrastructure modernization including VNet integration ...' -> "
        "'Microsoft will modernize infrastructure, including VNet integration "
        "...'.\n"
        "C. Remove banned hedges (may, might, should, could, possibly, "
        "potentially, generally, typically, where applicable, as appropriate).\n"
        "D. Replace banned tokens (TBD, whisper number, N-1, L0, [insert ...]) "
        "with concrete commitments or clear bracketed placeholders.\n"
        "E. Remove any leftover template instruction text or unfilled "
        "placeholders. If a placeholder cannot be replaced from context, leave "
        "a clear marker like [CUSTOMER NAME] for the architect to fill.\n\n"
        "INTENT PRESERVATION:\n"
        "- Do NOT add new commitments, deliverables, numbers, dates, prices, or "
        "roles that are not present in the draft.\n"
        "- Preserve all technical specifics (acronyms, metric thresholds like "
        "'>=95%', technology names, agency names).\n"
        "- Preserve bullet structure: bullets stay bullets, paragraphs stay "
        "paragraphs.\n\n"
        "CHANGE LOG REQUIREMENTS:\n"
        "- For EVERY substantive edit, emit one change record with the EXACT "
        "before substring (must appear verbatim in the draft) and the after "
        "substring.\n"
        "- The 'rule' field must be ONE of: VOICE-MS-ACTION, "
        "VOICE-CANONICAL-VERB, BANNED-HEDGE, BANNED-TOKEN, PLACEHOLDER, "
        "REMOVED-INSTRUCTION, BULLET-TO-SENTENCE, PASSIVE-TO-ACTIVE.\n"
        "- The 'why' field is ONE sentence in plain English.\n"
        "- If you genuinely cannot improve the draft, return it unchanged with "
        "an empty changes list AND set summary to start with 'No edits: ' "
        "followed by your reason. Be honest — most architect drafts have at "
        "least one passive-subject or noun-phrase bullet to rewrite.\n"
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
    import time

    t0 = time.perf_counter()
    phases: list[dict[str, Any]] = []

    def _mark(label: str) -> None:
        phases.append({"name": label, "ms": int((time.perf_counter() - t0) * 1000)})

    body = body or ""
    if not body.strip():
        _mark("empty input — skipped")
        return {
            "rewritten": "",
            "summary": "Empty input — nothing to polish.",
            "changes": [],
            "model": "noop",
            "phases": phases,
        }

    _mark("loading rubric + template guidance")
    client = llm or from_env()
    system, user = _build_prompt(
        body=body,
        template_id=template_id,
        section_title=section_title,
        subheading=subheading,
    )
    _mark("prompt assembled")
    schema_hint = (
        '{ "rewritten": string, "summary": string, '
        '"changes": [{"before": string, "after": string, "rule": string, "why": string}] }'
    )
    deployment = os.environ.get("SOWAI_LLM_DEPLOYMENT", "unknown")
    _mark(f"calling {deployment} (first pass)")
    try:
        result = client.complete_json(system=system, user=user, schema_hint=schema_hint)
    except Exception as exc:  # noqa: BLE001 — surface failure to caller
        _mark(f"first-pass error: {type(exc).__name__}")
        return {
            "rewritten": body,
            "summary": f"Polish failed: {type(exc).__name__}: {exc}",
            "changes": [],
            "error": str(exc),
            "model": deployment,
            "phases": phases,
        }
    _mark("first pass complete")

    if result.get("_stub"):
        return {
            "rewritten": body,
            "summary": "LLM stub — no real polish performed (set SOWAI_LLM_MODE=azure).",
            "changes": [],
            "model": "stub",
            "phases": phases,
        }

    rewritten = (result.get("rewritten") or body).strip()
    raw_changes = result.get("changes") or []

    # Force-rewrite pass: model returned identical text but the input clearly has
    # SOW-voice violations (passive subjects, noun-phrase bullets, hedges, banned
    # tokens). Re-prompt with stronger instructions before accepting "no changes".
    if (
        _normalize(rewritten) == _normalize(body)
        and not raw_changes
        and _has_voice_violations(body)
    ):
        _mark("first pass returned no edits — heuristic detected violations, retrying")
        retry_system = system + (
            "\n\nIMPORTANT — you returned an identical draft on the first pass. "
            "The draft contains at least one of: passive sentence subject "
            "('This engagement…', 'The objective is to support…'), noun-phrase "
            "scope/deliverable bullet (starts with a gerund or abstract noun "
            "instead of 'Microsoft will <verb>'), or a banned hedge. Apply the "
            "transformations in section A and B above to EVERY occurrence. Return "
            "the rewritten text plus one change record per substantive edit."
        )
        try:
            _mark(f"calling {deployment} (retry pass)")
            result2 = client.complete_json(
                system=retry_system, user=user, schema_hint=schema_hint
            )
            _mark("retry pass complete")
            r2 = (result2.get("rewritten") or "").strip()
            c2 = result2.get("changes") or []
            if r2 and (_normalize(r2) != _normalize(body) or c2):
                rewritten = r2
                raw_changes = c2
                # Annotate summary so the UI can surface the retry happened
                summary_extra = " (retry)"
                result["summary"] = (
                    (result2.get("summary") or "").strip() + summary_extra
                )
        except Exception as exc:  # noqa: BLE001 — keep first-pass result on retry failure
            _mark(f"retry pass error: {type(exc).__name__}")
    else:
        _mark("normalizing changes")

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

    _mark(f"done — {len(changes)} edit(s)")
    return {
        "rewritten": rewritten,
        "summary": (result.get("summary") or "").strip(),
        "changes": changes,
        "model": os.environ.get("SOWAI_LLM_DEPLOYMENT", "unknown"),
        "phases": phases,
    }


def _normalize(s: str) -> str:
    """Whitespace-normalize for equality comparison."""
    return re.sub(r"\s+", " ", s).strip().lower()


_PASSIVE_SUBJECTS = (
    "this engagement",
    "the objective of this engagement",
    "the system will",
    "the platform will",
    "the project focuses",
    "this project focuses",
    "this section outlines",
)
_HEDGES = (
    "may ",
    "might ",
    "should ",
    "could ",
    "possibly",
    "potentially",
    "generally",
    "typically",
    "where applicable",
    "as appropriate",
)


def _has_voice_violations(text: str) -> bool:
    """Heuristic: detect obvious SOW-voice issues that warrant a forced rewrite."""
    low = text.lower()
    if any(p in low for p in _PASSIVE_SUBJECTS):
        return True
    if any(h in low for h in _HEDGES):
        return True
    # Bullet lines that begin with a noun-phrase / gerund instead of "Microsoft will"
    bullet_lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip().startswith(("•", "-", "*", "·"))
    ]
    nounish = 0
    for ln in bullet_lines:
        # Strip the bullet glyph + whitespace
        body_part = re.sub(r"^[•\-\*·]+\s*", "", ln).strip()
        if not body_part:
            continue
        first = body_part.split()[0].lower().rstrip(",.;:")
        if first.startswith("microsoft"):
            continue
        # Gerunds (-tion, -ing, -ment, -ness) or single noun starts
        if first.endswith(("tion", "ing", "ment", "ness", "ity", "ization")):
            nounish += 1
    if nounish >= 2:
        return True
    return False
