"""Extract structural metadata from MS Services templates.

Walks templates/ and emits templates/_profiles/<file>.json containing:
- For DOCX: ordered list of headings (style + text), section break count, table count,
  list of content controls / placeholders, named styles used.
- For XLSX/XLSM: sheet names, named ranges, defined-name targets, and (for XLSM)
  whether VBA project is present.
- For PPTX: slide titles, layout names, and placeholder texts per slide.
- For PDF: page count and (best-effort) outline / TOC.

These profiles become the contract drafter agents must hit. If a draft deviates
(missing heading, extra section, wrong style), the SQA Gatekeeper flags it.

Run:
    python scripts/extract_template_profiles.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
OUT_DIR = TEMPLATES_DIR / "_profiles"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "ssml": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}


@dataclass
class Heading:
    style: str
    text: str


@dataclass
class DocxProfile:
    kind: str = "docx"
    headings: list[Heading] = field(default_factory=list)
    table_count: int = 0
    section_break_count: int = 0
    placeholders: list[str] = field(default_factory=list)
    styles_used: list[str] = field(default_factory=list)


@dataclass
class XlsxProfile:
    kind: str = "xlsx"
    sheets: list[str] = field(default_factory=list)
    defined_names: list[str] = field(default_factory=list)
    has_vba: bool = False


@dataclass
class PptxSlide:
    index: int
    title: str | None
    layout: str | None
    placeholders: list[str] = field(default_factory=list)


@dataclass
class PptxProfile:
    kind: str = "pptx"
    slides: list[PptxSlide] = field(default_factory=list)


@dataclass
class PdfProfile:
    kind: str = "pdf"
    page_count: int = 0


def _read_zip_xml(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    if name not in zf.namelist():
        return None
    return ET.fromstring(zf.read(name))  # noqa: S314 - trusted local Office file


def profile_docx(path: Path) -> DocxProfile:
    prof = DocxProfile()
    with zipfile.ZipFile(path) as zf:
        doc = _read_zip_xml(zf, "word/document.xml")
        if doc is None:
            return prof

        styles_seen: set[str] = set()
        placeholder_tokens: list[str] = []
        for p in doc.iter(f"{{{NS['w']}}}p"):
            style_el = p.find(f"{{{NS['w']}}}pPr/{{{NS['w']}}}pStyle")
            style = style_el.attrib.get(f"{{{NS['w']}}}val") if style_el is not None else ""
            text = "".join(t.text or "" for t in p.iter(f"{{{NS['w']}}}t")).strip()
            if style:
                styles_seen.add(style)
            if style and (style.lower().startswith("heading") or style.lower() in {"title", "subtitle"}):
                if text:
                    prof.headings.append(Heading(style=style, text=text))
            for token in ("[insert", "TBD", "TODO", "<<", "{{"):
                if token.lower() in text.lower():
                    placeholder_tokens.append(text[:160])
                    break

        prof.table_count = sum(1 for _ in doc.iter(f"{{{NS['w']}}}tbl"))
        prof.section_break_count = sum(1 for _ in doc.iter(f"{{{NS['w']}}}sectPr"))
        prof.styles_used = sorted(styles_seen)
        # de-dupe placeholders, keep order
        seen: set[str] = set()
        for tok in placeholder_tokens:
            if tok not in seen:
                seen.add(tok)
                prof.placeholders.append(tok)
    return prof


def profile_xlsx(path: Path) -> XlsxProfile:
    prof = XlsxProfile(kind="xlsm" if path.suffix.lower() == ".xlsm" else "xlsx")
    with zipfile.ZipFile(path) as zf:
        wb = _read_zip_xml(zf, "xl/workbook.xml")
        if wb is not None:
            for s in wb.iter(f"{{{NS['ssml']}}}sheet"):
                name = s.attrib.get("name")
                if name:
                    prof.sheets.append(name)
            for dn in wb.iter(f"{{{NS['ssml']}}}definedName"):
                n = dn.attrib.get("name")
                if n:
                    prof.defined_names.append(n)
        prof.has_vba = "xl/vbaProject.bin" in zf.namelist()
    return prof


def profile_pptx(path: Path) -> PptxProfile:
    prof = PptxProfile()
    with zipfile.ZipFile(path) as zf:
        slide_names = sorted(n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
        for idx, slide_name in enumerate(slide_names, start=1):
            xml = _read_zip_xml(zf, slide_name)
            if xml is None:
                continue
            texts: list[str] = []
            title: str | None = None
            for sp in xml.iter(f"{{{NS['p']}}}sp"):
                ph = sp.find(f".//{{{NS['p']}}}ph")
                placeholder_type = ph.attrib.get("type") if ph is not None else None
                paragraphs = ["".join(t.text or "" for t in para.iter(f"{{{NS['a']}}}t")).strip()
                              for para in sp.iter(f"{{{NS['a']}}}p")]
                joined = " | ".join(p for p in paragraphs if p).strip()
                if not joined:
                    continue
                if placeholder_type in {"title", "ctrTitle"} and title is None:
                    title = joined
                else:
                    texts.append(joined)
            prof.slides.append(PptxSlide(index=idx, title=title, layout=None, placeholders=texts[:6]))
    return prof


def profile_pdf(path: Path) -> PdfProfile:
    # Lightweight: count "/Type /Page" occurrences without depending on a PDF lib.
    data = path.read_bytes()
    # crude but acceptable for inventory
    count = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
    return PdfProfile(page_count=max(count, 0))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, object]] = []

    for path in sorted(TEMPLATES_DIR.rglob("*")):
        if not path.is_file() or path.name.startswith("~$") or path.parent == OUT_DIR:
            continue
        suffix = path.suffix.lower()
        try:
            if suffix == ".docx":
                prof: object = profile_docx(path)
            elif suffix in {".xlsx", ".xlsm"}:
                prof = profile_xlsx(path)
            elif suffix == ".pptx":
                prof = profile_pptx(path)
            elif suffix == ".pdf":
                prof = profile_pdf(path)
            else:
                continue
        except (zipfile.BadZipFile, ET.ParseError, OSError) as exc:
            print(f"SKIP {path.name}: {exc}", file=sys.stderr)
            continue

        rel = path.relative_to(TEMPLATES_DIR)
        out_name = rel.as_posix().replace("/", "__") + ".json"
        out_path = OUT_DIR / out_name
        out_path.write_text(json.dumps(asdict(prof) if hasattr(prof, "__dataclass_fields__") else prof, indent=2, default=str))
        summary.append({"template": rel.as_posix(), "profile": out_path.relative_to(ROOT).as_posix(), "kind": getattr(prof, "kind", "?")})
        print(f"OK   {rel.as_posix()}  ->  {out_path.relative_to(ROOT).as_posix()}")

    (OUT_DIR / "_index.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {len(summary)} profiles to {OUT_DIR.relative_to(ROOT).as_posix()}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
