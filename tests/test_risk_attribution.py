
import pytest

from backend.quant.risk_attribution import run_risk_attribution
from backend.quant.simulation_engine import SimulationEvent


def test_risk_attribution_identifies_risky_outflow():
    result = run_risk_attribution(
        starting_balance=1_000,
        events=[
            SimulationEvent(0, "outflow", 100, "small-bill"),
            SimulationEvent(1, "outflow", 1_200, "large-bill"),
        ],
        horizon_days=3,
        simulations=2_000,
        safety_buffer=500,
        max_outflow_uplift=0.0,
    )

    drivers = {
        item["event_id"]: item
        for item in result["risk_drivers"]
    }

    assert drivers["large-bill"][
        "shortfall_probability_contribution"
    ] > drivers["small-bill"][
        "shortfall_probability_contribution"
    ]


def test_risk_attribution_is_reproducible():
    kwargs = {
        "starting_balance": 1_000,
        "events": [
            SimulationEvent(0, "inflow", 500, "deposit"),
            SimulationEvent(1, "outflow", 700, "bill"),
        ],
        "horizon_days": 3,
        "simulations": 500,
        "seed": 17,
    }

    first = run_risk_attribution(**kwargs)
    second = run_risk_attribution(**kwargs)

    assert first == second


def test_risk_attribution_reports_protective_inflow():
    result = run_risk_attribution(
        starting_balance=0,
        events=[
            SimulationEvent(0, "inflow", 2_000, "protective-deposit"),
            SimulationEvent(0, "outflow", 500, "bill"),
        ],
        horizon_days=2,
        simulations=1_000,
        safety_buffer=100,
        inflow_clear_probability=1.0,
        max_inflow_delay_days=0,
        max_outflow_uplift=0.0,
    )

    drivers = {
        item["event_id"]: item
        for item in result["risk_drivers"]
    }

    assert drivers["protective-deposit"][
        "shortfall_probability_contribution"
    ] < 0


def test_risk_attribution_rejects_duplicate_event_ids():
    with pytest.raises(ValueError, match="Duplicate"):
        run_risk_attribution(
            starting_balance=1_000,
            events=[
                SimulationEvent(0, "outflow", 100, "same-id"),
                SimulationEvent(1, "outflow", 200, "same-id"),
            ],
            simulations=100,
        )
