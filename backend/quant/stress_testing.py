
"""Deterministic stress scenarios for Nesshield AI liquidity risk."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from backend.quant.simulation_engine import (
    SimulationEvent,
    generate_random_shocks,
    simulate_cashflows,
)


@dataclass(frozen=True)
class StressScenario:
    """Explicit, reproducible changes applied to a baseline cash-flow plan."""

    name: str
    inflow_delay_days: int = 0
    inflow_reduction_fraction: float = 0.0
    outflow_multiplier: float = 1.0
    unexpected_outflow_amount: float = 0.0
    unexpected_outflow_day: int = 1


def default_stress_scenarios(
    horizon_days: int,
) -> list[StressScenario]:
    """Return the standard stress scenarios for liquidity analysis."""
    expense_day = min(1, horizon_days)

    return [
        StressScenario(
            name="deposit_delays",
            inflow_delay_days=2,
        ),
        StressScenario(
            name="reduced_inflows",
            inflow_reduction_fraction=0.25,
        ),
        StressScenario(
            name="unexpected_expense",
            unexpected_outflow_amount=1_000.0,
            unexpected_outflow_day=expense_day,
        ),
        StressScenario(
            name="combined_adverse",
            inflow_delay_days=2,
            inflow_reduction_fraction=0.25,
            outflow_multiplier=1.20,
            unexpected_outflow_amount=1_500.0,
            unexpected_outflow_day=expense_day,
        ),
    ]


def _validate_scenario(
    scenario: StressScenario,
    horizon_days: int,
) -> None:
    if not scenario.name.strip():
        raise ValueError("Scenario name must not be empty")

    if scenario.inflow_delay_days < 0:
        raise ValueError("inflow_delay_days must be non-negative")

    if not 0 <= scenario.inflow_reduction_fraction <= 1:
        raise ValueError(
            "inflow_reduction_fraction must be between 0 and 1"
        )

    if scenario.outflow_multiplier < 1:
        raise ValueError("outflow_multiplier must be at least 1")

    if scenario.unexpected_outflow_amount < 0:
        raise ValueError(
            "unexpected_outflow_amount must be non-negative"
        )

    if scenario.unexpected_outflow_day < 0:
        raise ValueError(
            "unexpected_outflow_day must be non-negative"
        )

    if scenario.unexpected_outflow_day > horizon_days:
        raise ValueError(
            "unexpected_outflow_day must be within the horizon"
        )

    values = (
        scenario.inflow_reduction_fraction,
        scenario.outflow_multiplier,
        scenario.unexpected_outflow_amount,
    )

    if any(value != value or value in (float("inf"), float("-inf"))
           for value in values):
        raise ValueError("Scenario numeric values must be finite")


def _stable_events(
    events: list[SimulationEvent],
) -> list[SimulationEvent]:
    """Give anonymous events stable IDs for cross-scenario comparisons."""
    result = []
    seen: set[str] = set()

    for index, event in enumerate(events):
        event_id = event.event_id or (
            f"stress_base_{index}_{event.kind}_{event.day}"
        )

        if event_id in seen:
            raise ValueError(
                f"Duplicate simulation event ID: {event_id}"
            )

        seen.add(event_id)
        result.append(replace(event, event_id=event_id))

    return result


def _apply_scenario(
    events: list[SimulationEvent],
    scenario: StressScenario,
) -> list[SimulationEvent]:
    """Create scenario events without mutating the baseline events."""
    stressed_events = []

    for event in events:
        if event.kind == "inflow":
            stressed_events.append(
                replace(
                    event,
                    day=event.day + scenario.inflow_delay_days,
                    amount=event.amount
                    * (1.0 - scenario.inflow_reduction_fraction),
                )
            )
        else:
            stressed_events.append(
                replace(
                    event,
                    amount=event.amount * scenario.outflow_multiplier,
                )
            )

    if scenario.unexpected_outflow_amount > 0:
        stressed_events.append(
            SimulationEvent(
                day=scenario.unexpected_outflow_day,
                kind="outflow",
                amount=scenario.unexpected_outflow_amount,
                event_id=f"stress_expense_{scenario.name}",
            )
        )

    return stressed_events


def _summarize(result: dict[str, Any]) -> dict[str, Any]:
    """Select the comparable risk metrics from a simulation result."""
    risk = result["risk_metrics"]

    return {
        "shortfall_probability": result["shortfall_probability"],
        "safety_buffer_breach_probability": (
            result["safety_buffer_breach_probability"]
        ),
        "ending_balance_p05": result["ending_balance_p05"],
        "ending_balance_median": result["ending_balance_median"],
        "ending_balance_p95": result["ending_balance_p95"],
        "minimum_balance_p05": result["minimum_balance_p05"],
        "ending_balance_cvar_95": risk["ending_balance_cvar_95"],
        "minimum_balance_cvar_95": risk["minimum_balance_cvar_95"],
        "expected_shortfall_severity": (
            risk["expected_shortfall_severity"]
        ),
        "time_to_first_buffer_breach": (
            result["time_to_first_buffer_breach"]
        ),
    }


def run_stress_tests(
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
    scenarios: list[StressScenario] | None = None,
) -> dict[str, Any]:
    """
    Compare baseline liquidity risk with adverse scenarios.

    Common random numbers are reused for shared event IDs, helping
    isolate the effect of scenario changes from simulation noise.
    """
    if horizon_days < 0:
        raise ValueError("horizon_days must be non-negative")

    if simulations < 1:
        raise ValueError("simulations must be at least 1")

    baseline_events = _stable_events(events)
    scenarios = (
        default_stress_scenarios(horizon_days)
        if scenarios is None
        else list(scenarios)
    )

    scenario_names: set[str] = set()

    for scenario in scenarios:
        _validate_scenario(scenario, horizon_days)

        if scenario.name in scenario_names:
            raise ValueError(
                f"Duplicate stress scenario name: {scenario.name}"
            )

        scenario_names.add(scenario.name)

    transformed: dict[str, list[SimulationEvent]] = {
        scenario.name: _apply_scenario(baseline_events, scenario)
        for scenario in scenarios
    }

    # Generate one shock set for all distinct event IDs across scenarios.
    # Existing events keep their IDs, so their random draws are shared.
    all_events_by_id: dict[str, SimulationEvent] = {}

    for event in baseline_events:
        all_events_by_id[event.event_id] = event

    for scenario_events in transformed.values():
        for event in scenario_events:
            all_events_by_id.setdefault(event.event_id, event)

    all_events = list(all_events_by_id.values())

    random_shocks = generate_random_shocks(
        events=all_events,
        simulations=simulations,
        seed=seed,
        max_inflow_delay_days=max_inflow_delay_days,
        max_outflow_uplift=max_outflow_uplift,
    )

    common_args = {
        "starting_balance": starting_balance,
        "horizon_days": horizon_days,
        "simulations": simulations,
        "safety_buffer": safety_buffer,
        "seed": seed,
        "inflow_clear_probability": inflow_clear_probability,
        "max_inflow_delay_days": max_inflow_delay_days,
        "max_outflow_uplift": max_outflow_uplift,
        "random_shocks": random_shocks,
    }

    baseline_result = simulate_cashflows(
        events=baseline_events,
        **common_args,
    )
    baseline_summary = _summarize(baseline_result)

    results: dict[str, Any] = {}

    for scenario in scenarios:
        scenario_result = simulate_cashflows(
            events=transformed[scenario.name],
            **common_args,
        )
        scenario_summary = _summarize(scenario_result)

        deltas = {}

        for metric, value in scenario_summary.items():
            if isinstance(value, (int, float)) and isinstance(
                baseline_summary[metric], (int, float)
            ):
                deltas[metric] = value - baseline_summary[metric]

        results[scenario.name] = {
            "assumptions": asdict(scenario),
            "metrics": scenario_summary,
            "change_vs_baseline": deltas,
        }

    return {
        "simulations": simulations,
        "horizon_days": horizon_days,
        "baseline": baseline_summary,
        "scenarios": results,
        "methodology": {
            "common_random_numbers": True,
            "random_seed": seed,
            "confidence_level": 0.95,
            "note": (
                "Stress scenarios are deterministic assumption changes, "
                "not forecasts of event likelihood. The standard scenarios "
                "are illustrative and should be calibrated to account data."
            ),
        },
    }
