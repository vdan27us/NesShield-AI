
"""Shared cash-flow simulation engine with reusable random shocks."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Literal

import numpy as np


EventKind = Literal["inflow", "outflow"]
RandomShockMap = dict[str, dict[str, np.ndarray]]


@dataclass(frozen=True)
class SimulationEvent:
    """A cash-flow event scheduled relative to day zero."""

    day: int
    kind: EventKind
    amount: float
    event_id: str = ""


def _event_keys(events: list[SimulationEvent]) -> list[str]:
    """Return stable shock keys and reject duplicate explicit IDs."""
    keys = []
    seen = set()

    for index, event in enumerate(events):
        key = event.event_id or (
            f"anonymous:{index}:{event.kind}:{event.day}"
        )

        if key in seen:
            raise ValueError(f"Duplicate simulation event ID: {key}")

        seen.add(key)
        keys.append(key)

    return keys


def generate_random_shocks(
    *,
    events: list[SimulationEvent],
    simulations: int,
    seed: int = 42,
    max_inflow_delay_days: int = 3,
    max_outflow_uplift: float = 0.15,
) -> RandomShockMap:
    """
    Generate reusable random arrays keyed by event ID.

    The same seed and event ID produce the same shocks even when
    unrelated events are added or reordered. Pass the returned map
    to multiple simulations to compare scenarios on common draws.
    """
    if simulations < 1:
        raise ValueError("simulations must be at least 1")

    if max_inflow_delay_days < 0:
        raise ValueError(
            "max_inflow_delay_days must be non-negative"
        )

    if (
        not np.isfinite(max_outflow_uplift)
        or max_outflow_uplift < 0
    ):
        raise ValueError(
            "max_outflow_uplift must be finite and non-negative"
        )

    keys = _event_keys(events)
    shocks: RandomShockMap = {}

    for key in keys:
        digest = blake2b(
            f"{seed}:{key}".encode("utf-8"),
            digest_size=8,
        ).digest()
        event_seed = int.from_bytes(digest, "little")
        rng = np.random.default_rng(event_seed)

        shocks[key] = {
            "clear_uniform": rng.random(simulations),
            "delay_days": rng.integers(
                0,
                max_inflow_delay_days + 1,
                size=simulations,
            ),
            "outflow_uplift": rng.uniform(
                0.0,
                max_outflow_uplift,
                size=simulations,
            ),
        }

    return shocks


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
    random_shocks: RandomShockMap | None = None,
) -> dict:
    """Simulate cash balances using explicit event arrival times."""

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

    if (
        not np.isfinite(max_outflow_uplift)
        or max_outflow_uplift < 0
    ):
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

    keys = _event_keys(events)

    if random_shocks is None:
        random_shocks = generate_random_shocks(
            events=events,
            simulations=simulations,
            seed=seed,
            max_inflow_delay_days=max_inflow_delay_days,
            max_outflow_uplift=max_outflow_uplift,
        )

    # Validate all required shock arrays before starting the simulation.
    for key in keys:
        if key not in random_shocks:
            raise ValueError(f"Missing random shocks for event: {key}")

        for shock_name in (
            "clear_uniform",
            "delay_days",
            "outflow_uplift",
        ):
            values = random_shocks[key].get(shock_name)

            if values is None or np.asarray(values).shape != (simulations,):
                raise ValueError(
                    f"Invalid {shock_name} array for event {key!r}"
                )

    # Precompute each event's clearance and arrival day once.
    prepared_events = []

    for event, key in zip(events, keys):
        shock = random_shocks[key]

        if event.kind == "inflow":
            clears = (
                np.asarray(shock["clear_uniform"])
                < inflow_clear_probability
            )
            delays = np.asarray(shock["delay_days"], dtype=int)
            arrival_days = event.day + delays

            prepared_events.append(
                (event, clears, arrival_days, None)
            )
        else:
            uplift = np.asarray(
                shock["outflow_uplift"], dtype=float
            )
            prepared_events.append(
                (event, None, None, uplift)
            )

    balances = np.full(
        simulations, float(starting_balance), dtype=float
    )
    minimum_balances = balances.copy()
    daily_balances = []

    # Process today (day zero) and each subsequent day.
    for day in range(horizon_days + 1):
        # Inflows clear before outflows on the same day.
        for event, clears, arrival_days, _ in prepared_events:
            if event.kind != "inflow":
                continue

            arrives_today = (
                clears
                & (arrival_days == day)
                & (arrival_days <= horizon_days)
            )

            balances += np.where(
                arrives_today, event.amount, 0.0
            )

        for event, _, _, uplift in prepared_events:
            if event.kind != "outflow" or event.day != day:
                continue

            balances -= event.amount * (1.0 + uplift)

        minimum_balances = np.minimum(
            minimum_balances, balances
        )
        daily_balances.append(balances.copy())

    ending_balances = balances

    # Vectorized first-breach calculation: no Python loop per path.
    daily_matrix = np.stack(daily_balances, axis=0)
    breached = daily_matrix < safety_buffer
    ever_breached = breached.any(axis=0)

    first_breach_days = np.argmax(breached, axis=0)
    breach_times = first_breach_days[ever_breached]

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
            day: float(np.mean(breached[day]))
            for day in range(horizon_days + 1)
        },
        "time_to_first_buffer_breach": {
            "breach_probability": float(np.mean(ever_breached)),
            "mean_day_if_breached": (
                float(np.mean(breach_times))
                if breach_times.size
                else None
            ),
        },
        "assumptions": {
            "starting_balance": float(starting_balance),
            "safety_buffer": float(safety_buffer),
            "inflow_clear_probability": inflow_clear_probability,
            "max_inflow_delay_days": max_inflow_delay_days,
            "max_outflow_uplift": max_outflow_uplift,
            "seed": seed,
        },
    }
