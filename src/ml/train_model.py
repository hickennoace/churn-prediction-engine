"""Phase 3 — train the churn model and write 1-100 risk scores.

Trains a Scikit-Learn Random Forest on the labeled (train_v2) customers using the
leak-free `customer_features` (as of 2017-02-28), calibrates probabilities, evaluates,
then scores the full customer base into `customer_risk_scores`.

Usage:
    python -m src.ml.train_model
"""
from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import get_engine  # noqa: E402

NUMERIC = [
    "bd_clean", "account_age_days", "n_tx", "tenure_days", "recency_days",
    "avg_plan_days", "avg_paid", "avg_discount", "n_distinct_plans", "n_payment_methods",
    "auto_renew_share", "n_cancels", "ever_cancelled", "total_paid", "n_promo_tx",
    "avg_monthly_value", "last_plan_days", "last_paid", "last_auto_renew",
    "last_is_cancel", "days_to_expiry",
]
CATEGORICAL = ["gender", "city", "registered_via", "last_payment_method"]
FEATURES = NUMERIC + CATEGORICAL
SEED = 42


def _prep_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Cast categoricals to clean strings so the encoder handles them + missing."""
    for col in CATEGORICAL:
        df[col] = df[col].astype("string").fillna("NA")
    return df


def build_pipeline() -> Pipeline:
    pre = ColumnTransformer([
        ("num", SimpleImputer(strategy="median", add_indicator=True), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), CATEGORICAL),
    ])
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=18, min_samples_leaf=50,
        class_weight="balanced_subsample", n_jobs=-1, random_state=SEED,
    )
    return Pipeline([("pre", pre), ("rf", rf)])


def main() -> None:
    engine = get_engine()

    print("[train] loading labeled features ...", flush=True)
    labeled = pd.read_sql(
        f"SELECT is_churn, {', '.join(FEATURES)} FROM customer_features WHERE is_churn IS NOT NULL",
        engine,
    )
    labeled = _prep_frame(labeled)
    y = labeled["is_churn"].astype(int)
    X = labeled[FEATURES]
    print(f"[train] {len(X):,} labeled rows, churn rate {y.mean()*100:.2f}%")

    # train / calibration / test split (60/20/20), stratified.
    X_fit, X_tmp, y_fit, y_tmp = train_test_split(X, y, test_size=0.40, stratify=y, random_state=SEED)
    X_cal, X_test, y_cal, y_test = train_test_split(X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=SEED)

    print("[train] fitting Random Forest ...", flush=True)
    pipe = build_pipeline()
    pipe.fit(X_fit, y_fit)

    print("[train] calibrating (isotonic) ...", flush=True)
    cal = CalibratedClassifierCV(pipe, method="isotonic", cv="prefit")
    cal.fit(X_cal, y_cal)

    # evaluation on held-out test.
    p_test = cal.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, p_test)
    ap = average_precision_score(y_test, p_test)
    preds = (p_test >= 0.5).astype(int)
    print("\n[train] === evaluation (held-out test) ===")
    print(f"  ROC-AUC : {auc:.4f}")
    print(f"  PR-AUC  : {ap:.4f}  (baseline = churn rate {y_test.mean():.4f})")
    print("  confusion matrix [ [TN FP] [FN TP] ] @0.5:")
    print("   ", confusion_matrix(y_test, preds).tolist())
    print(classification_report(y_test, preds, digits=3))

    # feature importances (map back through the preprocessor).
    rf = pipe.named_steps["rf"]
    names = pipe.named_steps["pre"].get_feature_names_out()
    imp = sorted(zip(names, rf.feature_importances_), key=lambda t: -t[1])[:15]
    print("[train] === top 15 features ===")
    for name, val in imp:
        print(f"  {val:.4f}  {name}")

    # score the FULL customer base in chunks (memory-friendly).
    print("\n[train] scoring full customer base ...", flush=True)
    with engine.begin() as conn:
        conn.execute(_t("DROP TABLE IF EXISTS customer_risk_scores"))
        conn.execute(_t(
            "CREATE TABLE customer_risk_scores ("
            " msno TEXT PRIMARY KEY REFERENCES customers(msno),"
            " churn_prob DOUBLE PRECISION, risk_score SMALLINT,"
            " scored_at TIMESTAMP NOT NULL)"
        ))

    scored_at = datetime.now().isoformat(sep=" ", timespec="seconds")
    raw = engine.raw_connection()
    total = 0
    try:
        cur = raw.cursor()
        for chunk in pd.read_sql(f"SELECT msno, {', '.join(FEATURES)} FROM customer_features", engine, chunksize=400_000):
            chunk = _prep_frame(chunk)
            prob = cal.predict_proba(chunk[FEATURES])[:, 1]
            score = np.round(1 + 99 * prob).astype(int)
            buf = io.StringIO()
            out = pd.DataFrame({"msno": chunk["msno"], "churn_prob": prob, "risk_score": score})
            out["scored_at"] = scored_at
            out.to_csv(buf, index=False, header=False)
            buf.seek(0)
            cur.copy_expert(
                "COPY customer_risk_scores (msno, churn_prob, risk_score, scored_at) FROM STDIN WITH (FORMAT csv)",
                buf,
            )
            total += len(out)
            print(f"  scored {total:,} ...", flush=True)
        raw.commit()
    finally:
        raw.close()

    with engine.connect() as c:
        dist = c.execute(_t(
            "SELECT width_bucket(risk_score,1,101,10) b, COUNT(*) n, MIN(risk_score), MAX(risk_score)"
            " FROM customer_risk_scores GROUP BY b ORDER BY b")).fetchall()
    print(f"\n[train] wrote {total:,} risk scores. Distribution by 10-point band:")
    for b, n, lo, hi in dist:
        print(f"  band {b:>2} (score {lo}-{hi}): {n:,}")
    print("\n[train] OK — model trained, evaluated, and full base scored.")


def _t(sql: str):
    from sqlalchemy import text
    return text(sql)


if __name__ == "__main__":
    main()
