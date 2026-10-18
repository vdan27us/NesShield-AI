
import pytest

from backend.services.what_if import run_what_if_simulation


def run_example(**overrides):
    arguments = {
        "starting_balance": 10_000,
        "payroll_amount": 3_000,
        "deposit_amount": 2_000,
        "deposit_delay_days": 2,
        "safety_buffer": 5_000,
        "simulations": 500,
        "seed": 42,
    }
    arguments.update(overrides)
    return run_what_if_simulation(**arguments)


def test_what_if_preserves_three_value_return_contract():
    result = run_example()

    assert isinstance(result, tuple)
    assert len(result) == 3

    risk_metrics, forecast, ending_balance = result

    assert isinstance(risk_metrics, dict)
    assert isinstance(forecast, list)
    assert isinstance(ending_balance, float)


def test_what_if_forecast_has_fifteen_daily_points():
    _, forecast, _ = run_example()

    assert len(forecast) == 15
    assert forecast[0]["label"] == "Today"
    assert forecast[0]["day"] == 0
    assert forecast[-1]["day"] == 14


def test_what_if_deterministic_forecast_is_correct():
    _, forecast, ending_balance = run_example(
        starting_balance=10_000,
        deposit_amount=2_000,
        deposit_delay_days=2,
        payroll_amount=3_000,
    )

    # Deposit is added on day 2; payroll leaves on day 3.
    assert forecast[0]["projected_balance"] == 10_000
    assert forecast[1]["projected_balance"] == 10_000
    assert forecast[2]["projected_balance"] == 12_000
    assert forecast[3]["projected_balance"] == 9_000
    assert forecast[14]["projected_balance"] == 9_000
    assert ending_balance == 9_000.0


def test_what_if_results_are_reproducible():
    first = run_example()
    second = run_example()

    assert first == second


def test_what_if_exposes_risk_metrics():
    risk_metrics, _, _ = run_example()

    expected_keys = {
        "simulations",
        "horizon_days",
        "shortfall_probability",
        "safety_buffer_breach_probability",
        "ending_balance_p05",
        "ending_balance_median",
        "ending_balance_p95",
        "minimum_balance_p05",
        "expected_minimum_balance",
        "expected_ending_balance",
        "probability_of_breach_by_day",
        "time_to_first_buffer_breach",
        "assumptions",
    }

    assert expected_keys.issubset(risk_metrics.keys())
    assert risk_metrics["simulations"] == 500
    assert risk_metrics["horizon_days"] == 14


@pytest.mark.parametrize(
    "overrides",
    [
        {"deposit_delay_days": -1},
        {"deposit_delay_days": 8},
        {"payroll_amount": -1},
        {"deposit_amount": -1},
        {"safety_buffer": -1},
        {"simulations": 0},
    ],
)
def test_what_if_rejects_invalid_inputs(overrides):
    with pytest.raises(ValueError):
        run_example(**overrides)
