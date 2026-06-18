# Phase 3 — Business Metrics & Churn Model: Methodology

> Explains the economic metrics (MRR / ARPU / LTV / CAC) and the churn model — the
> definitions, the **leak-free** design, and the evidence behind each choice. Companion to
> [`docs/data-cleaning.md`](data-cleaning.md).
>
> **Status:** ✅ done · 🔜 planned · ⏳ needs your input

---

## 1. The single most important decision: a leak-free "as-of" date

A churn model is only valid if its features use **no information from after the prediction
point**. Using the renewal transaction that *defines* the label would inflate accuracy to
a meaningless ~100%.

**Evidence (from our `train_v2` labeled customers):**
- Transaction data spans **2015-01-01 … 2017-03-31**.
- Their `membership_expire_date` peaks in **March 2017** (1,023,819) then drops off sharply
  after April 2017.
- This matches the official KKBox `train_v2` definition: predict churn (no renewal within 30
  days of expiry) for memberships **expiring in March 2017**.

**Decision ▶ Feature cutoff = `2017-02-28`.** Every feature is computed from transactions with
`transaction_date <= 2017-02-28` (i.e. 2015-01 → 2017-02). All March-2017 activity — which
contains the label-determining renewal/non-renewal — is excluded. One consistent "as-of"
snapshot date for both training and scoring.

*Churn definition (KKBox):* `is_churn = 1` ⟺ no valid new subscription within 30 days after
the membership expires. Sources: [Kaggle competition](https://www.kaggle.com/c/kkbox-churn-prediction-challenge),
[WSDM write-up](https://asad-99rizvi.medium.com/wsdm-kkboxs-churn-prediction-challenge-d7c9cfa21cbd).

---

## 2. Economic metrics — definitions & evidence

### 2.1 Monthly-equivalent value (the MRR building block)
Plans range from 7 to 410 days, so raw price isn't comparable. We normalize every paid
subscription to a 30-day-equivalent:

```
monthly_value = actual_amount_paid / payment_plan_days * 30      (payment_plan_days > 0)
```

**Why this is sound (evidence):** the per-month rate is stable across plan lengths —
30-day plans ≈ 131, 410-day plans ≈ 1770/410×30 ≈ 130. The 872,339 `0-day` plans are
excluded (division by zero; already flagged `plan_days_valid = FALSE`).

### 2.2 Headline metrics
| Metric | Definition | Notes |
|---|---|---|
| **MRR** (snapshot) | Σ `monthly_value` of each customer's **active** subscription as of `2017-02-28` | "active" = `transaction_date ≤ cutoff < membership_expire_date`; one (latest) per customer |
| **Active customers** | distinct customers with an active subscription at the cutoff | denominator for ARPU |
| **ARPU** | MRR ÷ active customers | average monthly revenue per user |
| **Monthly churn rate** | from the `train_v2` label = **8.99%** | 30-day churn for the target cohort |
| **Avg lifetime** | `1 / churn_rate` ≈ **11.1 months** | geometric-survival approximation |
| **LTV** | `ARPU × avg_lifetime` = `ARPU / churn_rate` | per-customer lifetime value |

*(The full **monthly MRR time series / rolling MRR / cohort retention** belongs to Phase 5 —
that's exactly what its window-function SQL is for. Here we compute the as-of snapshot.)*

### 2.3 CAC — an honest limitation ⏳
**CAC (Customer Acquisition Cost) cannot be computed from this dataset** — there is no
marketing-spend or acquisition-channel-cost data. Rather than fabricate it, the options are:

- **▶ Option A** — present **LTV** on its own, and show **LTV : CAC** as a *parameterized*
  scenario with an explicitly-labelled assumed CAC (e.g. "at a CAC of \$X, LTV:CAC = …").
- Option B — omit CAC entirely and note the data gap.

*Needs your call (see §5).*

---

## 3. Feature engineering 🔜 (as-of `2017-02-28`)

Per-customer features, all derived from transactions **on/before the cutoff**, plus member
profile:

| Group | Features |
|---|---|
| **Tenure / recency** | days since first transaction, days since last transaction, # transactions |
| **Plan behavior** | avg/last `payment_plan_days`, avg/last price, avg discount (`list − paid`), # distinct plans |
| **Payment** | # distinct `payment_method_id`, most-used method |
| **Auto-renew / cancel** | share auto-renew, # cancels, ever-cancelled flag |
| **Revenue** | total paid, avg `monthly_value`, # zero-paid (promo) months |
| **Profile** | `bd_clean`, `gender`, `city`, `registered_via`, account age from `registration_date` |

Output: a `customer_features` table keyed by `msno`.

---

## 4. Model 🔜

- **Algorithm:** Scikit-Learn **Random Forest** (roadmap baseline; handles mixed
  numeric/categorical, robust, gives feature importances an analyst can narrate).
- **Training set:** the 970,960 labeled (`train_v2`) customers, features as-of cutoff.
- **Split:** stratified train/validation (e.g. 80/20) on `is_churn` (8.99% positive →
  use `class_weight`/stratification).
- **Evaluation:** ROC-AUC, PR-AUC, precision/recall, confusion matrix at a chosen threshold.
- **Calibration:** calibrate probabilities (isotonic/sigmoid) so the score is meaningful.
- **1–100 Churn Risk Score:** `round(1 + 99 × calibrated_prob)`, written to
  `customer_risk_scores(msno, churn_prob, risk_score, scored_at)`.

---

## 5. Open decisions ⏳
1. **CAC handling** — Option A (parameterized LTV:CAC, recommended) vs Option B (omit).
2. Confirm the **`2017-02-28` leak-free cutoff** (strongly recommended; the model's validity
   depends on it).

---

## 6. Execution results

### 6.1 Economic metrics ✅ (`python -m src.analytics.metrics`, as of 2017-02-28)
| Metric | Value |
|---|---|
| Active customers | 1,152,743 |
| **MRR** | **NT$ 147,593,251 / month** |
| ARPU | NT$ 128.04 / customer / month |
| Monthly churn rate | 8.99% |
| Avg customer lifetime | 11.1 months |
| **LTV** (ARPU ÷ churn) | **NT$ 1,424 / customer** |
| Annualized recurring revenue | NT$ 1.77B (MRR × 12) |

Sanity check: ARPU (128.04) ≈ the ~130/month per-plan rate from profiling — normalization
holds. Reusable view `v_subscription_value` created for Phase 5 BI.

### 6.2 Feature engineering ✅ (`python -m src.ml.features`)
`customer_features`: **2,391,675** customers × 27 columns, **968,436 labeled**. Every
feature derived from transactions `<= 2017-02-28` (leak-free) + static profile.

### 6.3 Model ✅ (`python -m src.ml.train_model`)
Random Forest (200 trees, `max_depth=18`, `class_weight=balanced_subsample`) on a 60/20/20
fit/calibrate/test split; isotonic-calibrated probabilities.

**Held-out test performance:**
| Metric | Value |
|---|---|
| ROC-AUC | **0.907** |
| PR-AUC | 0.629 (baseline = 0.089 churn rate → ~7× lift) |
| Precision / Recall (churn @0.5) | 0.739 / 0.435 |
| Accuracy | 0.936 |

**Top churn drivers (feature importance) — all business-explainable:**
`last_auto_renew` (0.155) · `days_to_expiry` (0.138) · `auto_renew_share` (0.105) ·
`last_is_cancel` (0.072) · `recency_days` (0.065) · `avg_paid` (0.055). → *Whether the
customer's last subscription had auto-renew on, how soon it expires, and their cancel
history dominate.*

**Score calibration (the real validation)** — actual churn by 1–100 risk band, on labeled
customers:

| Risk band | n | Actual churn |
|---|---|---|
| 1–10 | 809,389 | 2.2% |
| 41–50 | 15,444 | 49.6% |
| 71–80 | 10,082 | 76.5% |
| 91–100 | 10,122 | **94.8%** |

Monotonic and well-calibrated — the score reads ≈ churn probability. All **2,391,675**
customers scored into `customer_risk_scores(msno, churn_prob, risk_score, scored_at)`.
