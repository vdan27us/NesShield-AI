"""Common-scenario comparison of simple, costed liquidity actions."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from backend.quant.simulation_engine import (
    SimulationEvent,
    generate_random_shocks,
    simulate_cashflows,
)


def compare_interventions(
    *,
    starting_balance: float,
    events: list[SimulationEvent],
    horizon_days: int = 14,
    simulations: int = 2000,
    safety_buffer: float = 5000.0,
    seed: int = 42,
    risk_target: float = 0.05,
    inflow_clear_probability: float = 0.70,
    max_inflow_delay_days: int = 3,
    max_outflow_uplift: float = 0.15,
    shock_correlation: float = 0.35,
) -> dict[str, Any]:
    """Compare baseline and feasible event-timing shifts on common shocks."""
    scenarios = [{"name": "No action", "cost": 0.0, "events": events}]

    deferable = [event for event in events if event.kind == "outflow"]
    if deferable:
        chosen = min(deferable, key=lambda event: (event.amount, event.event_id))
        shifted = [
            replace(event, day=min(horizon_days, event.day + 2))
            if event.event_id == chosen.event_id else event
            for event in events
        ]
        scenarios.append({
            "name": f"Defer {chosen.event_id} by up to 2 days",
            "cost": round(chosen.amount * 0.01, 2),
            "events": shifted,
        })

    accelerable = [event for event in events if event.kind == "inflow" and event.day >= 2]
    if accelerable:
        chosen = max(accelerable, key=lambda event: (event.amount, event.event_id))
        shifted = [
            replace(event, day=max(0, event.day - 2))
            if event.event_id == chosen.event_id else event
            for event in events
        ]
        scenarios.append({
            "name": f"Accelerate {chosen.event_id} by up to 2 days",
            "cost": round(chosen.amount * 0.015, 2),
            "events": shifted,
        })

    union_by_id = {event.event_id: event for event in events}
    shocks = generate_random_shocks(
        events=list(union_by_id.values()), simulations=simulations, seed=seed,
        max_inflow_delay_days=max_inflow_delay_days,
        max_outflow_uplift=max_outflow_uplift,
        shock_correlation=shock_correlation,
    )
    comparisons = []
    for scenario in scenarios:
        metrics = simulate_cashflows(
            starting_balance=starting_balance, events=scenario["events"],
            horizon_days=horizon_days, simulations=simulations,
            safety_buffer=safety_buffer, seed=seed,
            inflow_clear_probability=inflow_clear_probability,
            max_inflow_delay_days=max_inflow_delay_days,
            max_outflow_uplift=max_outflow_uplift,
            random_shocks=shocks, shock_correlation=shock_correlation,
        )
        comparisons.append({
            "name": scenario["name"], "cost": scenario["cost"],
            "safety_buffer_breach_probability": metrics["safety_buffer_breach_probability"],
            "shortfall_probability": metrics["shortfall_probability"],
            "cvar_95": metrics["risk_metrics"].get("minimum_balance_cvar_95"),
            "risk_reduction": 0.0,
        })

    baseline = comparisons[0]["safety_buffer_breach_probability"]
    for item in comparisons:
        item["risk_reduction"] = round(baseline - item["safety_buffer_breach_probability"], 6)
    feasible = [item for item in comparisons[1:] if item["safety_buffer_breach_probability"] <= risk_target]
    recommendation = min(feasible, key=lambda item: item["cost"]) if feasible else None
    return {
        "risk_target": risk_target, "horizon_days": horizon_days,
        "simulations": simulations, "common_random_scenarios": True,
        "recommended_action": recommendation,
        "comparisons": comparisons,
        "assumptions": {"shock_correlation": shock_correlation,
                        "inflow_clear_probability": inflow_clear_probability,
                        "max_inflow_delay_days": max_inflow_delay_days,
                        "max_outflow_uplift": max_outflow_uplift,
                        "safety_buffer": safety_buffer},
    }
