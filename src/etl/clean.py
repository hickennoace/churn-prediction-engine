"""Phase 2 — Data cleaning & ETL (KKBox).

Transforms the verbatim ``raw_*`` staging tables into a clean, typed, relational
schema using set-based SQL inside PostgreSQL (no 23M-row round-trip into Python).

Approved decisions (see docs/data-cleaning.md):
  1. Label source     -> train_v2.csv is canonical (latest churn window).
  2. Customer universe -> distinct msno that actually transact (~2.43M).
  3. Dirty-value policy -> null out-of-range ages, null+flag bad expiry dates,
                           keep+flag zero-day plans.

Outputs two tables:
  customers     one row per msno (PK), member profile + churn label where known.
  transactions  one row per billing event (FK -> customers), de-duplicated & typed.

Usage:
    python -m src.etl.clean
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import get_engine  # noqa: E402

# Validity window for membership_expire_date. The raw field ranges from the 1970
# epoch placeholder to absurd far-future dates; anything outside this window is junk.
EXPIRE_MIN = "2015-01-01"
EXPIRE_MAX = "2018-12-31"

CUSTOMERS_SQL = f"""
DROP TABLE IF EXISTS transactions;     -- drop child first (FK) if re-running
DROP TABLE IF EXISTS customers;

CREATE TABLE customers AS
WITH universe AS (                      -- decision #2: transacting customers only
    SELECT DISTINCT msno FROM raw_transactions
),
label AS (                              -- decision #1: train_v2 is canonical
    SELECT msno, is_churn FROM raw_train WHERE _source_file = 'train_v2.csv'
)
SELECT
    u.msno,
    CASE WHEN m.city ~ '^[0-9]+$' THEN m.city::smallint END                       AS city,
    CASE WHEN m.bd ~ '^-?[0-9]+$' AND m.bd::int BETWEEN 1 AND 100
         THEN m.bd::smallint END                                                  AS bd_clean,
    NULLIF(m.gender, '')                                                          AS gender,
    CASE WHEN m.registered_via ~ '^[0-9]+$' THEN m.registered_via::smallint END   AS registered_via,
    CASE WHEN m.registration_init_time ~ '^[0-9]{{8}}$'
         THEN to_date(m.registration_init_time, 'YYYYMMDD') END                   AS registration_date,
    CASE WHEN l.is_churn IS NOT NULL THEN (l.is_churn = '1') END                  AS is_churn
FROM universe u
LEFT JOIN raw_members m ON m.msno = u.msno
LEFT JOIN label       l ON l.msno = u.msno;

ALTER TABLE customers ADD PRIMARY KEY (msno);
"""

TRANSACTIONS_SQL = f"""
CREATE TABLE transactions AS
WITH parsed AS (
    SELECT DISTINCT                                  -- step T1: drop exact-duplicate rows
        msno,
        payment_method_id::smallint   AS payment_method_id,
        payment_plan_days::smallint   AS payment_plan_days,
        plan_list_price::int          AS plan_list_price,
        actual_amount_paid::int       AS actual_amount_paid,
        (is_auto_renew = '1')         AS is_auto_renew,
        (is_cancel = '1')             AS is_cancel,
        to_date(transaction_date, 'YYYYMMDD')        AS transaction_date,
        to_date(membership_expire_date, 'YYYYMMDD')  AS exp_raw
    FROM raw_transactions
)
SELECT
    msno, payment_method_id, payment_plan_days, plan_list_price, actual_amount_paid,
    is_auto_renew, is_cancel, transaction_date,
    CASE WHEN exp_raw BETWEEN DATE '{EXPIRE_MIN}' AND DATE '{EXPIRE_MAX}'
         THEN exp_raw END                                          AS membership_expire_date,
    (exp_raw BETWEEN DATE '{EXPIRE_MIN}' AND DATE '{EXPIRE_MAX}')  AS expire_date_valid,
    (payment_plan_days > 0)                                        AS plan_days_valid
FROM parsed;

ALTER TABLE transactions
    ADD CONSTRAINT fk_tx_customer FOREIGN KEY (msno) REFERENCES customers(msno);

CREATE INDEX ix_tx_msno        ON transactions(msno);
CREATE INDEX ix_tx_txn_date    ON transactions(transaction_date);
CREATE INDEX ix_tx_expire_date ON transactions(membership_expire_date);
"""


def run_sql_script(engine, label: str, script: str) -> None:
    """Execute a multi-statement SQL script in one transaction."""
    print(f"[clean] {label} ...", flush=True)
    with engine.begin() as conn:
        for stmt in (s.strip() for s in script.split(";")):
            if stmt:
                conn.execute(text(stmt))
    print(f"[clean] {label} done.", flush=True)


def validate(engine) -> bool:
    """Run post-build checks; return True if all pass."""
    checks: list[tuple[str, bool, str]] = []
    with engine.connect() as c:
        def scalar(sql: str):
            return c.execute(text(sql)).scalar_one()

        cust = scalar("SELECT COUNT(*) FROM customers")
        uni = scalar("SELECT COUNT(DISTINCT msno) FROM raw_transactions")
        checks.append(("customers count = distinct transacting msno", cust == uni, f"{cust:,} vs {uni:,}"))

        pk_dupes = scalar("SELECT COUNT(*) - COUNT(DISTINCT msno) FROM customers")
        checks.append(("customers.msno unique (PK)", pk_dupes == 0, f"dupes={pk_dupes}"))

        tx = scalar("SELECT COUNT(*) FROM transactions")
        raw_tx = scalar("SELECT COUNT(*) FROM raw_transactions")
        checks.append(("transactions de-duplicated", tx < raw_tx, f"{tx:,} (raw {raw_tx:,}, removed {raw_tx - tx:,})"))

        orphans = scalar("SELECT COUNT(*) FROM transactions t LEFT JOIN customers c ON c.msno=t.msno WHERE c.msno IS NULL")
        checks.append(("0 FK orphans", orphans == 0, f"orphans={orphans}"))

        bad_age = scalar("SELECT COUNT(*) FROM customers WHERE bd_clean IS NOT NULL AND bd_clean NOT BETWEEN 1 AND 100")
        checks.append(("bd_clean within 1..100 or NULL", bad_age == 0, f"violations={bad_age}"))

        bad_gender = scalar("SELECT COUNT(*) FROM customers WHERE gender IS NOT NULL AND gender NOT IN ('male','female')")
        checks.append(("gender in {male,female,NULL}", bad_gender == 0, f"violations={bad_gender}"))

        # Informational metrics (not pass/fail).
        labeled = scalar("SELECT COUNT(*) FROM customers WHERE is_churn IS NOT NULL")
        churn_rate = c.execute(text(
            "SELECT ROUND(100.0*AVG(CASE WHEN is_churn THEN 1 ELSE 0 END),2) FROM customers WHERE is_churn IS NOT NULL")).scalar_one()
        bad_expiry = scalar("SELECT COUNT(*) FROM transactions WHERE NOT expire_date_valid")
        zero_days = scalar("SELECT COUNT(*) FROM transactions WHERE NOT plan_days_valid")

    print("\n[clean] === validation ===")
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  ({detail})")
        ok = ok and passed

    print("\n[clean] === metrics ===")
    print(f"  labeled customers : {labeled:,}  (churn rate {churn_rate}%)")
    print(f"  flagged bad expiry: {bad_expiry:,}")
    print(f"  flagged 0-day plan: {zero_days:,}")
    return ok


def main() -> None:
    engine = get_engine()
    run_sql_script(engine, "build customers", CUSTOMERS_SQL)
    run_sql_script(engine, "build transactions", TRANSACTIONS_SQL)
    if not validate(engine):
        raise SystemExit("[clean] VALIDATION FAILED — see checks above.")
    print("\n[clean] OK — clean schema built and validated.")


if __name__ == "__main__":
    main()
