
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
