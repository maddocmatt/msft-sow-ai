"""Mine SOW/collateral templates for the LANGUAGE patterns SQA expects.

We don't care about process here. We care about: what verbs, sentence shapes,
section openings, assumption phrasings, and forbidden hedge words appear in
the templates that are *already* SQA-blessed.

Output: templates/_profiles/_language.json
{
  "section_openings":   {section_name: [opening_sentences...]},
  "scope_verbs":        {verb: count}     # action verbs in scope/approach sections
  "deliverable_phrases":[phrase, ...]     # patterns under "Deliverables" sub-headings
  "assumption_phrases": [phrase, ...]     # patterns under assumptions sections
  "responsibility_phrases": [phrase, ...] # patterns under responsibilities sections
  "placeholder_tokens": {token: count}    # <Customer Name>, <Date>, etc. — what the
                                          # drafter is REQUIRED to fill
  "banned_hedges":      {hedge: count}    # weasel words that DO appear (drafters
                                          # should AVOID adding any new ones)
}
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
OUT = TEMPLATES_DIR / "_profiles" / "_language.json"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}

# Sections we care about, matched case-insensitively against heading text.
SCOPE_HEADINGS = (
    "scope", "areas in scope", "objectives", "delivery approach", "approach",
    "general project scope", "envision phase", "plan", "build", "stabilize", "deploy",
)
ASSUMPTION_HEADINGS = ("assumption", "project assumption")
DELIVERABLE_HEADINGS = ("deliverable",)
RESPONSIBILITY_HEADINGS = ("responsibilit", "microsoft", "customer name")

# Strong action verbs that are good in scope/approach prose.
ACTION_VERBS = {
    "design", "build", "implement", "deploy", "develop", "deliver", "configure",
    "integrate", "migrate", "assess", "document", "review", "validate", "test",
    "establish", "produce", "perform", "create", "enable", "operationalize",
    "instrument", "stand up", "transition", "knowledge transfer",
}

# Hedges/weasel words. If they exist in templates we note them; drafters MUST NOT add new ones.
HEDGES = {
    "may", "might", "could", "should", "approximately", "roughly", "around",
    "as needed", "best effort", "best-effort", "tbd", "to be determined",
    "etc.", "and so on", "various", "some", "potentially", "likely", "ideally",
}

PLACEHOLDER_RE = re.compile(r"<[^>]{1,60}>|\[[^\]]{1,60}\]|\{\{[^}]{1,60}\}\}")


def _para_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.iter(f"{{{W}}}t")).strip()


def _para_style(p: ET.Element) -> str:
    s = p.find(f"{{{W}}}pPr/{{{W}}}pStyle")
    return (s.attrib.get(f"{{{W}}}val") if s is not None else "") or ""


def _is_heading(style: str) -> int:
    """Return heading level 1..9 or 0 if not a heading."""
    if not style:
        return 0
    m = re.search(r"(?i)heading\s*(\d)", style)
    return int(m.group(1)) if m else 0


def _classify_heading(text: str) -> str | None:
    t = text.lower().strip("., :")
    for needle, label in [
        *((h, "scope") for h in SCOPE_HEADINGS),
        *((h, "assumption") for h in ASSUMPTION_HEADINGS),
        *((h, "deliverable") for h in DELIVERABLE_HEADINGS),
        *((h, "responsibility") for h in RESPONSIBILITY_HEADINGS),
    ]:
        if needle in t:
            return label
    return None


def _walk_paragraphs(path: Path):  # type: ignore[no-untyped-def]
    with zipfile.ZipFile(path) as zf:
        if "word/document.xml" not in zf.namelist():
            return
        doc = ET.fromstring(zf.read("word/document.xml"))  # noqa: S314
        for p in doc.iter(f"{{{W}}}p"):
            yield _para_style(p), _para_text(p)


def mine_language() -> dict[str, object]:
    section_openings: dict[str, list[str]] = defaultdict(list)
    scope_verbs: Counter[str] = Counter()
    deliverable_phrases: list[str] = []
    assumption_phrases: list[str] = []
    responsibility_phrases: list[str] = []
    placeholders: Counter[str] = Counter()
    hedges: Counter[str] = Counter()

    docx_files = sorted(p for p in TEMPLATES_DIR.rglob("*.docx") if not p.name.startswith("~$"))
    for path in docx_files:
        current_bucket: str | None = None
        first_in_bucket = True
        for style, text in _walk_paragraphs(path):
            if not text:
                continue
            level = _is_heading(style)
            if level:
                current_bucket = _classify_heading(text)
                first_in_bucket = True
                continue

            # collect placeholders + hedges everywhere
            for m in PLACEHOLDER_RE.findall(text):
                placeholders[m] += 1
            lower = text.lower()
            for h in HEDGES:
                if re.search(rf"\b{re.escape(h)}\b", lower):
                    hedges[h] += 1

            if current_bucket == "scope":
                if first_in_bucket and len(text) > 25:
                    section_openings["scope"].append(text[:240])
                    first_in_bucket = False
                for verb in ACTION_VERBS:
                    if re.search(rf"\b{re.escape(verb)}\b", lower):
                        scope_verbs[verb] += 1
            elif current_bucket == "deliverable":
                if 5 < len(text) < 200:
                    deliverable_phrases.append(text)
            elif current_bucket == "assumption":
                if 5 < len(text) < 240:
                    assumption_phrases.append(text)
            elif current_bucket == "responsibility":
                if 5 < len(text) < 240:
                    responsibility_phrases.append(text)

    # de-dupe while preserving order, keep top-N
    def _uniq(seq: list[str], n: int = 50) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for s in seq:
            if s not in seen:
                seen.add(s)
                out.append(s)
            if len(out) >= n:
                break
        return out

    return {
        "source_files": [p.name for p in docx_files],
        "section_openings": {k: _uniq(v, 20) for k, v in section_openings.items()},
        "scope_verbs": dict(scope_verbs.most_common()),
        "deliverable_phrases": _uniq(deliverable_phrases, 60),
        "assumption_phrases": _uniq(assumption_phrases, 60),
        "responsibility_phrases": _uniq(responsibility_phrases, 60),
        "placeholder_tokens": dict(placeholders.most_common()),
        "hedges_found_in_templates": dict(hedges.most_common()),
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = mine_language()
    OUT.write_text(json.dumps(data, indent=2))
    print(f"Wrote {OUT.relative_to(ROOT).as_posix()}")
    print(
        f"  scope_verbs={len(data['scope_verbs'])}  "  # type: ignore[arg-type]
        f"deliverable_phrases={len(data['deliverable_phrases'])}  "  # type: ignore[arg-type]
        f"assumption_phrases={len(data['assumption_phrases'])}  "  # type: ignore[arg-type]
        f"placeholders={len(data['placeholder_tokens'])}  "  # type: ignore[arg-type]
        f"hedges={len(data['hedges_found_in_templates'])}"  # type: ignore[arg-type]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
