# Power BI Dashboard — Customer Churn & Business Performance

An editable **Power BI Project (`.pbip`)** that visualizes the engine's outputs:
SaaS economics (MRR/ARPU/LTV), churn drivers, cohort retention, and the 1–100 risk model.

## How to open
1. Use **Power BI Desktop** (recent version — the `.pbip` format needs the *Power BI Project*
   preview enabled: *File → Options → Preview features → "Power BI Project (.pbip) save option"*).
2. Open **`ChurnEngine/ChurnEngine.pbip`**.
3. If prompted about the file/CSV source, allow it. The model imports from
   `ChurnEngine/data/*.csv` using **absolute paths** under
   `C:\Users\Daniel\churn-prediction-engine\...` — if you move the project, update the
   paths in *Transform data → each query → Source*.

## Applying the theme (recommended)
The project ships a polished theme, **`ChurnEngineTheme.json`** (in this folder). The most
reliable way to apply it is to import it once in Desktop:

> **View → Themes → Browse for themes →** select `powerbi/ChurnEngineTheme.json`.

It sets the data palette, fonts, white "card" visual backgrounds with subtle borders, dark
table/matrix headers, and default data-label styling. A copy is also registered inside the
report at `ChurnEngine.Report/StaticResources/SharedResources/BuiltInThemes/` so the report's
theme reference resolves on open.

## Refreshing the data
The CSVs are produced from PostgreSQL by:
```
python -m src.analytics.build_bi
```
That rebuilds the BI views and re-exports `powerbi/ChurnEngine/data/*.csv`. Then **Refresh**
in Power BI.

## Project structure (text-based, git-friendly)
```
ChurnEngine/
├── ChurnEngine.pbip                      # open this
├── ChurnEngine.SemanticModel/
│   ├── definition.pbism
│   └── model.bim                         # tables (from CSV) + DAX measures (documented)
├── ChurnEngine.Report/
│   ├── definition.pbir
│   ├── report.json                       # 4-page report layout
│   └── StaticResources/.../ChurnEngineTheme.json
└── data/                                 # CSV marts exported from Postgres
ChurnEngineTheme.json                     # importable theme (View → Themes → Browse)
tools/enhance_report.py                   # regenerates chart titles/labels safely
```

## Dashboard (4 pages)
All four pages share one design system: a **dark slate banner** with a green accent rule, a unified
slate page background, **semantic colours** (green = growth, blue = customer counts, amber = money at
risk, red = churn), white KPI/chart cards, and **tinted insight callouts** (info / warning / caution).

**1 · Executive Summary** — a **5-KPI strip** (MRR, Active Customers, Retention Rate, % Revenue
Retained, Revenue at Risk), a headline **MRR trend area chart**, a **Key Insights** panel, and two
compact risk charts (revenue at risk by band in amber, customers by band in blue).

**2 · Revenue & Customers** — ARPU / LTV / ARR cards, an **MRR growth line** beside an
**active-customers trend**, and an info callout (per-customer economics + headline MRR growth).

**3 · Why Customers Leave** — a `segment_type` slicer + a churn-rate **bar chart by `segment`** (red),
an auto-renew warning callout, and a **cohort-retention heatmap** (rows = signup month, columns =
months since signup).

**4 · Who's At Risk** — expected **revenue-at-risk by score band** (amber), **customers per band**
(blue), a caution callout, and a **high-risk customer table** prioritised for outreach.

Every chart carries an explicit caption; the rest of the styling comes from the theme above.

## DAX measures (in `model.bim`)
All measures carry a `description` and are grouped into display folders:

**1 Revenue** — `MRR (NT$)`, `ARPU (NT$)`, `LTV (NT$)`, `ARR (NT$)`, `Peak MRR (NT$)`
**2 Customers** — `Active Customers`, `Monthly Churn Rate`, `Retention Rate`,
`Customers Lost (est. / mo)`, `Avg Lifetime (months)`
**3 Risk & Churn** — `Scored Customers`, `High-Risk Customers (80+)`, `% High-Risk (80+)`,
`Avg Churn Prob (High-Risk 80+)`, `Revenue at Risk (NT$/mo)`, `MRR Covered (NT$)`,
`% Revenue at Risk`, `Revenue Retained (NT$/mo)`, `% Revenue Retained`, `Annual Revenue at Risk (NT$)`
_(plus `Scale 100%`, a display constant used as the gauge maximum.)_

## Headline insights
- **Revenue grew from ~NT$80M to ~NT$279M/month** over the observed period.
- **~9% of customers churn monthly**; manual-pay customers churn **37%** vs **5%** for
  auto-renew — roughly **7× higher**, the single strongest churn signal.
- The **riskiest band (~10% of customers) represents ~NT$13.8M/month** of revenue at risk —
  retaining even a fraction of it justifies the whole retention effort.

## Editing visuals safely
The visual `config` blocks in `report.json` are JSON *strings* embedded in JSON. Don't
hand-edit the escaped text — use the generator scripts (both use `json.dumps`, so escaping is
always valid) or rebuild the visual in Desktop by dragging fields:
- **`tools/build_template_report.py`** — rebuilds page 1 (Executive Summary) in the KPI-template layout.
- **`tools/enhance_report.py`** — adds chart titles + data labels to pages 2–4.
The semantic model, measures, and data are solid; if a visual ever shows an error on first
open it's a layout-schema nuance, not a data problem.
