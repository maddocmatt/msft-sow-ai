"""Quick CLI to peek at extracted guidance: usage: python show_guidance.py msd-v13 [N]"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    tmpl_id = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    path = ROOT / "templates" / tmpl_id / "guidance.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"{tmpl_id}: {data['guidance_count']} items, roles={data['counts_by_role']}")
    for g in data["guidance"][:n]:
        head = " > ".join(g["heading_path"][-2:]) if g["heading_path"] else "(no heading)"
        print(f"\n  [{g['role']}] {head}")
        print(f"    {g['text'][:200]}")


if __name__ == "__main__":
    main()
