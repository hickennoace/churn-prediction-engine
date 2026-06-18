# Customer Churn Prediction & Business Performance Engine

> **Source of truth & project tracker.** This file governs scope, sequencing, and
> the rules of engagement for the project. Keep it updated as phases complete.

## Project Goal

An end-to-end engine that ingests raw subscription data, cleans and models it into a
relational schema, computes core SaaS economics (CAC, LTV, MRR), trains an ML model to
assign a **1–100 Churn Risk Score** to active customers, and exposes the results through
a FastAPI layer feeding Excel/PowerBI dashboards. The piece is meant to demonstrate the
full bridge from **raw data → ML → executive BI**.

## Confirmed Technical Decisions

| Area | Decision |
|------|----------|
| **Dataset** | **KKBox Churn Prediction Challenge** (WSDM Cup 2018, Kaggle). Scope = full `members_v3` + `transactions`(+`v2`) + `train`(+`v2`) labels. The 30GB `user_logs` behavioral firehose is **out of scope** (optional future enhancement) — not loadable on a laptop. No synthetic data. |
| **Database** | **PostgreSQL** (local install or Docker). Connection config via `.env` (never committed). |
| **Env / deps** | **`venv` + pinned `requirements.txt`** (Python 3.11+). |
| **ML** | Scikit-Learn (Random Forest classifier baseline). |
| **API** | FastAPI + Uvicorn. |
| **BI** | Advanced SQL (CTEs, window functions) → Excel / PowerBI. |

## Proposed Repository Layout
```
churn-prediction-engine/
├── data/
│   ├── raw/            # original Kaggle CSV (gitignored)
│   ├── interim/        # intermediate ETL output (gitignored)
│   └── processed/      # clean, load-ready data (gitignored)
├── src/
│   ├── ingestion/      # Phase 1: raw load
│   ├── etl/            # Phase 2: clean & transform
│   ├── analytics/      # Phase 3: CAC / LTV / MRR
│   ├── ml/             # Phase 3: churn model train + score
│   └── api/            # Phase 4: FastAPI app
├── sql/                # Phase 5: BI queries (CTEs, window funcs)
├── notebooks/          # exploratory analysis (EDA)
├── tests/
├── .env.example        # template; real .env is gitignored
├── requirements.txt
└── CLAUDE.md
```

---

## Roadmap

### Phase 1: Data Acquisition & Infrastructure — `[x] Complete`
- [x] Stand up **PostgreSQL 16** via Docker (`docker-compose.yml`, container `churn_postgres`, healthy on `:5432`).
- [x] `.env.example` + `.env` with `DB_HOST/PORT/NAME/USER/PASSWORD`.
- [x] `requirements.txt` (pinned) + `.venv`; added Phase-1 acquisition tooling (`kaggle`, `py7zr`).
- [x] Acquired the **KKBox** dataset via Kaggle CLI; extracted CSVs into `data/raw/` (`members_v3`, `transactions`(+`v2`), `train`(+`v2`)). `user_logs` excluded by scope.
- [x] `src/ingestion/load_raw.py` rewritten for the multi-file dataset: loads **verbatim** (all `TEXT`) into 3 staging tables via PostgreSQL `COPY`, with a `_source_file` provenance column. Tables: `raw_members`, `raw_transactions`, `raw_train`.
- [x] Sanity check passed — DB row counts match source exactly: `raw_members`=6,769,473 · `raw_transactions`=22,978,755 · `raw_train`=1,963,891.

### Phase 2: Data Cleaning & ETL — `[x] Complete`
> Full methodology + evidence in [`docs/data-cleaning.md`](docs/data-cleaning.md).
- [x] Profiled raw data (nulls, dupes, type/outlier issues) — e.g. 67% garbage ages, 65% missing gender, epoch/2036 junk expiry dates, 881,701 label overlap.
- [x] Missing-value strategy (documented per column): age out of 1–100 → NULL; gender empty → NULL (kept as "unknown"); bad expiry → NULL + `expire_date_valid` flag.
- [x] Dates parsed `YYYYMMDD` → `DATE` (`to_date`).
- [x] Clean relational schema built via set-based SQL (`src/etl/clean.py`): **`customers`** (one row per `msno`, PK) + **`transactions`** (one row per billing event) with FK.
- [x] Constraints/keys/indexes: `customers` PK; `transactions` FK→customers + indexes on `msno`, `transaction_date`, `membership_expire_date`.
- [x] Clean tables in PostgreSQL; `customers` snapshot to `data/processed/customers.parquet` (transactions kept in PG by design). All validation checks PASS.

### Phase 3: Business Logic & Machine Learning — `[x] Complete`
> Methodology + results in [`docs/phase3-metrics-and-model.md`](docs/phase3-metrics-and-model.md).
- [x] **Economic metrics** (`src/analytics/metrics.py`): MRR NT$147.6M/mo, ARPU NT$128, LTV NT$1,424 (as of 2017-02-28). **CAC** not in dataset → handled honestly (see doc §2.3; pending user pick A/B).
- [x] Feature engineering (`src/ml/features.py`): `customer_features` (2,391,675 × 27), leak-free as of 2017-02-28.
- [x] **Random Forest** trained (`src/ml/train_model.py`) on 968,436 labeled, isotonic-calibrated.
- [x] Evaluation: **ROC-AUC 0.907**, PR-AUC 0.629; confusion matrix + report logged.
- [x] **1–100 risk score** — well-calibrated (band 1 → 2.2% actual churn, band 10 → 94.8%).
- [x] Scores written to `customer_risk_scores(msno, churn_prob, risk_score, scored_at)` for all 2,391,675 customers.

### Phase 4: API Layer — `[x] Complete`
- [x] **FastAPI** app (`src/api/main.py`): `/metrics`, `/customers/high-risk`, `/customer?msno=`, plus `/`, `/health`. Run: `uvicorn src.api.main:app --port 8000`.
- [x] Service layer (`src/api/service.py`) — only place touching the DB; parameterized SQL, raw schema never exposed.
- [x] Pydantic DTOs (`src/api/schemas.py`); pagination (`limit`/`offset`/`min_score`); 404 + 422 + 503 handling. CAC handled per **Option A** (`/metrics?cac=` → LTV:CAC, no fabricated value).
- [x] OpenAPI/Swagger at `/docs` + `/openapi.json` (verified 200). All endpoints tested live.

### Phase 5: BI Preparation — `[x] Complete`
- [x] Advanced **SQL** in `sql/` (CTEs + window functions): `v_subscription_coverage` (LEAD), `mv_mrr_monthly`/`v_mrr_monthly` (LAG growth), `mv_cohort_retention`/`v_cohort_retention`, `v_churn_by_segment`, `v_risk_distribution` (SUM OVER), `v_revenue_at_risk`.
- [x] Reporting views + `src/analytics/build_bi.py` exports 7 marts to `powerbi/ChurnEngine/data/*.csv`.
- [x] **Power BI `.pbip` project** in `powerbi/ChurnEngine/` (semantic model + DAX measures + 3-page report) — see `powerbi/README.md`. BI tools connect via these views (direct) or the API.
- _Key insights surfaced: MRR NT$80M→279M; manual-pay churn 37.3% vs auto-renew 5.0%; top risk band = NT$13.8M/mo revenue at risk._

### Phase 6: Showcase & Portfolio Presentation — `[ ] Pending`
> The deliverable that gets seen. For a **data/business/financial analyst** target role,
> insight + communication are graded as heavily as the engineering. Optimize for the
> 30-second skim a recruiter/hiring manager actually gives a portfolio repo.

- [ ] **`README.md` as the front door** — problem statement, **architecture diagram** (raw → ETL → ML → API → BI), tech-stack badges, headline KPIs, **dashboard screenshots/GIF near the top**, key business insights, and a copy-paste **quickstart** (Docker up → load → run).
- [ ] **Executive insight write-up** (1–2 pages, the analyst differentiator) — top **churn drivers**, **revenue/MRR at risk ($)**, concrete **retention recommendations**, and model performance translated into *business* terms (not just AUC).
- [ ] **Polished BI dashboard** (PowerBI/Excel) — pages for MRR/revenue overview, churn-risk distribution, cohort retention, and segment deep-dive. Commit `.pbix`/`.xlsx` + screenshots; publish a share link if possible.
- [ ] **Architecture diagram** (Mermaid in-README, or draw.io/Excalidraw export) so the end-to-end pipeline is legible at a glance.
- [ ] **Clean GitHub presentation** — meaningful commit history, descriptive messages, a tagged `v1.0` release, repo **pinned** on the profile, topics/description set.
- [ ] **Quantified CV bullet(s)** — e.g. *"End-to-end churn & revenue engine on 20M+ real subscription transactions; surfaced \$X MRR at risk; Random-Forest risk model (ROC-AUC 0.X) scoring active users 1–100."*
- [ ] **Portfolio + social linkage** — add a case-study page on the Next.js portfolio site and the HTML/PDF résumé; optional **LinkedIn post** and a short **Loom/GIF walkthrough**.
- [ ] **Interview talking points** (`docs/talking-points.md`) — STAR-style narrative: the business problem, what you explored & *why*, how you'd explain the KPIs and the model to a non-technical exec.

---

## Working Protocol (Strict Rules of Engagement)

1. **Step-by-Step Execution.** Work on **only one phase at a time**. Always ask for
   explicit approval before moving to the next phase.
2. **Ask Before Assuming.** If a specific dataset, library version, or architectural
   decision is needed, **STOP and ask**. Never generate fake data or hallucinate file
   paths.
3. **Update the Roadmap.** After completing a phase, update this file to mark it
   `[x] Complete` (and check off the sub-tasks) before proceeding.

## Status Log
- _Project initialized; repo + `.gitignore` + `CLAUDE.md` created._
- _Dataset locked in (2026-06-18): **KKBox Churn Prediction Challenge**. Multi-table — Phase 1 loader (`load_raw.py`, currently single-CSV) to be adapted for `members`/`transactions`/`train`. Awaiting user to download `members_v3`, `transactions`(+`v2`), `train`(+`v2`) from Kaggle into `data/raw/`. `user_logs` excluded by scope._
- _**Phase 1 COMPLETE (2026-06-18).** KKBox CSVs downloaded + extracted; Postgres 16 up via Docker; `load_raw.py` loads 3 verbatim staging tables via `COPY` — row counts verified (6.77M / 22.98M / 1.96M). Ready to begin Phase 2 (cleaning & ETL) on approval._
- _**Phase 2 COMPLETE (2026-06-18).** Profiled raw data; built clean `customers` (2,426,143) + `transactions` (22,975,416, deduped) via SQL ETL (`src/etl/clean.py`) with PK/FK/indexes; all validation PASS; 970,960 labeled customers @ 8.99% churn. Methodology in `docs/data-cleaning.md`. Decisions: train_v2 canonical label, transacting-customer universe, null+flag dirty values. Ready for Phase 3 (metrics + ML) on approval._
- _**Phase 3 COMPLETE (2026-06-18).** Leak-free as-of cutoff 2017-02-28 (predict March-2017 expiry cohort). Metrics: MRR NT$147.6M/mo, ARPU NT$128, LTV NT$1,424. Features `customer_features` (2,391,675×27). Random Forest (ROC-AUC 0.907, PR-AUC 0.629), isotonic-calibrated; well-calibrated 1-100 score (band 1→2.2%, band 10→94.8% actual churn) written to `customer_risk_scores`. Docs: `docs/phase3-metrics-and-model.md`._
- _**Phase 4 COMPLETE (2026-06-18).** FastAPI read-only API (`src/api/`): `/metrics` (+`?cac=` for LTV:CAC, Option A chosen), `/customers/high-risk` (paginated), `/customer?msno=`, `/health`, Swagger `/docs`. Service-layer isolates DB; Pydantic DTOs; 404/422/503 handled. Persisted `business_metrics` table + `ix_risk_score` index for fast serving. All endpoints tested live. Ready for Phase 5 (BI SQL) on approval._
- _**Phase 5 COMPLETE (2026-06-18).** BI SQL (`sql/00-04`, CTEs + LEAD/LAG/SUM-OVER window funcs) → views/matviews; `src/analytics/build_bi.py` exports 7 CSV marts. **Power BI `.pbip`** authored in `powerbi/ChurnEngine/` (model.bim + DAX measures + report.json). User has AWS free tier + wants AWS (future Phase 7: RDS serving marts + S3 + dashboard, free-tier-safe)._
- _**Dashboard opens & saved in Power BI Desktop 26.06 (2026-06-18, commit `3d62180`).** Fixed 3 issues iteratively (.pbip $schema, report themeCollection, then rendered). Enhanced to 4 plain-language pages (Executive Summary, Revenue & Customers, Why Customers Leave, Who's At Risk) with header banners, KPI cards, insight callouts. Power BI re-serialized to canonical format (compat 1600, .platform, diagramLayout); dropped the registered-resource custom theme — re-apply next session via View→Themes→Browse. **NEXT:** verify/refine visuals; re-apply theme; Phase 6 (showcase README) + Phase 7 (AWS)._
