"""Scenario simulation for Nesshield AI's interactive what-if tool."""
from __future__ import annotations

import numpy as np


def run_what_if_simulation(
    starting_balance: float,
    payroll_amount: float,
    deposit_amount: float,
    deposit_delay_days: int,
    safety_buffer: float,
    simulations: int = 10_000,
    seed: int = 42,
) -> tuple[dict, list[dict], float]:
    """Run a transparent 7-day scenario simulation with explicit assumptions."""
    rng = np.random.default_rng(seed)
    horizon_days = 7
    payroll_day = 3  # Payroll is modeled three days from the scenario start.
    delay_days = max(0, min(7, int(deposit_delay_days)))
    deposit_clear_probability = 0.70
    max_random_delay = 3
    max_outflow_uplift = 0.15

    deposit_clears = rng.random(simulations) < deposit_clear_probability
    random_delay = rng.integers(0, max_random_delay + 1, size=simulations)
    actual_deposit_day = delay_days + random_delay
    uplift = rng.uniform(0, max_outflow_uplift, size=simulations)

    balances = np.full(simulations, float(starting_balance), dtype=float)
    # Deposits modeled as clearing on day 0 are available at scenario start.
    balances += np.where(deposit_clears & (actual_deposit_day <= 0), float(deposit_amount), 0.0)
    minimum_balances = balances.copy()

    # Apply deposit only in scenarios where it clears during the horizon.
    for day in range(1, horizon_days + 1):
        deposit_today = deposit_clears & (actual_deposit_day == day)
        balances += np.where(deposit_today, float(deposit_amount), 0.0)

        if day == payroll_day:
            balances -= float(payroll_amount) * (1.0 + uplift)

        minimum_balances = np.minimum(minimum_balances, balances)

    shortfall_probability = float(np.mean(minimum_balances < 0))
    buffer_breach_probability = float(np.mean(minimum_balances < float(safety_buffer)))
    ending_p05 = float(np.percentile(balances, 5))
    ending_median = float(np.median(balances))
    ending_p95 = float(np.percentile(balances, 95))
    minimum_p05 = float(np.percentile(minimum_balances, 5))

    # Deterministic planning path: deposit arrives on the chosen delay day;
    # payroll leaves on day 3. This is separate from the stochastic simulations.
    planning_balance = float(starting_balance)
    forecast = []
    for day in range(0, horizon_days + 1):
        if day == max(1, delay_days):
            planning_balance += float(deposit_amount)
        if day == payroll_day:
            planning_balance -= float(payroll_amount)
        forecast.append({
            "day": day,
            "label": "Today" if day == 0 else f"Day {day}",
            "projected_balance": round(planning_balance, 2),
        })

    return {
        "simulations": simulations,
        "horizon_days": horizon_days,
        "shortfall_probability": shortfall_probability,
        "safety_buffer_breach_probability": buffer_breach_probability,
        "ending_balance_p05": ending_p05,
        "ending_balance_median": ending_median,
        "ending_balance_p95": ending_p95,
        "minimum_balance_p05": minimum_p05,
        "assumptions": {
            "starting_balance": float(starting_balance),
            "payroll_amount": float(payroll_amount),
            "deposit_amount": float(deposit_amount),
            "deposit_delay_days": delay_days,
            "payroll_day": payroll_day,
            "deposit_clear_probability": deposit_clear_probability,
            "max_random_deposit_delay_days": max_random_delay,
            "max_outflow_uplift": max_outflow_uplift,
            "safety_buffer": float(safety_buffer),
            "seed": seed,
        },
    }, forecast, round(planning_balance, 2)
