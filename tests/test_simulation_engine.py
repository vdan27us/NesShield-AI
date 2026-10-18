
import numpy as np
import pytest

from backend.quant.simulation_engine import (
    SimulationEvent,
    generate_random_shocks,
    simulate_cashflows,
)


def test_no_events_preserve_starting_balance():
    result = simulate_cashflows(
        starting_balance=1_000,
        events=[],
        horizon_days=7,
        simulations=100,
    )

    assert result["expected_ending_balance"] == pytest.approx(1_000)
    assert result["expected_minimum_balance"] == pytest.approx(1_000)
    assert result["shortfall_probability"] == 0.0
    assert result["safety_buffer_breach_probability"] == 1.0
    assert result["time_to_first_buffer_breach"]["breach_probability"] == 1.0


def test_certain_outflow_reduces_balance():
    events = [
        SimulationEvent(
            day=1,
            kind="outflow",
            amount=200,
            event_id="rent",
        )
    ]

    result = simulate_cashflows(
        starting_balance=1_000,
        events=events,
        horizon_days=2,
        simulations=100,
        max_outflow_uplift=0,
    )

    assert result["expected_ending_balance"] == pytest.approx(800)
    assert result["expected_minimum_balance"] == pytest.approx(800)
    assert result["shortfall_probability"] == 0.0


def test_certain_inflow_increases_balance_when_it_arrives():
    events = [
        SimulationEvent(
            day=1,
            kind="inflow",
            amount=500,
            event_id="paycheck",
        )
    ]

    result = simulate_cashflows(
        starting_balance=1_000,
        events=events,
        horizon_days=4,
        simulations=100,
        inflow_clear_probability=1.0,
        max_inflow_delay_days=0,
        max_outflow_uplift=0,
    )

    assert result["expected_ending_balance"] == pytest.approx(1_500)
    assert result["expected_minimum_balance"] == pytest.approx(1_000)


def test_simulation_is_reproducible_with_same_seed():
    events = [
        SimulationEvent(0, "inflow", 500, "deposit"),
        SimulationEvent(1, "outflow", 300, "bill"),
    ]

    first = simulate_cashflows(
        starting_balance=1_000,
        events=events,
        horizon_days=4,
        simulations=1_000,
        seed=123,
    )

    second = simulate_cashflows(
        starting_balance=1_000,
        events=events,
        horizon_days=4,
        simulations=1_000,
        seed=123,
    )

    assert first == second


def test_invalid_event_amount_is_rejected():
    events = [
        SimulationEvent(
            day=1,
            kind="outflow",
            amount=-100,
            event_id="invalid-bill",
        )
    ]

    with pytest.raises(ValueError, match="amount"):
        simulate_cashflows(
            starting_balance=1_000,
            events=events,
            simulations=10,
        )


def test_invalid_event_day_is_rejected():
    events = [
        SimulationEvent(
            day=-1,
            kind="inflow",
            amount=100,
            event_id="invalid-date",
        )
    ]

    with pytest.raises(ValueError, match="day"):
        simulate_cashflows(
            starting_balance=1_000,
            events=events,
            simulations=10,
        )


def test_payment_delay_changes_shortfall_probability():
    """
    Starting balance: $1,000.
    Day-zero deposit: $5,000.
    Day-one payment: $3,000.

    The deposit clears with probability 0.70. Its delay is
    uniformly distributed from day 0 through day 3.

    A cleared deposit arrives by day one when its delay is 0 or 1,
    which happens in 2 of 4 equally likely cases. Otherwise, the
    day-one payment causes a shortfall.

    Expected shortfall probability:
        0.30 + (0.70 * 0.50) = 0.65
    """
    events = [
        SimulationEvent(
            day=0,
            kind="inflow",
            amount=5_000,
            event_id="large-deposit",
        ),
        SimulationEvent(
            day=1,
            kind="outflow",
            amount=3_000,
            event_id="large-payment",
        ),
    ]

    result = simulate_cashflows(
        starting_balance=1_000,
        events=events,
        horizon_days=4,
        simulations=50_000,
        seed=123,
        inflow_clear_probability=0.70,
        max_inflow_delay_days=3,
        max_outflow_uplift=0,
        safety_buffer=0,
    )

    assert result["shortfall_probability"] == pytest.approx(
        0.65, abs=0.015
    )


def test_inflow_delayed_beyond_horizon_is_not_counted():
    events = [
        SimulationEvent(
            day=0,
            kind="inflow",
            amount=5_000,
            event_id="late-deposit",
        )
    ]

    shocks = {
        "late-deposit": {
            "clear_uniform": np.zeros(10),
            "delay_days": np.full(10, 3),
            "outflow_uplift": np.zeros(10),
        }
    }

    result = simulate_cashflows(
        starting_balance=100,
        events=events,
        horizon_days=2,
        simulations=10,
        inflow_clear_probability=1.0,
        max_inflow_delay_days=3,
        max_outflow_uplift=0,
        random_shocks=shocks,
    )

    assert result["expected_ending_balance"] == pytest.approx(100)


def test_random_shocks_are_stable_by_event_id_when_events_reordered():
    event_a = SimulationEvent(0, "inflow", 500, "deposit-A")
    event_b = SimulationEvent(1, "outflow", 200, "bill-B")

    first = generate_random_shocks(
        events=[event_a, event_b],
        simulations=100,
        seed=42,
    )

    reordered = generate_random_shocks(
        events=[event_b, event_a],
        simulations=100,
        seed=42,
    )

    for event_id in ("deposit-A", "bill-B"):
        for shock_name in (
            "clear_uniform",
            "delay_days",
            "outflow_uplift",
        ):
            np.testing.assert_array_equal(
                first[event_id][shock_name],
                reordered[event_id][shock_name],
            )


def test_same_random_shocks_can_be_reused_across_scenarios():
    original_events = [
        SimulationEvent(0, "inflow", 500, "deposit-A"),
        SimulationEvent(1, "outflow", 200, "bill-B"),
    ]

    modified_events = [
        SimulationEvent(0, "inflow", 900, "deposit-A"),
        SimulationEvent(1, "outflow", 200, "bill-B"),
    ]

    shocks = generate_random_shocks(
        events=original_events,
        simulations=1_000,
        seed=42,
    )

    first = simulate_cashflows(
        starting_balance=1_000,
        events=original_events,
        horizon_days=4,
        simulations=1_000,
        random_shocks=shocks,
    )

    second = simulate_cashflows(
        starting_balance=1_000,
        events=modified_events,
        horizon_days=4,
        simulations=1_000,
        random_shocks=shocks,
    )

    assert (
        first["ending_balance_median"]
        != second["ending_balance_median"]
    )


def test_duplicate_simulation_event_ids_are_rejected():
    events = [
        SimulationEvent(0, "inflow", 100, "duplicate"),
        SimulationEvent(1, "outflow", 50, "duplicate"),
    ]

    with pytest.raises(ValueError, match="Duplicate"):
        simulate_cashflows(
            starting_balance=1_000,
            events=events,
            simulations=10,
        )


def test_breach_probability_is_reported_for_each_day():
    events = [
        SimulationEvent(
            day=1,
            kind="outflow",
            amount=200,
            event_id="bill",
        )
    ]

    result = simulate_cashflows(
        starting_balance=100,
        events=events,
        horizon_days=2,
        simulations=100,
        safety_buffer=0,
        max_outflow_uplift=0,
    )

    daily = result["probability_of_breach_by_day"]

    assert set(daily.keys()) == {0, 1, 2}
    assert daily[0] == 0.0
    assert daily[1] == 1.0
    assert daily[2] == 1.0


def test_invalid_simulation_count_is_rejected():
    with pytest.raises(ValueError, match="simulations"):
        simulate_cashflows(
            starting_balance=1_000,
            events=[],
            simulations=0,
        )


def test_risk_metrics_include_var_cvar_and_shortfall_severity():
    events = [
        SimulationEvent(
            day=1,
            kind="outflow",
            amount=2_000,
            event_id="large-payment",
        )
    ]

    result = simulate_cashflows(
        starting_balance=1_000,
        events=events,
        horizon_days=2,
        simulations=1_000,
        safety_buffer=0,
        max_outflow_uplift=0,
    )

    metrics = result["risk_metrics"]

    assert metrics["confidence_level"] == pytest.approx(0.95)
    assert metrics["ending_balance_var_95"] == pytest.approx(-1_000)
    assert metrics["ending_balance_cvar_95"] == pytest.approx(-1_000)
    assert metrics["minimum_balance_var_95"] == pytest.approx(-1_000)
    assert metrics["minimum_balance_cvar_95"] == pytest.approx(-1_000)
    assert metrics["expected_shortfall_severity"] == pytest.approx(1_000)
    assert metrics["shortfall_path_count"] == 1_000


def test_daily_balance_percentiles_cover_every_day():
    events = [
        SimulationEvent(
            day=1,
            kind="outflow",
            amount=200,
            event_id="bill",
        )
    ]

    result = simulate_cashflows(
        starting_balance=1_000,
        events=events,
        horizon_days=3,
        simulations=100,
        max_outflow_uplift=0,
    )

    daily = result["daily_balance_percentiles"]

    assert set(daily.keys()) == {0, 1, 2, 3}

    assert daily[0]["p05"] == pytest.approx(1_000)
    assert daily[0]["p50"] == pytest.approx(1_000)
    assert daily[0]["p95"] == pytest.approx(1_000)

    assert daily[1]["p05"] == pytest.approx(800)
    assert daily[1]["p50"] == pytest.approx(800)
    assert daily[1]["p95"] == pytest.approx(800)


def test_shortfall_severity_is_none_when_no_path_goes_negative():
    result = simulate_cashflows(
        starting_balance=10_000,
        events=[
            SimulationEvent(
                day=1,
                kind="outflow",
                amount=100,
                event_id="small-bill",
            )
        ],
        horizon_days=2,
        simulations=100,
        safety_buffer=5_000,
        max_outflow_uplift=0,
    )

    metrics = result["risk_metrics"]

    assert metrics["shortfall_path_count"] == 0
    assert metrics["expected_shortfall_severity"] is None


def test_cvar_is_no_greater_than_var_for_lower_tail_balances():
    events = [
        SimulationEvent(0, "inflow", 500, "deposit"),
        SimulationEvent(1, "outflow", 800, "bill"),
    ]

    result = simulate_cashflows(
        starting_balance=1_000,
        events=events,
        horizon_days=4,
        simulations=2_000,
        seed=123,
    )

    metrics = result["risk_metrics"]

    assert (
        metrics["ending_balance_cvar_95"]
        <= metrics["ending_balance_var_95"]
    )

    assert (
        metrics["minimum_balance_cvar_95"]
        <= metrics["minimum_balance_var_95"]
    )


def test_correlated_shocks_are_reproducible():
    events = [
        SimulationEvent(0, "inflow", 1_000, "deposit-A"),
        SimulationEvent(1, "inflow", 1_000, "deposit-B"),
        SimulationEvent(1, "outflow", 500, "bill-A"),
        SimulationEvent(2, "outflow", 700, "bill-B"),
    ]

    first = generate_random_shocks(
        events=events,
        simulations=5_000,
        seed=123,
        shock_correlation=0.8,
    )
    second = generate_random_shocks(
        events=events,
        simulations=5_000,
        seed=123,
        shock_correlation=0.8,
    )

    for event in events:
        for key in (
            "clear_uniform",
            "delay_days",
            "outflow_uplift",
        ):
            np.testing.assert_array_equal(
                first[event.event_id][key],
                second[event.event_id][key],
            )


def test_correlated_shocks_increase_cross_event_dependence():
    events = [
        SimulationEvent(0, "inflow", 1_000, "deposit-A"),
        SimulationEvent(1, "inflow", 1_000, "deposit-B"),
        SimulationEvent(1, "outflow", 500, "bill-A"),
        SimulationEvent(2, "outflow", 700, "bill-B"),
    ]

    independent = generate_random_shocks(
        events=events,
        simulations=20_000,
        seed=321,
        shock_correlation=0.0,
    )
    correlated = generate_random_shocks(
        events=events,
        simulations=20_000,
        seed=321,
        shock_correlation=0.8,
    )

    independent_clear_corr = np.corrcoef(
        independent["deposit-A"]["clear_uniform"],
        independent["deposit-B"]["clear_uniform"],
    )[0, 1]

    correlated_clear_corr = np.corrcoef(
        correlated["deposit-A"]["clear_uniform"],
        correlated["deposit-B"]["clear_uniform"],
    )[0, 1]

    independent_uplift_corr = np.corrcoef(
        independent["bill-A"]["outflow_uplift"],
        independent["bill-B"]["outflow_uplift"],
    )[0, 1]

    correlated_uplift_corr = np.corrcoef(
        correlated["bill-A"]["outflow_uplift"],
        correlated["bill-B"]["outflow_uplift"],
    )[0, 1]

    assert abs(independent_clear_corr) < 0.05
    assert correlated_clear_corr > 0.65

    assert abs(independent_uplift_corr) < 0.05
    assert correlated_uplift_corr > 0.65


@pytest.mark.parametrize("correlation", [-0.01, 1.01, float("nan")])
def test_invalid_shock_correlation_is_rejected(correlation):
    events = [
        SimulationEvent(0, "inflow", 100, "deposit"),
    ]

    with pytest.raises(ValueError, match="shock_correlation"):
        generate_random_shocks(
            events=events,
            simulations=10,
            shock_correlation=correlation,
        )


def test_simulation_reports_shock_correlation_assumption():
    result = simulate_cashflows(
        starting_balance=1_000,
        events=[
            SimulationEvent(0, "inflow", 500, "deposit-A"),
            SimulationEvent(1, "inflow", 500, "deposit-B"),
        ],
        horizon_days=3,
        simulations=1_000,
        shock_correlation=0.8,
    )

    assert result["assumptions"]["shock_correlation"] == pytest.approx(0.8)


    
def test_breach_severity_reports_duration_and_deficit():
    result = simulate_cashflows(
        starting_balance=200,
        events=[
            SimulationEvent(1, "outflow", 150, "large-bill"),
        ],
        horizon_days=3,
        simulations=100,
        safety_buffer=100,
        max_outflow_uplift=0.0,
    )

    severity = result["breach_severity"]

    # The balance starts at 200, then falls to 50 on day 1.
    # It remains below 100 for days 1, 2, and 3.
    assert result["safety_buffer_breach_probability"] == pytest.approx(1.0)
    assert severity["expected_breach_duration_days_if_breached"] == pytest.approx(3.0)
    assert severity["p95_breach_duration_days_if_breached"] == pytest.approx(3.0)
    assert severity["expected_longest_breach_run_days_if_breached"] == pytest.approx(3.0)

    # The daily deficit is $50 for three daily observations.
    assert severity["expected_cumulative_buffer_deficit_if_breached"] == pytest.approx(150.0)
    assert severity["expected_max_buffer_deficit_if_breached"] == pytest.approx(50.0)


def test_breach_severity_is_none_when_no_path_breaches():
    result = simulate_cashflows(
        starting_balance=1_000,
        events=[],
        horizon_days=3,
        simulations=100,
        safety_buffer=500,
    )

    severity = result["breach_severity"]

    assert result["safety_buffer_breach_probability"] == pytest.approx(0.0)
    assert severity["expected_breach_duration_days_if_breached"] is None
    assert severity["expected_cumulative_buffer_deficit_if_breached"] is None
    assert severity["expected_max_buffer_deficit_if_breached"] is None

