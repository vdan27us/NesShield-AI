
"""Shared cash-flow simulation engine with reusable random shocks."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from math import ceil
from statistics import NormalDist
from typing import Literal

import numpy as np


EventKind = Literal["inflow", "outflow"]
RandomShockMap = dict[str, dict[str, np.ndarray]]

RISK_CONFIDENCE_LEVEL = 0.95
TAIL_PROBABILITY = 1.0 - RISK_CONFIDENCE_LEVEL


@dataclass(frozen=True)
class SimulationEvent:
    """A cash-flow event scheduled relative to day zero."""

    day: int
    kind: EventKind
    amount: float
    event_id: str = ""
    clear_probability: float | None = None
    predicted_delay_days: int = 0
    late_probability: float | None = None


def _event_keys(events: list[SimulationEvent]) -> list[str]:
    """Return stable shock keys and reject duplicate IDs."""
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


def _seed_for(seed: int, key: str) -> int:
    """Create a deterministic NumPy seed from a stable key."""
    digest = blake2b(
        f"{seed}:{key}".encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "little")


def _normal_to_uniform(values: np.ndarray) -> np.ndarray:
    """Transform standard-normal values into uniform values via its CDF."""
    normal = NormalDist()

    return np.fromiter(
        (normal.cdf(float(value)) for value in values),
        dtype=float,
        count=len(values),
    )


def _lower_tail_mean(
    values: np.ndarray,
    tail_probability: float,
) -> float:
    """Return the mean of the worst fraction of observations."""
    if values.size == 0:
        raise ValueError("Cannot calculate tail mean of empty values")

    if not 0 < tail_probability <= 1:
        raise ValueError("tail_probability must be in (0, 1]")

    tail_count = max(1, ceil(values.size * tail_probability))
    worst_values = np.partition(values, tail_count - 1)[:tail_count]

    return float(np.mean(worst_values))


def generate_random_shocks(
    *,
    events: list[SimulationEvent],
    simulations: int,
    seed: int = 42,
    max_inflow_delay_days: int = 3,
    max_outflow_uplift: float = 0.15,
    shock_correlation: float = 0.0,
    horizon_days: int = 0,
    unexpected_expense_probability: float = 0.0,
    max_unexpected_expense: float = 0.0,
) -> RandomShockMap:
    """
    Generate reproducible shocks keyed by event ID.

    Correlation zero preserves the independent-shock model. Positive
    correlation uses a Gaussian common factor to introduce dependence
    between events while preserving the uniform marginal distributions.

    Adverse latent values correspond to less reliable inflows, longer
    delays, and larger outflow uplifts.
    """
    if simulations < 1:
        raise ValueError("simulations must be at least 1")

    if max_inflow_delay_days < 0:
        raise ValueError("max_inflow_delay_days must be non-negative")

    if (
        not np.isfinite(max_outflow_uplift)
        or max_outflow_uplift < 0
    ):
        raise ValueError(
            "max_outflow_uplift must be finite and non-negative"
        )

    if (
        not np.isfinite(shock_correlation)
        or not 0.0 <= shock_correlation <= 1.0
    ):
        raise ValueError("shock_correlation must be between 0 and 1")

    keys = _event_keys(events)
    shocks: RandomShockMap = {}
    common_rng = np.random.default_rng(
        _seed_for(seed, "systemic_common_factor")
    )
    common_factor = common_rng.standard_normal(simulations)

    if not 0 <= unexpected_expense_probability <= 1:
        raise ValueError("unexpected_expense_probability must be between 0 and 1")
    if not np.isfinite(max_unexpected_expense) or max_unexpected_expense < 0:
        raise ValueError("max_unexpected_expense must be finite and non-negative")

    def add_unexpected_expenses() -> None:
        if unexpected_expense_probability == 0 or max_unexpected_expense == 0:
            return
        rng = np.random.default_rng(_seed_for(seed, "unexpected_expenses"))
        individual = rng.standard_normal((horizon_days + 1, simulations))
        latent = (
            np.sqrt(shock_correlation) * common_factor[None, :]
            + np.sqrt(1.0 - shock_correlation) * individual
        )
        occurrence_uniform = _normal_to_uniform(latent.ravel()).reshape(
            horizon_days + 1, simulations
        )
        shocks["__unexpected_expenses__"] = {
            "occurrence_uniform": occurrence_uniform,
            "amount": rng.uniform(
                0.0, max_unexpected_expense,
                size=(horizon_days + 1, simulations),
            ),
        }

    if shock_correlation == 0.0:
        # Preserve the original independent-shock behavior.
        for key in keys:
            rng = np.random.default_rng(_seed_for(seed, key))

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

        add_unexpected_expenses()
        return shocks

    # A common latent factor shared by every event and shock type.
    common_weight = np.sqrt(shock_correlation)
    individual_weight = np.sqrt(1.0 - shock_correlation)

    for key in keys:
        event_shocks = {}

        for shock_name in (
            "clear_uniform",
            "delay_days",
            "outflow_uplift",
        ):
            rng = np.random.default_rng(
                _seed_for(seed, f"{key}:{shock_name}")
            )
            individual_factor = rng.standard_normal(simulations)

            latent = (
                common_weight * common_factor
                + individual_weight * individual_factor
            )
            uniform_values = _normal_to_uniform(latent)

            if shock_name == "clear_uniform":
                event_shocks[shock_name] = uniform_values

            elif shock_name == "delay_days":
                delays = np.floor(
                    uniform_values * (max_inflow_delay_days + 1)
                ).astype(int)

                event_shocks[shock_name] = np.minimum(
                    delays,
                    max_inflow_delay_days,
                )

            else:
                event_shocks[shock_name] = (
                    uniform_values * max_outflow_uplift
                )

        shocks[key] = event_shocks

    add_unexpected_expenses()
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
    shock_correlation: float = 0.0,
    unexpected_expense_probability: float = 0.0,
    max_unexpected_expense: float = 0.0,
) -> dict:
    """Simulate cash balances and calculate downside risk metrics."""
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
        raise ValueError("max_inflow_delay_days must be non-negative")

    if (
        not np.isfinite(max_outflow_uplift)
        or max_outflow_uplift < 0
    ):
        raise ValueError(
            "max_outflow_uplift must be finite and non-negative"
        )

    if (
        not np.isfinite(shock_correlation)
        or not 0.0 <= shock_correlation <= 1.0
    ):
        raise ValueError("shock_correlation must be between 0 and 1")

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
        if event.clear_probability is not None and not 0 <= event.clear_probability <= 1:
            raise ValueError("event clear_probability must be between 0 and 1")
        if event.predicted_delay_days < 0:
            raise ValueError("event predicted_delay_days must be non-negative")
        if event.late_probability is not None and not 0 <= event.late_probability <= 1:
            raise ValueError("event late_probability must be between 0 and 1")

    keys = _event_keys(events)

    if random_shocks is None:
        random_shocks = generate_random_shocks(
            events=events,
            simulations=simulations,
            seed=seed,
            max_inflow_delay_days=max_inflow_delay_days,
            max_outflow_uplift=max_outflow_uplift,
            shock_correlation=shock_correlation,
            horizon_days=horizon_days,
            unexpected_expense_probability=unexpected_expense_probability,
            max_unexpected_expense=max_unexpected_expense,
        )

    # Explicitly supplied shocks take precedence. Generate them with
    # the desired correlation setting when constructing custom scenarios.
    for key in keys:
        if key not in random_shocks:
            raise ValueError(f"Missing random shocks for event: {key}")

        for shock_name in (
            "clear_uniform",
            "delay_days",
            "outflow_uplift",
        ):
            values = random_shocks[key].get(shock_name)

            if (
                values is None
                or np.asarray(values).shape != (simulations,)
            ):
                raise ValueError(
                    f"Invalid {shock_name} array for event {key!r}"
                )

            if not np.all(np.isfinite(values)):
                raise ValueError(
                    f"Non-finite {shock_name} values for event {key!r}"
                )

    prepared_events = []

    for event, key in zip(events, keys):
        shock = random_shocks[key]

        if event.kind == "inflow":
            clear_uniform = np.asarray(
                shock["clear_uniform"], dtype=float
            )
            delays = np.asarray(
                shock["delay_days"], dtype=int
            )

            if np.any((clear_uniform < 0) | (clear_uniform > 1)):
                raise ValueError(
                    "clear_uniform values must be in [0, 1]"
                )

            if np.any(delays < 0):
                raise ValueError("Delay values must be non-negative")

            clear_probability = (
                inflow_clear_probability
                if event.clear_probability is None
                else event.clear_probability
            )
            clears = clear_uniform < clear_probability
            late_flags = (
                clear_uniform < event.late_probability
                if event.late_probability is not None
                else np.zeros(simulations, dtype=bool)
            )
            arrival_days = (
                event.day + event.predicted_delay_days + delays
                + np.where(late_flags, max_inflow_delay_days + 1, 0)
            )

            prepared_events.append(
                (event, clears, arrival_days, None)
            )

        else:
            uplift = np.asarray(
                shock["outflow_uplift"], dtype=float
            )

            if np.any(uplift < 0):
                raise ValueError(
                    f"Invalid outflow uplift values for event {key!r}"
                )

            prepared_events.append(
                (event, None, None, uplift)
            )

    balances = np.full(
        simulations, float(starting_balance), dtype=float
    )
    minimum_balances = balances.copy()
    daily_balances = []

    # Process day zero and each subsequent day.
    # Inflows clear before outflows on the same day.
    for day in range(horizon_days + 1):
        for event, clears, arrival_days, _ in prepared_events:
            if event.kind != "inflow":
                continue

            arrives_today = (
                clears
                & (arrival_days == day)
                & (arrival_days <= horizon_days)
            )

            balances += np.where(
                arrives_today,
                event.amount,
                0.0,
            )

        for event, _, _, uplift in prepared_events:
            if event.kind != "outflow" or event.day != day:
                continue

            balances -= event.amount * (1.0 + uplift)

        expense_shocks = random_shocks.get("__unexpected_expenses__")
        if expense_shocks is not None:
            occurs = (
                expense_shocks["occurrence_uniform"][day]
                < unexpected_expense_probability
            )
            balances -= np.where(occurs, expense_shocks["amount"][day], 0.0)

        minimum_balances = np.minimum(
            minimum_balances,
            balances,
        )
        daily_balances.append(balances.copy())

    ending_balances = balances
    daily_matrix = np.stack(daily_balances, axis=0)

    breached = daily_matrix < safety_buffer
    ever_breached = breached.any(axis=0)

    first_breach_days = np.argmax(breached, axis=0)
    breach_times = first_breach_days[ever_breached]

    # Phase 3.4: breach duration and severity.
    # Duration counts daily observations below the buffer, including day 0.
    breach_duration_days = np.sum(breached, axis=0)

    # Longest consecutive run of daily observations below the buffer.
    longest_breach_duration_days = np.zeros(
        simulations,
        dtype=int,
    )
    current_breach_run = np.zeros(
        simulations,
        dtype=int,
    )

    for day_breached in breached:
        current_breach_run = np.where(
            day_breached,
            current_breach_run + 1,
            0,
        )
        longest_breach_duration_days = np.maximum(
            longest_breach_duration_days,
            current_breach_run,
        )

    # Dollar deficit relative to the safety buffer on each daily observation.
    buffer_deficits = np.maximum(
        safety_buffer - daily_matrix,
        0.0,
    )

    # Cumulative deficit is expressed in dollar-days.
    cumulative_buffer_deficit = np.sum(
        buffer_deficits,
        axis=0,
    )

    maximum_buffer_deficit = np.max(
        buffer_deficits,
        axis=0,
    )

    if np.any(ever_breached):
        breached_durations = breach_duration_days[ever_breached]
        breached_longest_durations = (
            longest_breach_duration_days[ever_breached]
        )
        breached_cumulative_deficits = (
            cumulative_buffer_deficit[ever_breached]
        )
        breached_maximum_deficits = (
            maximum_buffer_deficit[ever_breached]
        )

        breach_severity = {
            "expected_breach_duration_days_if_breached": float(
                np.mean(breached_durations)
            ),
            "p95_breach_duration_days_if_breached": float(
                np.percentile(breached_durations, 95)
            ),
            "expected_longest_breach_run_days_if_breached": float(
                np.mean(breached_longest_durations)
            ),
            "expected_cumulative_buffer_deficit_if_breached": float(
                np.mean(breached_cumulative_deficits)
            ),
            "p95_cumulative_buffer_deficit_if_breached": float(
                np.percentile(breached_cumulative_deficits, 95)
            ),
            "expected_max_buffer_deficit_if_breached": float(
                np.mean(breached_maximum_deficits)
            ),
            "p95_max_buffer_deficit_if_breached": float(
                np.percentile(breached_maximum_deficits, 95)
            ),
        }

    else:
        breach_severity = {
            "expected_breach_duration_days_if_breached": None,
            "p95_breach_duration_days_if_breached": None,
            "expected_longest_breach_run_days_if_breached": None,
            "expected_cumulative_buffer_deficit_if_breached": None,
            "p95_cumulative_buffer_deficit_if_breached": None,
            "expected_max_buffer_deficit_if_breached": None,
            "p95_max_buffer_deficit_if_breached": None,
        }

    ending_balance_p05 = float(
        np.percentile(ending_balances, 5)
    )
    ending_balance_median = float(
        np.percentile(ending_balances, 50)
    )
    ending_balance_p95 = float(
        np.percentile(ending_balances, 95)
    )

    shortfall_paths = minimum_balances < 0

    expected_shortfall_severity = (
        float(np.mean(-minimum_balances[shortfall_paths]))
        if np.any(shortfall_paths)
        else None
    )

    daily_balance_percentiles = {}

    for day in range(horizon_days + 1):
        day_balances = daily_matrix[day]

        daily_balance_percentiles[day] = {
            "p05": float(np.percentile(day_balances, 5)),
            "p50": float(np.percentile(day_balances, 50)),
            "p95": float(np.percentile(day_balances, 95)),
        }

    return {
        "simulations": simulations,
        "horizon_days": horizon_days,
        "shortfall_probability": float(
            np.mean(shortfall_paths)
        ),
        "safety_buffer_breach_probability": float(
            np.mean(ever_breached)
        ),
        "ending_balance_p05": ending_balance_p05,
        "ending_balance_median": ending_balance_median,
        "ending_balance_p95": ending_balance_p95,
        "minimum_balance_p05": float(
            np.percentile(minimum_balances, 5)
        ),
        "expected_minimum_balance": float(
            np.mean(minimum_balances)
        ),
        "expected_ending_balance": float(
            np.mean(ending_balances)
        ),
        "risk_metrics": {
            "confidence_level": RISK_CONFIDENCE_LEVEL,
            "ending_balance_var_95": ending_balance_p05,
            "ending_balance_cvar_95": _lower_tail_mean(
                ending_balances,
                TAIL_PROBABILITY,
            ),
            "minimum_balance_var_95": float(
                np.percentile(minimum_balances, 5)
            ),
            "minimum_balance_cvar_95": _lower_tail_mean(
                minimum_balances,
                TAIL_PROBABILITY,
            ),
            "expected_shortfall_severity": (
                expected_shortfall_severity
            ),
            "shortfall_path_count": int(
                np.sum(shortfall_paths)
            ),
        },
        "daily_balance_percentiles": daily_balance_percentiles,
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
        "breach_severity": breach_severity,
        "assumptions": {
            "starting_balance": float(starting_balance),
            "safety_buffer": float(safety_buffer),
            "inflow_clear_probability": inflow_clear_probability,
            "max_inflow_delay_days": max_inflow_delay_days,
            "max_outflow_uplift": max_outflow_uplift,
            "shock_correlation": shock_correlation,
            "unexpected_expense_probability": unexpected_expense_probability,
            "max_unexpected_expense": max_unexpected_expense,
            "seed": seed,
        },
    }
