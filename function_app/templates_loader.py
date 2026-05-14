"""Template registry + per-template guidance loader.

The deployment package contains:

    function_app/templates/_profiles/registry.yaml
    function_app/templates/<id>/template.json
    function_app/templates/<id>/guidance.json

This module exposes:

  list_templates()            -> [{id, engagement_type, display_name, ...}, ...]
  load_template(template_id)  -> dict from template.json (UI-friendly section tree)
  load_guidance(template_id)  -> dict from guidance.json (raw role-tagged items)
  guidance_for_section(...)   -> per-section guidance items (used by judges)

All loaders are cached in-process for the warm function instance.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).parent / "templates"
_REGISTRY = _ROOT / "_profiles" / "registry.yaml"


class TemplateNotFound(KeyError):
    """Raised when a template_id is not present in the registry."""


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    if not _REGISTRY.exists():
        return {"templates": [], "color_roles": {}}
    data = yaml.safe_load(_REGISTRY.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"templates": [], "color_roles": {}}


def list_templates() -> list[dict[str, Any]]:
    """Public list of templates for the UI selector."""
    items: list[dict[str, Any]] = []
    for entry in _registry().get("templates", []):
        items.append(
            {
                "id": entry.get("id"),
                "engagement_type": entry.get("engagement_type"),
                "display_name": entry.get("display_name"),
                "description": entry.get("description"),
            }
        )
    return items


@lru_cache(maxsize=64)
def load_template(template_id: str) -> dict[str, Any]:
    path = _ROOT / template_id / "template.json"
    if not path.exists():
        raise TemplateNotFound(template_id)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


@lru_cache(maxsize=64)
def load_guidance(template_id: str) -> dict[str, Any]:
    path = _ROOT / template_id / "guidance.json"
    if not path.exists():
        raise TemplateNotFound(template_id)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def guidance_for_section(template_id: str, section_match: str) -> list[dict[str, Any]]:
    """Return guidance items for a section whose title contains `section_match`.

    Case-insensitive substring match. Returns the first matching section's items.
    """
    try:
        tmpl = load_template(template_id)
    except TemplateNotFound:
        return []
    needle = section_match.lower()
    for s in tmpl.get("sections", []):
        if needle in (s.get("title") or "").lower():
            return list(s.get("guidance", []))
    return []
