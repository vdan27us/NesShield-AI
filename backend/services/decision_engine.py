"""Common-scenario comparison of costed liquidity interventions."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
from backend.quant.simulation_engine import (
    SimulationEvent,
    generate_random_shocks,
    simulate_cashflows,
)


def compare_interventions(
    *, starting_balance: float, events: list[SimulationEvent],
    horizon_days: int = 14, simulations: int = 10_000,
    safety_buffer: float = 5_000.0, seed: int = 42,
    risk_target: float = 0.05, inflow_clear_probability: float = 0.70,
    max_inflow_delay_days: int = 3, max_outflow_uplift: float = 0.15,
    shock_correlation: float = 0.0,
    unexpected_expense_probability: float = 0.03,
    max_unexpected_expense: float = 1_000.0,
    deferral_days: int = 2, deferral_fee_rate: float = 0.01,
    acceleration_days: int = 2, acceleration_fee_rate: float = 0.015,
    credit_line_limit: float = 10_000.0, credit_line_fee_rate: float = 0.02,
) -> dict[str, Any]:
    """Compare timing, credit, and combined actions using common shocks.

    Fee rates and the default line limit are illustrative planning inputs,
    not live lender offers. Callers should replace them with quoted terms.
    """
    fee_rates = (deferral_fee_rate, acceleration_fee_rate, credit_line_fee_rate)
    if any(rate < 0 for rate in fee_rates) or credit_line_limit < 0:
        raise ValueError("Intervention costs and limits must be non-negative")

    candidates: list[dict[str, Any]] = []
    outflows = sorted((e for e in events if e.kind == "outflow"),
                      key=lambda e: (-e.amount, e.event_id))
    inflows = sorted((e for e in events if e.kind == "inflow"),
                     key=lambda e: (-e.amount, e.event_id))

    def shifted(event: SimulationEvent, day: int) -> list[SimulationEvent]:
        return [replace(e, day=day) if e.event_id == event.event_id else e
                for e in events]

    for event in outflows:
        moved = min(horizon_days, event.day + deferral_days)
        if moved > event.day:
            candidates.append({
                "name": f"Defer {event.event_id} by {moved - event.day} days",
                "cost": round(event.amount * deferral_fee_rate, 2),
                "events": shifted(event, moved), "funding": 0.0,
            })

    for event in inflows:
        moved = max(0, event.day - acceleration_days)
        if moved < event.day:
            candidates.append({
                "name": f"Accelerate {event.event_id} by {event.day - moved} days",
                "cost": round(event.amount * acceleration_fee_rate, 2),
                "events": shifted(event, moved), "funding": 0.0,
            })

    if credit_line_limit > 0:
        draw = min(credit_line_limit, max(safety_buffer - starting_balance, 0.0)
                   + max((e.amount for e in outflows), default=0.0))
        if draw > 0:
            line_event = SimulationEvent(0, "inflow", draw, "intervention-credit-line", 1.0)
            candidates.append({
                "name": f"Draw ${draw:,.0f} from illustrative credit line",
                "cost": round(draw * credit_line_fee_rate, 2),
                "events": [*events, line_event], "funding": 0.0,
                "certain_event_ids": {line_event.event_id},
            })

    # Also try the principal outflow deferral in combination with the line.
    if outflows and credit_line_limit > 0:
        event = outflows[0]
        moved = min(horizon_days, event.day + deferral_days)
        draw = min(credit_line_limit, max(safety_buffer - starting_balance, 0.0)
                   + event.amount)
        if moved > event.day and draw > 0:
            line_event = SimulationEvent(0, "inflow", draw, "intervention-credit-line", 1.0)
            combined = [replace(e, day=moved) if e.event_id == event.event_id else e
                        for e in events]
            combined.append(line_event)
            candidates.append({
                "name": f"Defer {event.event_id} and draw ${draw:,.0f} credit",
                "cost": round(event.amount * deferral_fee_rate
                              + draw * credit_line_fee_rate, 2),
                "events": combined, "funding": 0.0,
                "certain_event_ids": {line_event.event_id},
            })

    scenarios = [{"name": "No action", "cost": 0.0, "events": events,
                  "funding": 0.0, "certain_event_ids": set()}, *candidates]
    all_events = {event.event_id: event for item in scenarios
                  for event in item["events"]}
    shocks = generate_random_shocks(
        events=list(all_events.values()), simulations=simulations, seed=seed,
        max_inflow_delay_days=max_inflow_delay_days,
        max_outflow_uplift=max_outflow_uplift,
        shock_correlation=shock_correlation,
        horizon_days=horizon_days,
        unexpected_expense_probability=unexpected_expense_probability,
        max_unexpected_expense=max_unexpected_expense,
    )
    if "intervention-credit-line" in shocks:
        shocks["intervention-credit-line"]["delay_days"] = np.zeros(
            simulations, dtype=int
        )
    comparisons = []
    for item in scenarios:
        metrics = simulate_cashflows(
            starting_balance=starting_balance - item["cost"],
            events=item["events"], horizon_days=horizon_days,
            simulations=simulations, safety_buffer=safety_buffer, seed=seed,
            inflow_clear_probability=inflow_clear_probability,
            max_inflow_delay_days=max_inflow_delay_days,
            max_outflow_uplift=max_outflow_uplift,
            random_shocks=shocks, shock_correlation=shock_correlation,
            unexpected_expense_probability=unexpected_expense_probability,
            max_unexpected_expense=max_unexpected_expense,
        )
        comparisons.append({
            "name": item["name"], "cost": item["cost"],
            "safety_buffer_breach_probability": metrics["safety_buffer_breach_probability"],
            "shortfall_probability": metrics["shortfall_probability"],
            "cvar_95": metrics["risk_metrics"]["minimum_balance_cvar_95"],
            "risk_reduction": 0.0,
            "daily_balance_percentiles": metrics["daily_balance_percentiles"],
        })

    baseline = comparisons[0]["safety_buffer_breach_probability"]
    for item in comparisons:
        item["risk_reduction"] = round(
            baseline - item["safety_buffer_breach_probability"], 6)
    feasible = [item for item in comparisons
                if item["safety_buffer_breach_probability"] <= risk_target]
    recommendation = min(feasible, key=lambda item: item["cost"]) if feasible else None
    if recommendation is not None and recommendation["name"] == "No action":
        recommendation = {**recommendation, "action_type": "none"}
    return {
        "risk_target": risk_target, "horizon_days": horizon_days,
        "simulations": simulations, "common_random_scenarios": True,
        "recommended_action": recommendation,
        "comparisons": comparisons,
        "assumptions": {
            "shock_correlation": shock_correlation,
            "inflow_clear_probability": inflow_clear_probability,
            "max_inflow_delay_days": max_inflow_delay_days,
            "max_outflow_uplift": max_outflow_uplift,
            "unexpected_expense_probability": unexpected_expense_probability,
            "max_unexpected_expense": max_unexpected_expense,
            "safety_buffer": safety_buffer,
            "deferral_days": deferral_days,
            "deferral_fee_rate": deferral_fee_rate,
            "acceleration_days": acceleration_days,
            "acceleration_fee_rate": acceleration_fee_rate,
            "credit_line_limit": credit_line_limit,
            "credit_line_fee_rate": credit_line_fee_rate,
            "costs_are_illustrative": True,
            "credit_line_clearing_assumption": "certain on day 0; illustrative only",
        },
    }
