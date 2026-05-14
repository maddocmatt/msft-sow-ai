"""Extract template authoring guidance (pink/green/red) from each SOW template.

Template color convention (official):
  Italic Pink  -> instruction       (must be deleted before sending)
  Bold Green   -> optional_language (keep / edit / remove and un-bold)
  Red          -> placeholder       (must be filled in)

Walks every paragraph in document order, tracks the current heading path
(Heading 1 > Heading 2 > Heading 3 ...), and emits two artifacts per template:

  templates/<id>/guidance.json  - raw flat list of color-coded guidance items
  templates/<id>/template.json  - UI-friendly section tree with per-section
                                  guidance grouped by sub-heading

Reads the registry at templates/_profiles/registry.yaml.

Usage:
  python scripts/extract_template_guidance.py
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import docx
import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
SOW_DIR = TEMPLATES_DIR / "sow"
REGISTRY = TEMPLATES_DIR / "_profiles" / "registry.yaml"


@dataclass
class GuidanceItem:
    role: str  # 'instruction' | 'optional_language' | 'placeholder'
    heading_path: list[str]
    heading_level: int
    paragraph_index: int
    style: str
    text: str
    color: str
    enclosing_text: str


def _is_heading(style_name: str) -> int | None:
    """Return heading level (1-9) or None."""
    if not style_name:
        return None
    s = style_name.strip()
    for prefix in ("Heading ", "heading "):
        if s.startswith(prefix):
            tail = s[len(prefix) :].strip().split(" ")[0]
            try:
                return int(tail)
            except ValueError:
                return None
    if s in {"Title"}:
        return 0
    return None


def _classify_runs(para: Any, color_to_role: dict[str, str]) -> list[tuple[str, str, str]]:
    """Return (text, color, role) for runs whose color maps to a known role."""
    out: list[tuple[str, str, str]] = []
    for run in para.runs:
        c = run.font.color
        if c is None or c.rgb is None:
            continue
        hx = str(c.rgb).upper()
        role = color_to_role.get(hx)
        if role is None:
            continue
        txt = (run.text or "").strip()
        if txt:
            out.append((txt, hx, role))
    return out


def _emit(
    runs: list[tuple[str, str, str]],
    *,
    headings: list[str],
    paragraph_index: int,
    style: str,
    enclosing: str,
) -> list[GuidanceItem]:
    """Group adjacent runs of the same role into one GuidanceItem."""
    items: list[GuidanceItem] = []
    if not runs:
        return items
    cur_role = runs[0][2]
    cur_color = runs[0][1]
    cur_text: list[str] = [runs[0][0]]
    for txt, hx, role in runs[1:]:
        if role == cur_role:
            cur_text.append(txt)
        else:
            items.append(
                GuidanceItem(
                    role=cur_role,
                    heading_path=[h for h in headings if h],
                    heading_level=len(headings),
                    paragraph_index=paragraph_index,
                    style=style,
                    text=" ".join(cur_text).strip(),
                    color=cur_color,
                    enclosing_text=enclosing,
                )
            )
            cur_role = role
            cur_color = hx
            cur_text = [txt]
    items.append(
        GuidanceItem(
            role=cur_role,
            heading_path=[h for h in headings if h],
            heading_level=len(headings),
            paragraph_index=paragraph_index,
            style=style,
            text=" ".join(cur_text).strip(),
            color=cur_color,
            enclosing_text=enclosing,
        )
    )
    return items


def _walk(doc: Any, color_to_role: dict[str, str]) -> tuple[list[GuidanceItem], list[str]]:
    """Walk body in document order so tables inherit the current heading.

    Returns (guidance items, ordered list of unique level-1 headings).
    """
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    headings: list[str] = []
    items: list[GuidanceItem] = []
    top_level: list[str] = []
    body = doc.element.body
    para_idx = 0
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            style_name = para.style.name if para.style else ""
            text = (para.text or "").strip()
            level = _is_heading(style_name)
            if level is not None and text:
                while len(headings) >= level:
                    headings.pop()
                while len(headings) < level - 1:
                    headings.append("")
                headings.append(text)
                if level == 1 and text not in top_level:
                    top_level.append(text)
                para_idx += 1
                continue
            if text:
                runs = _classify_runs(para, color_to_role)
                items.extend(
                    _emit(
                        runs,
                        headings=headings,
                        paragraph_index=para_idx,
                        style=style_name,
                        enclosing=text,
                    )
                )
            para_idx += 1
        elif child.tag == qn("w:tbl"):
            tbl = Table(child, doc)
            for row in tbl.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        runs = _classify_runs(para, color_to_role)
                        items.extend(
                            _emit(
                                runs,
                                headings=headings,
                                paragraph_index=para_idx,
                                style="TableCell",
                                enclosing=(para.text or "").strip(),
                            )
                        )
    return items, top_level


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.strip().lower()).strip("-")[:64] or "section"


def _build_template_doc(
    *,
    entry: dict[str, Any],
    items: list[GuidanceItem],
    top_level: list[str],
) -> dict[str, Any]:
    """Group guidance by top-level heading into a section list for the UI."""
    sections: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for title in top_level:
        slug = _slugify(title)
        # disambiguate if duplicate
        base = slug
        i = 2
        while slug in seen_slugs:
            slug = f"{base}-{i}"
            i += 1
        seen_slugs.add(slug)
        section_items = [it for it in items if it.heading_path[:1] == [title]]
        sections.append(
            {
                "name": slug,
                "title": title,
                "guidance_count": len(section_items),
                "guidance": [
                    {
                        "role": it.role,
                        "subheading": " > ".join(it.heading_path[1:])
                        if len(it.heading_path) > 1
                        else None,
                        "text": it.text,
                        "enclosing_text": it.enclosing_text,
                    }
                    for it in section_items
                ],
            }
        )
    # Also collect orphans (table cells, items with no top-level heading)
    orphan_items = [
        it for it in items if not it.heading_path or it.heading_path[0] not in top_level
    ]
    if orphan_items:
        sections.append(
            {
                "name": "_unclassified",
                "title": "Unclassified",
                "guidance_count": len(orphan_items),
                "guidance": [
                    {
                        "role": it.role,
                        "subheading": " > ".join(it.heading_path) if it.heading_path else None,
                        "text": it.text,
                        "enclosing_text": it.enclosing_text,
                    }
                    for it in orphan_items
                ],
            }
        )
    return {
        "id": entry["id"],
        "engagement_type": entry["engagement_type"],
        "display_name": entry["display_name"],
        "source_file": entry["file"],
        "section_count": len([s for s in sections if s["name"] != "_unclassified"]),
        "sections": sections,
    }


def main() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    color_to_role: dict[str, str] = {}
    for role, hexes in registry["color_roles"].items():
        for hx in hexes:
            color_to_role[hx.upper()] = role
    summary: list[dict[str, Any]] = []
    for entry in registry["templates"]:
        tmpl_id = entry["id"]
        path = SOW_DIR / entry["file"]
        if not path.exists():
            print(f"  ! missing: {path}")
            continue
        doc = docx.Document(str(path))
        items, top_level = _walk(doc, color_to_role)
        out_dir = TEMPLATES_DIR / tmpl_id
        out_dir.mkdir(parents=True, exist_ok=True)
        by_role: dict[str, int] = {}
        for it in items:
            by_role[it.role] = by_role.get(it.role, 0) + 1
        guidance_doc = {
            "template_id": tmpl_id,
            "engagement_type": entry["engagement_type"],
            "display_name": entry["display_name"],
            "source_file": entry["file"],
            "color_roles": registry["color_roles"],
            "counts_by_role": by_role,
            "guidance_count": len(items),
            "guidance": [asdict(i) for i in items],
        }
        (out_dir / "guidance.json").write_text(
            json.dumps(guidance_doc, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        template_doc = _build_template_doc(entry=entry, items=items, top_level=top_level)
        (out_dir / "template.json").write_text(
            json.dumps(template_doc, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary.append(
            {
                "template": tmpl_id,
                "items": len(items),
                "sections": template_doc["section_count"],
                "roles": by_role,
            }
        )
        print(
            f"  - {tmpl_id}: sections={template_doc['section_count']:2d}  items={len(items):3d}  "
            f"(instr={by_role.get('instruction', 0)}, "
            f"opt={by_role.get('optional_language', 0)}, "
            f"slot={by_role.get('placeholder', 0)})"
        )
    print("\nSummary:")
    for s in summary:
        print(
            f"  {s['template']:24} sections={s['sections']:2d}  items={s['items']:3d}  {s['roles']}"
        )


if __name__ == "__main__":
    main()
