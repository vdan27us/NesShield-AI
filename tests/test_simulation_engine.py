
import pytest

from backend.quant.simulation_engine import (
    SimulationEvent,
    simulate_cashflows,
)


def test_no_events_preserve_balance():
    result = simulate_cashflows(
        starting_balance=10_000,
        events=[],
        horizon_days=7,
        simulations=100,
        safety_buffer=5_000,
    )

    assert result["ending_balance_median"] == 10_000
    assert result["shortfall_probability"] == 0
    assert result["safety_buffer_breach_probability"] == 0


def test_certain_outflow_reduces_balance():
    result = simulate_cashflows(
        starting_balance=10_000,
        events=[
            SimulationEvent(
                day=3,
                kind="outflow",
                amount=2_000,
            )
        ],
        horizon_days=7,
        simulations=100,
        safety_buffer=5_000,
        max_outflow_uplift=0,
    )

    assert result["ending_balance_median"] == 8_000
    assert result["expected_ending_balance"] == 8_000


def test_certain_inflow_arrives_on_scheduled_day():
    result = simulate_cashflows(
        starting_balance=1_000,
        events=[
            SimulationEvent(
                day=1,
                kind="inflow",
                amount=500,
            )
        ],
        horizon_days=2,
        simulations=100,
        safety_buffer=0,
        inflow_clear_probability=1,
        max_inflow_delay_days=0,
    )

    assert result["ending_balance_median"] == 1_500


def test_seed_makes_results_reproducible():
    arguments = {
        "starting_balance": 1_000,
        "events": [
            SimulationEvent(day=1, kind="inflow", amount=500),
            SimulationEvent(day=2, kind="outflow", amount=800),
        ],
        "horizon_days": 3,
        "simulations": 100,
    }

    first = simulate_cashflows(**arguments)
    second = simulate_cashflows(**arguments)

    assert first == second


def test_invalid_event_amount_is_rejected():
    with pytest.raises(ValueError):
        simulate_cashflows(
            starting_balance=1_000,
            events=[
                SimulationEvent(day=1, kind="outflow", amount=-1)
            ],
        )
