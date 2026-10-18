
"""What-if scenario simulation using the shared cash-flow engine."""
from __future__ import annotations

import numpy as np

from backend.quant.simulation_engine import (
    SimulationEvent,
    simulate_cashflows,
)


def run_what_if_simulation(
    starting_balance: float,
    payroll_amount: float,
    deposit_amount: float,
    deposit_delay_days: int,
    safety_buffer: float,
    simulations: int = 10_000,
    seed: int = 42,
) -> tuple[dict, list[dict], float]:
    """
    Simulate a hypothetical deposit and payroll scenario.

    Return format remains:
        (risk_metrics, deterministic_forecast, projected_ending_balance)
    """
    numeric_values = {
        "starting_balance": starting_balance,
        "payroll_amount": payroll_amount,
        "deposit_amount": deposit_amount,
        "safety_buffer": safety_buffer,
    }

    for name, value in numeric_values.items():
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite")

    if payroll_amount < 0 or deposit_amount < 0:
        raise ValueError("Payment amounts must be non-negative")

    if safety_buffer < 0:
        raise ValueError("safety_buffer must be non-negative")

    if not isinstance(deposit_delay_days, int):
        raise ValueError("deposit_delay_days must be an integer")

    if not 0 <= deposit_delay_days <= 7:
        raise ValueError(
            "deposit_delay_days must be between 0 and 7"
        )

    if simulations < 1:
        raise ValueError("simulations must be at least 1")

    horizon_days = 14
    payroll_day = min(3, horizon_days)

    # Preserve the existing what-if assumptions.
    deposit_clear_probability = 0.70
    max_random_delay = 3
    max_outflow_uplift = 0.15
    shock_correlation = 0.35

    # Preserve the previous deterministic planning convention:
    # a delay of zero means the deposit is credited on day 1.
    planned_deposit_day = max(1, deposit_delay_days)

    events = [
        SimulationEvent(
            day=planned_deposit_day,
            kind="inflow",
            amount=float(deposit_amount),
            event_id="hypothetical-deposit",
        ),
        SimulationEvent(
            day=payroll_day,
            kind="outflow",
            amount=float(payroll_amount),
            event_id="hypothetical-payroll",
        ),
    ]

    risk_metrics = simulate_cashflows(
        starting_balance=float(starting_balance),
        events=events,
        horizon_days=horizon_days,
        simulations=simulations,
        safety_buffer=float(safety_buffer),
        seed=seed,
        inflow_clear_probability=deposit_clear_probability,
        max_inflow_delay_days=max_random_delay,
        max_outflow_uplift=max_outflow_uplift,
        shock_correlation=shock_correlation,
        unexpected_expense_probability=0.03,
        max_unexpected_expense=1_000.0,
    )

    # Deterministic planning path remains separate from the stochastic
    # risk estimate, as in the original API.
    planning_balance = float(starting_balance)
    forecast = []

    for day in range(horizon_days + 1):
        if day == planned_deposit_day:
            planning_balance += float(deposit_amount)

        if day == payroll_day:
            planning_balance -= float(payroll_amount)

        forecast.append(
            {
                "day": day,
                "label": "Today" if day == 0 else f"Day {day}",
                "projected_balance": round(planning_balance, 2),
            }
        )

    # Preserve the original risk fields and assumptions for API consumers.
    risk_metrics.update(
        {
            "assumptions": {
                "starting_balance": float(starting_balance),
                "payroll_amount": float(payroll_amount),
                "deposit_amount": float(deposit_amount),
                "deposit_delay_days": deposit_delay_days,
                "payroll_day": payroll_day,
                "deposit_clear_probability": (
                    deposit_clear_probability
                ),
                "max_random_deposit_delay_days": (
                    max_random_delay
                ),
                "max_outflow_uplift": max_outflow_uplift,
                "shock_correlation": shock_correlation,
                "unexpected_expense_probability": 0.03,
                "max_unexpected_expense": 1_000.0,
                "safety_buffer": float(safety_buffer),
                "seed": seed,
            }
        }
    )

    return (
        risk_metrics,
        forecast,
        round(planning_balance, 2),
    )
