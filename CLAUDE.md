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

### Phase 2: Data Cleaning & ETL — `[ ] Pending`
- [ ] Profile data: nulls, duplicates, type mismatches, outliers.
- [ ] Handle missing values (documented strategy per column).
- [ ] Normalize/parse dates to a consistent `DATE`/`TIMESTAMP` standard.
- [ ] Split into a clean relational schema: **`customers`** (one row per customer) vs **`transactions`** (one row per billing event) with FK relationship.
- [ ] Add constraints, primary/foreign keys, and indexes.
- [ ] Load cleaned tables into PostgreSQL; persist intermediate output to `data/processed/`.

### Phase 3: Business Logic & Machine Learning — `[ ] Pending`
- [ ] **Economic metrics:** compute **CAC**, **LTV**, and **MRR** (define formulas/assumptions explicitly).
- [ ] Feature engineering for churn (tenure, usage trends, payment history, etc.).
- [ ] Train a **Scikit-Learn Random Forest** classifier on historical churned vs retained customers.
- [ ] Evaluate (precision/recall, ROC-AUC, confusion matrix); calibrate probabilities.
- [ ] Convert predicted churn probability into a **1–100 Churn Risk Score** for active users.
- [ ] **Write scores back** to the database (e.g., `customer_risk_scores` table with `scored_at` timestamp).

### Phase 4: API Layer — `[ ] Pending`
- [ ] Build a lightweight **FastAPI** app exposing read-only endpoints (e.g., `/metrics`, `/customers/high-risk`, `/customers/{id}`).
- [ ] Serve via a service layer so the **raw DB is never directly exposed**; return curated DTOs only.
- [ ] Add input validation (Pydantic), pagination, and basic error handling.
- [ ] Document with the auto-generated OpenAPI/Swagger UI.

### Phase 5: BI Preparation — `[ ] Pending`
- [ ] Author advanced **SQL** in `sql/` using **CTEs and window functions** (cohort retention, rolling MRR, churn-by-segment, risk distribution).
- [ ] Create reporting views optimized for Excel/PowerBI consumption.
- [ ] Document the connection path (direct DB view vs. via API) for the BI tools.

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
