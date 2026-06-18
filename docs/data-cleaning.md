# Phase 2 — Data Cleaning & ETL Methodology

> **Purpose.** This document explains, step by step, exactly how the raw KKBox data is
> cleaned and reshaped into an analysis-ready relational schema — *what* we do, *why* we
> do it, and *which tool* we use at each step. Every decision is grounded in the real data
> profiling in [§2](#2-profiling-the-evidence), not assumptions.
>
> **Status legend:** ✅ done · 🔜 planned (this phase) · ⏳ awaiting your approval

---

## 1. Philosophy & approach

Phase 1 loaded the source files **verbatim** into three `raw_*` staging tables (everything
stored as `TEXT`, nothing coerced). Phase 2 turns that faithful-but-messy copy into a clean,
typed, **relational** model that the rest of the project (metrics, ML, BI) can trust.

We follow a classic **ELT** pattern:

| | Stage | Where | Tool |
|---|---|---|---|
| **E**xtract | raw CSV → DB | Phase 1 | Kaggle CLI, `py7zr`, PostgreSQL `COPY` |
| **L**oad | verbatim staging tables | Phase 1 | `src/ingestion/load_raw.py` |
| **T**ransform | clean → typed relational schema | **Phase 2** | **SQL in PostgreSQL** (set-based, runs next to the 23M rows) |

**Why transform in SQL rather than pandas?** The transaction table is ~23M rows. Set-based
SQL runs the cleaning *inside* the database (no 1.7 GB round-trip into Python memory), it is
reproducible, and it is exactly the skill an analyst role expects. pandas is reserved for
later exploratory/feature work where it shines.

The two clean output tables:

```
customers        one row per customer (msno)  ── PK: msno
   ▲
   │ FK: transactions.msno → customers.msno
   │
transactions     one row per billing event
```

---

## 2. Profiling: the evidence

Real numbers from the raw tables (see [Appendix](#appendix-profiling-queries) for the exact
queries). These drive every cleaning decision below.

### 2.1 `raw_members` — 6,769,473 rows
| Finding | Value | Implication |
|---|---|---|
| Distinct `msno` | 6,769,473 (= row count) | ✅ `msno` is a natural primary key, no dedup needed |
| `gender` missing | 4,429,505 (**65.4%**) | Too sparse to drop rows; treat "unknown" as its own category |
| `bd` (age) ≤ 0 | 4,540,489 (**67.1%**) | Placeholder/garbage — must be nulled |
| `bd` in 1–100 | 2,223,607 (32.8%) | The only plausibly-valid ages |
| `bd` > 100 | 5,377 (0.08%) | Impossible — null these too |
| `bd` raw range | **−7,168 … 2,016** | Clear evidence the field is dirty |
| `gender` values | `male` 1.20M · `female` 1.14M · `NULL` 4.43M | Clean domain once nulls are handled |
| `city` distinct | 21 | Categorical code |
| `registered_via` | codes 4/3/9/7 dominate, long tail | Categorical code |
| `registration_init_time` range | 2004-03-26 … 2017-04-29 | Valid `YYYYMMDD`, parse to `DATE` |

### 2.2 `raw_transactions` — 22,978,755 rows
| Finding | Value | Implication |
|---|---|---|
| Distinct `msno` | 2,426,143 | The real "customer" universe (most members never transact) |
| `transaction_date` range | 2015-01-01 … 2017-03-31 | Clean, parse to `DATE` |
| `membership_expire_date` range | **1970-01-01 … 2036-10-15** | `19700101` = epoch placeholder; far-future = junk → null/flag |
| `is_auto_renew` × `is_cancel` | (1,0)=18.59M · (0,0)=3.50M · (1,1)=0.89M · (0,1)=10 | Both are clean 0/1 → cast to `BOOLEAN` |
| `actual_amount_paid` = 0 | 1,218,324 (5.3%) | Legitimate free/promo months — **keep** |
| `actual_amount_paid` < 0 | 0 | ✅ no negative payments |
| paid ≠ list price | 1,726,706 (7.5%) | Discounts/promos — keep, it's real |
| price range | 0 … 2,000 | Plausible (NT$) |
| `payment_plan_days` range | **0 … 450** | `0`-day plans are suspect → flag |
| Exact-duplicate rows | 3,339 across 3,222 groups (0.015%) | Negligible but real → de-duplicate |

### 2.3 `raw_train` — 1,963,891 rows (labels)
| Finding | Value | Implication |
|---|---|---|
| `train.csv` churn rate | 63,471 / 992,931 = **6.4%** | Feb-2017 churn window |
| `train_v2.csv` churn rate | 87,330 / 970,960 = **9.0%** | Mar-2017 churn window (competition refresh) |
| Duplicate `msno` within a file | 0 (both files) | ✅ each file is clean per-window |
| `msno` in **both** files | 881,701 | Same customer, two different prediction months |
| **Conflicting** labels in overlap | 45,990 (5.2% of overlap) | Expected — churned one month, not the other |

### 2.4 Cross-table integrity
| Finding | Value | Implication |
|---|---|---|
| Labeled `msno` **not** in `transactions` | 0 | ✅ every labeled customer has billing history |
| Labeled `msno` **not** in `members` | 120,759 | Some labels lack a profile → member fields become `NULL` |

---

## 3. Decisions (approved 2026-06-18) ✅

These three choices shaped the clean schema. **All approved as recommended (▶).**

1. **Label source (handling the 881,701-customer overlap).**
   - **▶ Option A — use `train_v2.csv` as the canonical label** (most recent / official
     competition refresh; March-2017 window). Single label per customer, no conflicts.
     Customer label universe ≈ 970,960.
   - Option B — keep **both** windows with a `churn_window` column (Feb & Mar). Richer for
     temporal analysis, but a customer can appear twice and we carry the 45,990 conflicts by
     design.
   - *Recommendation: A* — cleaner for a single churn model + 1–100 score; we can revisit B later.

2. **Customer universe (who is a "customer").**
   - **▶ Option A — distinct `msno` in `transactions` (2,426,143)**: the real paying base.
     Guarantees the `transactions → customers` foreign key is valid by construction, and makes
     revenue metrics (MRR/ARPU) meaningful. Member attributes/labels join on where available.
   - Option B — all 6,769,473 members (includes 4.3M who never transacted). Inflates the base
     with non-customers; weaker for revenue/churn.
   - *Recommendation: A.*

3. **Dirty-value policy (documented, not silent).** `bd` outside 1–100 → `NULL`;
   `membership_expire_date` = `19700101` or implausibly far future → `NULL` + a
   `expire_date_valid` flag; `payment_plan_days = 0` → keep but flag. (Open to tightening the
   future-date cap.)

---

## 4. Cleaning steps — `customers` ✅ (implemented in `src/etl/clean.py`)

One row per `msno` (universe per decision #2). Built by joining cleaned `members` to the
chosen label set.

| # | Step | Rule | Tool |
|---|---|---|---|
| C1 | **Define universe** | `SELECT DISTINCT msno FROM raw_transactions` | SQL |
| C2 | **Attach member profile** | `LEFT JOIN raw_members` (120,759 will have NULL attrs) | SQL |
| C3 | **Clean age** | `bd_clean = CASE WHEN bd BETWEEN 1 AND 100 THEN bd ELSE NULL END` | SQL `CASE`/cast |
| C4 | **Normalize gender** | keep `male`/`female`; empty → `NULL` (kept as "unknown") | SQL `NULLIF` |
| C5 | **Type categoricals** | `city`, `registered_via` → `SMALLINT` codes | SQL cast |
| C6 | **Parse dates** | `registration_init_time` `YYYYMMDD` → `DATE` (`to_date(...,'YYYYMMDD')`) | SQL |
| C7 | **Attach label** | `LEFT JOIN` chosen label → `is_churn BOOLEAN` (NULL = unlabeled, to be scored) | SQL |
| C8 | **Constraints** | `PRIMARY KEY (msno)`, `NOT NULL` where guaranteed | SQL DDL |

**Resulting `customers` schema (draft):**
```sql
customers(
  msno                TEXT     PRIMARY KEY,
  city                SMALLINT,
  bd_clean            SMALLINT,            -- 1..100 or NULL
  gender              TEXT,                -- 'male' | 'female' | NULL
  registered_via      SMALLINT,
  registration_date   DATE,
  is_churn            BOOLEAN              -- label where known, else NULL
)
```

---

## 5. Cleaning steps — `transactions` ✅ (implemented in `src/etl/clean.py`)

One row per billing event; the analytical fact table.

| # | Step | Rule | Tool |
|---|---|---|---|
| T1 | **De-duplicate** | drop the 3,339 exact-duplicate rows (`SELECT DISTINCT`) | SQL |
| T2 | **Cast numerics** | `payment_method_id`, `payment_plan_days`, `plan_list_price`, `actual_amount_paid` → `INT` | SQL cast |
| T3 | **Cast booleans** | `is_auto_renew`, `is_cancel` → `BOOLEAN` | SQL |
| T4 | **Parse dates** | `transaction_date`, `membership_expire_date` `YYYYMMDD` → `DATE` | SQL `to_date` |
| T5 | **Flag bad expiry** | `19700101` / implausible future → `membership_expire_date = NULL`, `expire_date_valid = FALSE` | SQL `CASE` |
| T6 | **Flag zero-day plans** | `payment_plan_days = 0` → keep, `plan_days_valid = FALSE` | SQL |
| T7 | **Foreign key** | `FOREIGN KEY (msno) REFERENCES customers(msno)` | SQL DDL |
| T8 | **Index** | `(msno)`, `(transaction_date)`, `(membership_expire_date)` for downstream metrics | SQL |

**Resulting `transactions` schema (draft):**
```sql
transactions(
  msno                    TEXT    REFERENCES customers(msno),
  payment_method_id       SMALLINT,
  payment_plan_days       SMALLINT,
  plan_list_price         INT,
  actual_amount_paid      INT,
  is_auto_renew           BOOLEAN,
  is_cancel               BOOLEAN,
  transaction_date        DATE,
  membership_expire_date  DATE,            -- NULL when invalid
  expire_date_valid       BOOLEAN,
  plan_days_valid         BOOLEAN
)
-- indexes: (msno), (transaction_date), (membership_expire_date)
```

---

## 6. Outputs & validation ✅

- **Persist** clean tables in PostgreSQL (schema `clean` or `clean_*` table names), plus a
  Parquet snapshot in `data/processed/` for portability.
- **Validate after load** (mirrors the Phase 1 row-count gate):
  - `customers` row count = distinct transaction `msno` (2,426,143).
  - No `transactions.msno` violates the FK (0 orphans — already confirmed).
  - `bd_clean` strictly within 1–100 or NULL; `gender ∈ {male, female, NULL}`.
  - All dates parse (no cast errors); flagged-invalid counts reported.
- **Document** the final per-column decisions and row-count deltas back into this file.

---

## 6b. Execution results (run 2026-06-18) ✅

Built by `python -m src.etl.clean`, snapshot by `python -m src.etl.export_processed`.

**Validation — all checks PASS:**

| Check | Result |
|---|---|
| `customers` count = distinct transacting `msno` | 2,426,143 = 2,426,143 ✅ |
| `customers.msno` unique (PK) | 0 dupes ✅ |
| `transactions` de-duplicated | 22,975,416 (removed **3,339** exact dupes — matches profiling) ✅ |
| FK orphans (`transactions` → `customers`) | 0 ✅ |
| `bd_clean` ∈ 1–100 or NULL | 0 violations ✅ |
| `gender` ∈ {male, female, NULL} | 0 violations ✅ |

**Resulting metrics:**
- Labeled customers: **970,960** at **8.99% churn** (matches the train_v2 window).
- Transactions flagged `expire_date_valid = FALSE`: **19,435**.
- Transactions flagged `plan_days_valid = FALSE` (0-day plans): **872,339**.

**Persisted outputs:**
- PostgreSQL tables `customers` and `transactions` (typed, keyed, indexed).
- `data/processed/customers.parquet` (2,426,143 rows × 7 cols). `transactions` kept in
  PostgreSQL only (indexed) — a 23M-row columnar copy would duplicate disk for no benefit.

---

## 7. Tools summary

| Tool | Used for |
|---|---|
| **PostgreSQL 16** (Docker) | the cleaning engine — all set-based transforms run here |
| **SQL** (`CASE`, `to_date`, casts, `DISTINCT`, constraints, indexes) | every cleaning step |
| **SQLAlchemy / psycopg2** (`src/config.py`) | running the SQL from Python, orchestration |
| **pandas / pyarrow** | Parquet snapshot to `data/processed/` |
| **ruff / pytest** | lint + validation tests on the ETL code |

---

## Appendix: profiling queries

The numbers in §2 come from aggregate scans of the `raw_*` tables, e.g.:

```sql
-- age (bd) sanity
SELECT MIN(b), MAX(b),
       COUNT(*) FILTER (WHERE b<=0)            AS le0,
       COUNT(*) FILTER (WHERE b BETWEEN 1 AND 100) AS in_1_100,
       COUNT(*) FILTER (WHERE b>100)           AS gt100
FROM (SELECT CASE WHEN bd ~ '^-?[0-9]+$' THEN bd::int END AS b FROM raw_members) s;

-- label overlap + conflicts between the two train files
WITH a AS (SELECT msno,is_churn FROM raw_train WHERE _source_file='train.csv'),
     b AS (SELECT msno,is_churn FROM raw_train WHERE _source_file='train_v2.csv')
SELECT COUNT(*) AS overlap,
       COUNT(*) FILTER (WHERE a.is_churn<>b.is_churn) AS conflicts
FROM a JOIN b USING(msno);
```
