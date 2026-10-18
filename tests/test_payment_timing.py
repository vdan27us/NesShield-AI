
import pandas as pd

from backend.ml.payment_timing import (
    estimate_baseline_delay,
    get_timing_features,
    prepare_timing_dataset,
)


def test_calculates_actual_settlement_delay():
    data = pd.DataFrame({
        "scheduled_date": ["2026-10-10", "2026-10-12"],
        "actual_settlement_date": ["2026-10-12", "2026-10-12"],
        "amount": [100.0, 50.0],
    })

    prepared, audit = prepare_timing_dataset(data)

    assert prepared["settlement_delay_days"].tolist() == [2, 0]
    assert audit.valid_rows == 2
    assert audit.rejected_rows == 0


def test_rejects_missing_required_columns():
    prepared, audit = prepare_timing_dataset(
        pd.DataFrame({"scheduled_date": ["2026-10-10"]})
    )

    assert prepared.empty
    assert audit.valid_rows == 0
    assert audit.rejected_rows == 1
    assert "actual_settlement_date" in audit.missing_columns


def test_rejects_invalid_dates_and_negative_delays():
    data = pd.DataFrame({
        "scheduled_date": [
            "2026-10-10", "not-a-date", "2026-10-12"
        ],
        "actual_settlement_date": [
            "2026-10-12", "2026-10-12", "2026-10-10"
        ],
    })

    prepared, audit = prepare_timing_dataset(data)

    assert prepared["settlement_delay_days"].tolist() == [2]
    assert audit.valid_rows == 1
    assert audit.rejected_rows == 2


def test_feature_selection_excludes_target():
    data = pd.DataFrame({
        "amount": [100.0],
        "transaction_type": ["deposit"],
        "settlement_delay_days": [2],
    })

    assert list(get_timing_features(data).columns) == [
        "amount", "transaction_type"
    ]


def test_baseline_unavailable_with_insufficient_history():
    data = pd.DataFrame({
        "scheduled_date": ["2026-10-10", "2026-10-11"],
        "actual_settlement_date": ["2026-10-12", "2026-10-12"],
    })

    result = estimate_baseline_delay(data)

    assert result["status"] == "unavailable"
    assert result["estimated_delay_days"] is None
    assert result["observations"] == 2


def test_baseline_uses_median_of_verified_delays():
    data = pd.DataFrame({
        "scheduled_date": [
            "2026-10-10", "2026-10-10", "2026-10-10"
        ],
        "actual_settlement_date": [
            "2026-10-11", "2026-10-12", "2026-10-14"
        ],
    })

    result = estimate_baseline_delay(data)

    assert result["status"] == "available"
    assert result["estimated_delay_days"] == 2.0
    assert result["observations"] == 3
