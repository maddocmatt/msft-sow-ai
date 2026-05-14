"""Dump every colored paragraph in a docx with full text + heading path."""

from __future__ import annotations

import sys

import docx


def _is_heading(style_name: str) -> int | None:
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
    return None


def main(path: str, only_color: str | None = None) -> None:
    doc = docx.Document(path)
    headings: list[str] = []
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""
        text = (para.text or "").strip()
        level = _is_heading(style_name)
        if level is not None and text:
            while len(headings) >= level:
                headings.pop()
            while len(headings) < level - 1:
                headings.append("")
            headings.append(text)
            continue
        if not text:
            continue
        # Find dominant color
        colors: dict[str, int] = {}
        for run in para.runs:
            c = run.font.color
            if c is None or c.rgb is None:
                continue
            hx = str(c.rgb).upper()
            colors[hx] = colors.get(hx, 0) + len(run.text or "")
        if not colors:
            continue
        dominant = max(colors, key=lambda k: colors[k])
        if only_color and dominant != only_color.upper():
            continue
        path_str = " > ".join(h for h in headings if h)
        print(f"[{dominant}] {path_str[:70]}")
        print(f"    {text[:200]}")
        print()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
