"""Probe the heading/style structure of a docx so we can map sections."""

from __future__ import annotations

import sys

import docx


def main(path: str) -> None:
    doc = docx.Document(path)
    for i, para in enumerate(doc.paragraphs):
        style = para.style.name if para.style else ""
        text = (para.text or "").strip()
        if not text:
            continue
        if style.startswith("Heading") or style in {"Title", "Subtitle"}:
            print(f"[{i:4}] [{style}] {text[:120]}")
        elif text and text[0].isdigit() and "." in text[:6]:
            print(f"[{i:4}] [num?]      {text[:120]}")


if __name__ == "__main__":
    main(sys.argv[1])
