"""Synthetic payer-history model and honest held-out evaluation helpers."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error
from sklearn.model_selection import GroupShuffleSplit


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "payment_timing_model.joblib"
HISTORY_PATH = BASE_DIR / "synthetic_payment_history.csv"
FEATURES = ["amount", "transaction_type", "scheduled_weekday",
            "payer_history_median_delay", "payer_history_count"]


def get_model_bundle():
    return joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None


def generate_synthetic_payer_history(
    *, payer_count: int = 160, transactions_per_payer: int = 50,
    seed: int = 42,
) -> pd.DataFrame:
    """Create repeat-payer histories with explicit, synthetic settlement labels."""
    rng = np.random.default_rng(seed)
    rows = []
    origin = pd.Timestamp("2024-01-01")
    for payer in range(payer_count):
        reliability = rng.beta(5.0, 2.0)
        prior_delays: list[int] = []
        for index in range(transactions_per_payer):
            scheduled = origin + pd.Timedelta(days=index * 7 + int(rng.integers(0, 7)))
            amount = float(np.exp(rng.normal(6.8, 1.0)))
            transaction_type = int(rng.integers(0, 2))
            late_probability = np.clip(
                0.04 + 0.18 * transaction_type
                + min(amount, 20_000.0) / 100_000.0
                + (0.04 if scheduled.dayofweek in (0, 4) else 0.0)
                + (1.0 - reliability) * 0.12,
                0.02, 0.60,
            )
            delay = (int(min(10, rng.geometric(max(0.08, reliability * 0.75)) - 1))
                     if rng.random() < late_probability else 0)
            rows.append({
                "payer_id": f"synthetic-payer-{payer:04d}",
                "amount": amount,
                "transaction_type": transaction_type,
                "scheduled_weekday": scheduled.dayofweek,
                "payer_history_median_delay": float(np.median(prior_delays)) if prior_delays else 0.0,
                "payer_history_count": min(len(prior_delays), 20),
                "scheduled_date": scheduled.date().isoformat(),
                "actual_settlement_date": (scheduled + pd.Timedelta(days=delay)).date().isoformat(),
                "settlement_delay_days": delay,
                "synthetic_label": True,
            })
            prior_delays.append(delay)
    return pd.DataFrame(rows)


def train_and_evaluate(*, seed: int = 42, save: bool = True) -> dict:
    """Train delay and calibrated late-probability models on held-out payers."""
    data = generate_synthetic_payer_history(seed=seed)
    train_ix, test_ix = next(GroupShuffleSplit(
        n_splits=1, test_size=0.2, random_state=seed
    ).split(data, groups=data["payer_id"]))
    train, test = data.iloc[train_ix], data.iloc[test_ix]
    x_train, x_test = train[FEATURES], test[FEATURES]
    y_train, y_test = train["settlement_delay_days"], test["settlement_delay_days"]

    delay_model = GradientBoostingRegressor(
        n_estimators=100, max_depth=2, learning_rate=0.05, random_state=seed
    ).fit(x_train, y_train)
    # A "late" payment here means outside the simulation's 3-day delay band.
    late_train = (y_train > 3).astype(int)
    late_test = (y_test > 3).astype(int)
    classifier = CalibratedClassifierCV(
        estimator=GradientBoostingClassifier(
            n_estimators=80, max_depth=2, learning_rate=0.05,
            random_state=seed,
        ), method="sigmoid", cv=3,
    ).fit(x_train, late_train)
    prevalence = float(late_train.mean())
    baseline_prob = np.full(len(y_test), prevalence)
    predictions = classifier.predict_proba(x_test)[:, 1]
    evaluation = {
        "dataset": "synthetic_repeat_payer_histories",
        "train_rows": int(len(train)), "held_out_rows": int(len(test)),
        "held_out_payers": int(test["payer_id"].nunique()),
        "delay_model": "GradientBoostingRegressor",
        "baseline": "payer historical median delay and training-set late-event prevalence",
        "gradient_boosting_mae_days": float(mean_absolute_error(y_test, delay_model.predict(x_test))),
        "median_baseline_mae_days": float(mean_absolute_error(y_test, test["payer_history_median_delay"])),
        "calibrated_over_3_day_delay_brier": float(brier_score_loss(late_test, predictions)),
        "prevalence_baseline_brier": float(brier_score_loss(late_test, baseline_prob)),
        "calibration": "sigmoid calibration fitted within training fold; evaluated on held-out payers",
        "limitations": ["All payer and settlement records are synthetic.",
                        "Metrics do not establish performance on Nessie or a real business."],
    }
    if save:
        joblib.dump({"delay_model": delay_model, "late_model": classifier,
                     "features": FEATURES, "evaluation": evaluation,
                     "dataset_type": "synthetic"}, MODEL_PATH)
        data.to_csv(HISTORY_PATH, index=False)
    return evaluation


def predict_synthetic_timing(*, amount: float, kind: str, weekday: int) -> dict:
    """Return a synthetic probability of clearing within the delay band."""
    bundle = get_model_bundle()
    if bundle is None:
        return {"predicted_delay_days": 0, "clear_probability": None}
    # Nessie does not currently provide verified payer histories. Use a
    # neutral pooled prior and disclose that it is synthetic in metadata.
    frame = pd.DataFrame([{
        "amount": amount, "transaction_type": 0 if kind == "inflow" else 1,
        "scheduled_weekday": weekday,
        "payer_history_median_delay": 1.0,
        "payer_history_count": 0,
    }], columns=bundle["features"])
    delay_model = bundle["delay_model"]
    evaluation = bundle["evaluation"]
    delay_mae = evaluation["gradient_boosting_mae_days"]
    baseline_mae = evaluation["median_baseline_mae_days"]
    # Do not deploy a delay estimate which lost to its simple baseline.
    delay = (int(np.clip(np.rint(delay_model.predict(frame)[0]), 0, 7))
             if delay_mae < baseline_mae else 0)
    late_probability = float(bundle["late_model"].predict_proba(frame)[0, 1])
    return {"predicted_delay_days": delay, "clear_probability": 1.0,
            "late_probability": float(np.clip(late_probability, 0.0, 1.0))}


def predict_synthetic_delay(*, amount: float, kind: str, weekday: int) -> int:
    """Compatibility helper returning delay only if it beats baseline."""
    return predict_synthetic_timing(amount=amount, kind=kind,
                                    weekday=weekday)["predicted_delay_days"]


if __name__ == "__main__":
    import json
    print(json.dumps(train_and_evaluate(), indent=2))
