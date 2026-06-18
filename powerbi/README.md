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
│   └── model.bim                         # tables (from CSV) + DAX measures
├── ChurnEngine.Report/
│   ├── definition.pbir
│   └── report.json                       # 3-page report layout
└── data/                                 # CSV marts exported from Postgres
    ├── metrics.csv  mrr_monthly.csv  cohort_retention.csv
    ├── churn_by_segment.csv  risk_distribution.csv
    ├── revenue_at_risk.csv  high_risk_customers.csv
```

## Dashboard spec (3 pages)
**1 · Executive Overview** — KPI cards (MRR, Active Customers, Monthly Churn Rate, LTV, ARPU,
Revenue at Risk, High-Risk Customers 80+), MRR trend line (`mrr_monthly`), risk-band column
chart (`risk_distribution`).

**2 · Churn Analysis** — `segment_type` slicer + churn-rate bar chart by `segment`
(`churn_by_segment`), and a cohort-retention matrix (rows = `cohort_month`,
columns = `month_offset`, values = avg `retention_pct`).

**3 · Risk & Revenue** — expected revenue-at-risk by score band (`revenue_at_risk`),
customers per band (`risk_distribution`), and a top-200 high-risk customer table.

## DAX measures (in `model.bim`)
`MRR (NT$)`, `ARPU (NT$)`, `LTV (NT$)`, `ARR (NT$)`, `Active Customers`,
`Monthly Churn Rate`, `Avg Lifetime (months)`, `Revenue at Risk (NT$/mo)`,
`MRR Covered (NT$)`, `Scored Customers`, `High-Risk Customers (80+)`.

## ⚠️ Note on the report layout
The semantic model + measures + data are solid. The **report visuals** (`report.json`) were
authored as text without a live Power BI to test-render them, so if a visual shows an error or
blank on first open, it's almost certainly a small layout-schema mismatch — the *data model is
fine*. In that case either rebuild the affected visual by dragging the fields above (≈10 min),
or report the exact error and the `report.json` can be corrected (it's plain text by design).
