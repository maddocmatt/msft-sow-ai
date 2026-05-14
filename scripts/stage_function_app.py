"""Stage the function_app/ folder for deployment.

Copies the vendored Python packages (shared, sqa) and the rubric file
from the repo root into function_app/ so `func ... publish` ships a
self-contained payload.

Run before `func azure functionapp publish ...`.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DST = ROOT / "function_app"

PACKAGES = ["shared", "sqa"]


def main() -> int:
    if not DST.exists():
        print(f"missing {DST}", file=sys.stderr)
        return 1

    for pkg in PACKAGES:
        src_pkg = SRC / pkg
        dst_pkg = DST / pkg
        if dst_pkg.exists():
            shutil.rmtree(dst_pkg)
        shutil.copytree(src_pkg, dst_pkg, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"staged {src_pkg} -> {dst_pkg}")

    rubric_src = ROOT / "sqa" / "rubrics" / "v1.yaml"
    rubric_dst = DST / "rubrics" / "v1.yaml"
    rubric_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rubric_src, rubric_dst)
    print(f"staged {rubric_src} -> {rubric_dst}")

    # Stage template registry + per-template guidance/template JSON files
    import yaml

    templates_src = ROOT / "templates"
    templates_dst = DST / "templates"
    if templates_dst.exists():
        shutil.rmtree(templates_dst)
    templates_dst.mkdir(parents=True, exist_ok=True)
    registry_src = templates_src / "_profiles" / "registry.yaml"
    registry_dst = templates_dst / "_profiles" / "registry.yaml"
    registry_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(registry_src, registry_dst)
    print(f"staged {registry_src} -> {registry_dst}")
    language_src = templates_src / "_profiles" / "_language.json"
    if language_src.exists():
        language_dst = templates_dst / "_profiles" / "_language.json"
        shutil.copy2(language_src, language_dst)
        print(f"staged {language_src} -> {language_dst}")
    registry = yaml.safe_load(registry_src.read_text(encoding="utf-8"))
    for entry in registry.get("templates", []):
        tmpl_id = entry["id"]
        src_dir = templates_src / tmpl_id
        if not src_dir.exists():
            continue
        tmpl_dst = templates_dst / tmpl_id
        tmpl_dst.mkdir(parents=True, exist_ok=True)
        for fname in ("template.json", "guidance.json"):
            src = src_dir / fname
            if src.exists():
                shutil.copy2(src, tmpl_dst / fname)
        print(f"staged {src_dir} -> {tmpl_dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
