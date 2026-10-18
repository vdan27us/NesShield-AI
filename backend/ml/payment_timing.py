
"""Payment-timing data validation and baseline estimation.

Actual settlement outcomes are required for historical delay estimates.
This module does not manufacture labels or claim ML prediction accuracy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


REQUIRED_COLUMNS = {
    "scheduled_date",
    "actual_settlement_date",
}

MINIMUM_BASELINE_OBSERVATIONS = 3


@dataclass(frozen=True)
class TimingDataAudit:
    total_rows: int
    valid_rows: int
    rejected_rows: int
    missing_columns: tuple[str, ...]
    messages: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def prepare_timing_dataset(
    data: pd.DataFrame,
) -> tuple[pd.DataFrame, TimingDataAudit]:
    """Validate real scheduled and actual settlement dates."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")

    missing = tuple(sorted(REQUIRED_COLUMNS - set(data.columns)))

    if missing:
        return pd.DataFrame(), TimingDataAudit(
            total_rows=len(data),
            valid_rows=0,
            rejected_rows=len(data),
            missing_columns=missing,
            messages=(
                "Verified scheduled and actual settlement dates are required.",
                "No training rows were accepted.",
            ),
        )

    prepared = data.copy()

    for column in REQUIRED_COLUMNS:
        prepared[column] = pd.to_datetime(
            prepared[column],
            errors="coerce",
            utc=True,
        ).dt.normalize()

    delay = (
        prepared["actual_settlement_date"]
        - prepared["scheduled_date"]
    ).dt.total_seconds() / 86400

    prepared["settlement_delay_days"] = delay

    valid = (
        prepared["scheduled_date"].notna()
        & prepared["actual_settlement_date"].notna()
        & prepared["settlement_delay_days"].ge(0)
    )

    rejected = int((~valid).sum())
    prepared = prepared.loc[valid].copy()
    prepared["settlement_delay_days"] = (
        prepared["settlement_delay_days"].astype(int)
    )

    messages = [
        "Delays were calculated from supplied settlement-date labels.",
        "Date labels must represent verified actual settlement.",
    ]

    if rejected:
        messages.append(f"Rejected {rejected} invalid row(s).")

    audit = TimingDataAudit(
        total_rows=len(data),
        valid_rows=len(prepared),
        rejected_rows=rejected,
        missing_columns=(),
        messages=tuple(messages),
    )

    return prepared.reset_index(drop=True), audit


def get_timing_features(data: pd.DataFrame) -> pd.DataFrame:
    """Select available predictors without including the target."""
    columns = [
        name
        for name in ("amount", "transaction_type")
        if name in data.columns
    ]
    return data[columns].copy()


def estimate_baseline_delay(
    data: pd.DataFrame,
) -> dict:
    """Estimate delay from historical observations when sufficient.

    With fewer than three valid observations, returns an unavailable
    estimate instead of inventing a prediction.
    """
    prepared, audit = prepare_timing_dataset(data)

    result = {
        "method": "historical_median_baseline",
        "status": "unavailable",
        "estimated_delay_days": None,
        "observations": audit.valid_rows,
        "minimum_observations": MINIMUM_BASELINE_OBSERVATIONS,
        "audit": audit.to_dict(),
        "limitations": [
            "This is a baseline, not a trained ML model.",
            "Historical delays do not guarantee future payment timing.",
        ],
    }

    if audit.valid_rows < MINIMUM_BASELINE_OBSERVATIONS:
        result["reason"] = (
            "Insufficient verified settlement history."
        )
        return result

    result["status"] = "available"
    result["estimated_delay_days"] = float(
        prepared["settlement_delay_days"].median()
    )
    return result
