"""Safely add chart titles + data labels to the Power BI report.

The visual `config` blocks in report.json are JSON *strings* embedded inside the
report JSON. Hand-editing those escaped strings is error-prone, so this script
parses each inner config, injects the `objects` (title text, data-label toggles)
for the named visuals, and re-serialises with json.dumps — guaranteeing valid
escaping. Idempotent: re-running just overwrites the same title/label objects.

Run:  python powerbi/tools/enhance_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1] / "ChurnEngine" / "ChurnEngine.Report" / "report.json"

# visual name -> (title text, show data labels?)
TITLES: dict[str, tuple[str, bool]] = {
    "v009": ("Monthly Recurring Revenue (NT$) over time", False),
    "v010": ("Customers by churn-risk band (1 = safe to 10 = high risk)", True),
    "v015": ("MRR growth (NT$ per month)", False),
    "v019": ("Churn rate by customer segment", True),
    "v021": ("Cohort retention (%)  -  rows: signup month, columns: months since signup", False),
    "v023": ("Expected revenue at risk by score band (NT$/mo)", True),
    "v024": ("Customers per risk band", True),
    "v026": ("Top 200 highest-risk customers", False),
}


def literal(value: str) -> dict:
    """Wrap a string as a Power BI literal expression (single-quoted inside)."""
    return {"expr": {"Literal": {"Value": f"'{value}'"}}}


def bool_literal(value: bool) -> dict:
    return {"expr": {"Literal": {"Value": "true" if value else "false"}}}


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    touched = []

    for section in report.get("sections", []):
        for vc in section.get("visualContainers", []):
            cfg = json.loads(vc["config"])
            name = cfg.get("name")
            if name not in TITLES:
                continue
            title_text, show_labels = TITLES[name]
            sv = cfg.setdefault("singleVisual", {})
            objects = sv.setdefault("objects", {})

            objects["title"] = [{
                "properties": {
                    "show": bool_literal(True),
                    "text": literal(title_text),
                    "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#0F172A'"}}}}},
                }
            }]
            if show_labels:
                objects["labels"] = [{"properties": {"show": bool_literal(True)}}]

            # re-serialise the inner config compactly (matches existing style)
            vc["config"] = json.dumps(cfg, separators=(",", ":"))
            touched.append(name)

    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # sanity: file still parses
    json.loads(REPORT.read_text(encoding="utf-8"))
    print(f"Enhanced {len(touched)} visuals: {', '.join(sorted(touched))}")


if __name__ == "__main__":
    main()
