"""Rebuild page 1 (Executive Summary) of report.json in the "National Summary"
KPI-template style: light-gray canvas, white rounded tiles, centered gray titles,
big numbers with delta accents, amber KPI mini-charts, green gauges, a wide trend
chart, an Insights panel, and green bottom column charts.

Only the first section (s1exec) is replaced; pages 2-4 are left untouched.
All configs are built as Python dicts and serialised with json.dumps, so the
embedded config strings are always valid. Idempotent.

Run:  python powerbi/tools/build_template_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1] / "ChurnEngine" / "ChurnEngine.Report" / "report.json"

GREEN = "#6FBE6F"
AMBER = "#F2A900"
GRAY_T = "#595959"   # titles
GRAY_N = "#404040"   # numbers
RED = "#C0504D"

PAGE_BG = "#F2F2F2"


# ---------- expression helpers ----------
def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def slit(value: str) -> dict:
    """String literal (single-quoted inside, as the vizConfig expects)."""
    return {"expr": {"Literal": {"Value": f"'{value}'"}}}


def color_obj(hexv: str) -> dict:
    return {"solid": {"color": slit(hexv)}}


def hide(*names: str) -> dict:
    """objects entries that hide the named formatting cards (show:false)."""
    return {n: [{"properties": {"show": lit("false")}}] for n in names}


# ---------- container wrapper ----------
def container(name, x, y, w, h, z, single):
    cfg = {
        "name": name,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z}}],
        "singleVisual": single,
    }
    return {
        "config": json.dumps(cfg, separators=(",", ":")),
        "filters": "[]",
        "height": h, "width": w, "x": x, "y": y, "z": z,
    }


# ---------- visual builders ----------
def textbox(name, x, y, w, h, z, paragraphs, card=False, valign="top"):
    objects = {"general": [{"properties": {"paragraphs": paragraphs}}]}
    if valign != "top":
        objects["general"][0]["properties"]["verticalContentAlignment"] = slit(valign)
    sv = {"visualType": "textbox", "drillFilterOtherVisuals": True, "objects": objects}
    if not card:
        sv["objects"].update(hide("background", "border"))
    return container(name, x, y, w, h, z, sv)


def para(text, size, color, bold=False, align="left", family="Segoe UI"):
    ts = {"fontSize": f"{size}px", "color": color, "fontFamily": family}
    if bold:
        ts["fontWeight"] = "bold"
    return {"textRuns": [{"value": text, "textStyle": ts}], "horizontalTextAlignment": align}


def card(name, x, y, w, h, z, measure, entity, alias):
    sv = {
        "visualType": "card",
        "projections": {"Values": [{"queryRef": measure}]},
        "prototypeQuery": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": entity, "Type": 0}],
            "Select": [{"Measure": {"Expression": {"SourceRef": {"Source": alias}}, "Property": measure}, "Name": measure}],
        },
        "drillFilterOtherVisuals": True,
        "objects": {
            "labels": [{"properties": {"color": color_obj(GRAY_N), "fontSize": lit("32D")}}],
            "categoryLabels": [{"properties": {"show": lit("false")}}],
            **hide("background", "border"),
        },
    }
    return container(name, x, y, w, h, z, sv)


def _cat_select(entity, alias, prop):
    return {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop}, "Name": f"{entity}.{prop}"}


def _val_select(entity, alias, prop, func=0):
    return {
        "Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop}}, "Function": func},
        "Name": f"{('Sum' if func == 0 else 'Avg')}({entity}.{prop})",
    }


def column_chart(name, x, y, w, h, z, *, entity, alias, cat, val, color, title=None, mini=False):
    cat_ref = f"{entity}.{cat}"
    val_ref = f"Sum({entity}.{val})"
    objects = {
        "dataPoint": [{"properties": {"defaultColor": {"solid": {"color": slit(color)}}}}],
        "legend": [{"properties": {"show": lit("false")}}],
        "labels": [{"properties": {"show": lit("true"), "color": {"solid": {"color": slit(GRAY_T)}}, "fontSize": lit("8D"), "labelDisplayUnits": lit("0D")}}],
    }
    if mini:
        objects["valueAxis"] = [{"properties": {"show": lit("false")}}]
        objects["categoryAxis"] = [{"properties": {"show": lit("true"), "fontSize": lit("8D")}}]
        objects.update(hide("background", "border"))
        objects["title"] = [{"properties": {"show": lit("false")}}]
    else:
        objects["title"] = [{"properties": {"show": lit("true"), "text": slit(title), "fontColor": {"solid": {"color": slit(GRAY_T)}}, "alignment": slit("left")}}]
        objects["valueAxis"] = [{"properties": {"show": lit("false")}}]
        objects["categoryAxis"] = [{"properties": {"show": lit("true")}}]
    sv = {
        "visualType": "clusteredColumnChart",
        "projections": {"Category": [{"queryRef": cat_ref, "active": True}], "Y": [{"queryRef": val_ref}]},
        "prototypeQuery": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": entity, "Type": 0}],
            "Select": [_cat_select(entity, alias, cat), _val_select(entity, alias, val)],
        },
        "drillFilterOtherVisuals": True,
        "objects": objects,
    }
    return container(name, x, y, w, h, z, sv)


def area_chart(name, x, y, w, h, z, *, entity, alias, cat, val, color, title):
    cat_ref = f"{entity}.{cat}"
    val_ref = f"Sum({entity}.{val})"
    objects = {
        "dataPoint": [{"properties": {"defaultColor": {"solid": {"color": slit(color)}}}}],
        "legend": [{"properties": {"show": lit("false")}}],
        "labels": [{"properties": {"show": lit("false")}}],
        "title": [{"properties": {"show": lit("true"), "text": slit(title), "fontColor": {"solid": {"color": slit(GRAY_T)}}, "alignment": slit("left")}}],
        "categoryAxis": [{"properties": {"show": lit("true")}}],
        "valueAxis": [{"properties": {"show": lit("true")}}],
    }
    sv = {
        "visualType": "areaChart",
        "projections": {"Category": [{"queryRef": cat_ref, "active": True}], "Y": [{"queryRef": val_ref}]},
        "prototypeQuery": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": entity, "Type": 0}],
            "Select": [_cat_select(entity, alias, cat), _val_select(entity, alias, val)],
        },
        "drillFilterOtherVisuals": True,
        "objects": objects,
    }
    return container(name, x, y, w, h, z, sv)


def gauge(name, x, y, w, h, z, *, value, maxv, entity, alias, color):
    sv = {
        "visualType": "gauge",
        "projections": {"Y": [{"queryRef": value}], "MaxValue": [{"queryRef": maxv}]},
        "prototypeQuery": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": entity, "Type": 0}],
            "Select": [
                {"Measure": {"Expression": {"SourceRef": {"Source": alias}}, "Property": value}, "Name": value},
                {"Measure": {"Expression": {"SourceRef": {"Source": alias}}, "Property": maxv}, "Name": maxv},
            ],
        },
        "drillFilterOtherVisuals": True,
        "objects": {
            "dataPoint": [{"properties": {"fillColor": {"solid": {"color": slit(color)}}, "targetColor": {"solid": {"color": slit(GRAY_T)}}}}],
            **hide("background", "border"),
        },
    }
    return container(name, x, y, w, h, z, sv)


# ---------- page assembly ----------
def build_exec_page_visuals():
    V = []
    # header
    V.append(textbox("ex_title", 24, 16, 700, 64, 10, [
        para("Customer Churn & Revenue", 30, GRAY_N, bold=True),
        para("Executive Summary  ·  Top-line KPIs  ·  snapshot Feb 2017", 13, "#8A8A8A"),
    ]))

    # KPI tiles
    tiles = [
        dict(x=24, title="MRR", measure="MRR (NT$)", entity="metrics", alias="m",
             delta="▲ 1.2%  vs prior month", dcolor=GREEN,
             mini=dict(entity="mrr_monthly", alias="t", cat="month", val="mrr")),
        dict(x=340, title="Active Customers", measure="Active Customers", entity="metrics", alias="m",
             delta="▲ 0.8%  vs prior month", dcolor=GREEN,
             mini=dict(entity="mrr_monthly", alias="t", cat="month", val="active_customers")),
        dict(x=656, title="Revenue at Risk / mo", measure="Revenue at Risk (NT$/mo)", entity="revenue_at_risk", alias="r",
             delta="▼ ~20% of MRR at risk", dcolor=RED,
             mini=dict(entity="revenue_at_risk", alias="r", cat="score_lo", val="expected_monthly_revenue_at_risk")),
    ]
    for i, t in enumerate(tiles):
        X = t["x"]
        # white background tile
        V.append(textbox(f"ex_bg{i}", X, 92, 300, 246, 100 + i, [para("", 1, "#FFFFFF")], card=True))
        # centered title
        V.append(textbox(f"ex_t{i}", X + 8, 100, 284, 24, 1000 + i * 10,
                         [para(t["title"], 15, GRAY_T, align="center")]))
        # big number
        V.append(card(f"ex_c{i}", X + 8, 126, 190, 58, 1001 + i * 10, t["measure"], t["entity"], t["alias"]))
        # delta accent
        V.append(textbox(f"ex_d{i}", X + 150, 138, 142, 40, 1002 + i * 10,
                         [para(t["delta"], 12, t["dcolor"], bold=True, align="right")], valign="middle"))
        # amber mini chart
        m = t["mini"]
        V.append(column_chart(f"ex_m{i}", X + 8, 188, 284, 144, 1003 + i * 10,
                              entity=m["entity"], alias=m["alias"], cat=m["cat"], val=m["val"],
                              color=AMBER, mini=True))

    # gauges (right column)
    gauges = [
        dict(y=92, title="Retention Rate (monthly)", value="Retention Rate"),
        dict(y=220, title="Revenue Retained (scored)", value="% Revenue Retained"),
    ]
    for i, g in enumerate(gauges):
        V.append(textbox(f"ex_gbg{i}", 972, g["y"], 284, 118, 140 + i, [para("", 1, "#FFFFFF")], card=True))
        V.append(textbox(f"ex_gt{i}", 980, g["y"] + 6, 268, 22, 1500 + i * 10,
                         [para(g["title"], 13, GRAY_T, align="center")]))
        V.append(gauge(f"ex_g{i}", 980, g["y"] + 26, 268, 86, 1501 + i * 10,
                       value=g["value"], maxv="Scale 100%", entity="metrics", alias="m", color=GREEN))

    # wide trend area chart (left)
    V.append(area_chart("ex_area", 24, 350, 620, 180, 2000,
                        entity="mrr_monthly", alias="t", cat="month", val="mrr",
                        color=GREEN, title="Monthly Recurring Revenue (NT$) — trend"))

    # insights panel (right, tall)
    bullets = [
        para("Insights", 16, GRAY_N, bold=True, align="center"),
        para("", 6, "#FFFFFF"),
        para("↑  Revenue grew from ~NT$80M to ~NT$279M per month.", 12, "#404040"),
        para("⚠  Manual-pay customers churn 37% vs 5% on auto-renew — ~7× higher.", 12, "#404040"),
        para("→  ~9% of customers churn each month (1.15M paying base).", 12, "#404040"),
        para("→  The riskiest band (~10% of customers) holds ~NT$13.8M/mo at risk.", 12, "#404040"),
        para("✓  Auto-renew status is the single strongest churn signal in the model.", 12, "#404040"),
        para("✓  Model ROC-AUC 0.907; scores active users 1–100 for targeting.", 12, "#404040"),
    ]
    V.append(textbox("ex_insights", 972, 350, 284, 358, 210, bullets, card=True))

    # bottom column charts (green)
    V.append(column_chart("ex_b1", 24, 542, 454, 166, 2100,
                         entity="risk_distribution", alias="rd", cat="score_lo", val="customers",
                         color=GREEN, title="Customers by risk band (score 1–100)"))
    V.append(column_chart("ex_b2", 494, 542, 462, 166, 2101,
                         entity="revenue_at_risk", alias="r", cat="score_lo", val="expected_monthly_revenue_at_risk",
                         color=GREEN, title="Expected revenue at risk by band (NT$/mo)"))
    return V


def main():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    for section in report["sections"]:
        if section.get("name") == "s1exec":
            section["displayName"] = "1 - Executive Summary"
            # light-gray page background to match the template
            section["config"] = json.dumps({
                "objects": {
                    "background": [{"properties": {"color": {"solid": {"color": slit(PAGE_BG)}}, "transparency": lit("0D")}}],
                    "outspace": [{"properties": {"color": {"solid": {"color": slit(PAGE_BG)}}, "transparency": lit("0D")}}],
                }
            }, separators=(",", ":"))
            section["visualContainers"] = build_exec_page_visuals()
            break
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    json.loads(REPORT.read_text(encoding="utf-8"))  # sanity parse
    print("Rebuilt page 1 (s1exec):", len(build_exec_page_visuals()), "visuals")


if __name__ == "__main__":
    main()
