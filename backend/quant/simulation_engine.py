
"""Shared, reproducible cash-flow simulation engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


EventKind = Literal["inflow", "outflow"]


@dataclass(frozen=True)
class SimulationEvent:
    """A cash-flow event scheduled relative to day zero."""

    day: int
    kind: EventKind
    amount: float
    event_id: str = ""


def simulate_cashflows(
    *,
    starting_balance: float,
    events: list[SimulationEvent],
    horizon_days: int = 7,
    simulations: int = 10_000,
    safety_buffer: float = 5_000.0,
    seed: int = 42,
    inflow_clear_probability: float = 0.70,
    max_inflow_delay_days: int = 3,
    max_outflow_uplift: float = 0.15,
) -> dict:
    """Simulate cash balances consistently across daily events."""

    if not np.isfinite(starting_balance):
        raise ValueError("starting_balance must be finite")

    if not np.isfinite(safety_buffer):
        raise ValueError("safety_buffer must be finite")

    if horizon_days < 0:
        raise ValueError("horizon_days must be non-negative")

    if simulations < 1:
        raise ValueError("simulations must be at least 1")

    if not 0 <= inflow_clear_probability <= 1:
        raise ValueError(
            "inflow_clear_probability must be between 0 and 1"
        )

    if max_inflow_delay_days < 0:
        raise ValueError(
            "max_inflow_delay_days must be non-negative"
        )

    if not np.isfinite(max_outflow_uplift) or max_outflow_uplift < 0:
        raise ValueError(
            "max_outflow_uplift must be finite and non-negative"
        )

    for event in events:
        if event.day < 0:
            raise ValueError("Event day must be non-negative")

        if not np.isfinite(event.amount) or event.amount < 0:
            raise ValueError(
                "Event amount must be finite and non-negative"
            )

        if event.kind not in ("inflow", "outflow"):
            raise ValueError(
                f"Unsupported event kind: {event.kind!r}"
            )

    rng = np.random.default_rng(seed)

    balances = np.full(
        simulations, float(starting_balance), dtype=float
    )
    minimum_balances = balances.copy()
    daily_balances = []

    # Process day zero as well as future days.
    for day in range(horizon_days + 1):
        for event in events:
            if event.day != day:
                continue

            if event.kind == "inflow":
                clears = (
                    rng.random(simulations)
                    < inflow_clear_probability
                )

                delays = rng.integers(
                    0,
                    max_inflow_delay_days + 1,
                    size=simulations,
                )

                arrives = clears & (
                    day + delays <= horizon_days
                )

                balances += np.where(
                    arrives, event.amount, 0.0
                )

            else:
                uplift = rng.uniform(
                    0.0,
                    max_outflow_uplift,
                    size=simulations,
                )

                balances -= event.amount * (1.0 + uplift)

        minimum_balances = np.minimum(
            minimum_balances, balances
        )

        daily_balances.append(balances.copy())

    ending_balances = balances

    first_breach_days = []

    for path_index in range(simulations):
        breach_day = next(
            (
                day
                for day, day_balances in enumerate(daily_balances)
                if day_balances[path_index] < safety_buffer
            ),
            None,
        )
        first_breach_days.append(breach_day)

    breach_times = [
        day
        for day in first_breach_days
        if day is not None
    ]

    return {
        "simulations": simulations,
        "horizon_days": horizon_days,
        "shortfall_probability": float(
            np.mean(minimum_balances < 0)
        ),
        "safety_buffer_breach_probability": float(
            np.mean(minimum_balances < safety_buffer)
        ),
        "ending_balance_p05": float(
            np.percentile(ending_balances, 5)
        ),
        "ending_balance_median": float(
            np.percentile(ending_balances, 50)
        ),
        "ending_balance_p95": float(
            np.percentile(ending_balances, 95)
        ),
        "minimum_balance_p05": float(
            np.percentile(minimum_balances, 5)
        ),
        "expected_minimum_balance": float(
            np.mean(minimum_balances)
        ),
        "expected_ending_balance": float(
            np.mean(ending_balances)
        ),
        "probability_of_breach_by_day": {
            day: float(
                np.mean(day_balances < safety_buffer)
            )
            for day, day_balances in enumerate(daily_balances)
        },
        "time_to_first_buffer_breach": {
            "breach_probability": (
                len(breach_times) / simulations
            ),
            "mean_day_if_breached": (
                float(np.mean(breach_times))
                if breach_times
                else None
            ),
        },
        "assumptions": {
            "starting_balance": float(starting_balance),
            "safety_buffer": float(safety_buffer),
            "inflow_clear_probability": (
                inflow_clear_probability
            ),
            "max_inflow_delay_days": (
                max_inflow_delay_days
            ),
            "max_outflow_uplift": max_outflow_uplift,
            "seed": seed,
        },
    }
