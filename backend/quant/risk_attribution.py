
"""Counterfactual attribution of simulated liquidity risk to events."""
from __future__ import annotations

from typing import Any

from backend.quant.simulation_engine import (
    SimulationEvent,
    generate_random_shocks,
    simulate_cashflows,
)


def run_risk_attribution(
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
    shock_correlation: float = 0.0,
) -> dict[str, Any]:
    """
    Estimate each event's risk contribution by removing it individually.

    Positive shortfall-risk contribution means removing the event
    reduces shortfall probability, so the event adds modeled risk.
    Negative contribution means the event is protective.

    Positive CVaR improvement means removing the event improves the
    lower-tail minimum balance. All comparisons reuse the same shocks.
    """
    if simulations < 1:
        raise ValueError("simulations must be at least 1")

    if horizon_days < 0:
        raise ValueError("horizon_days must be non-negative")

    if not 0.0 <= shock_correlation <= 1.0:
        raise ValueError("shock_correlation must be between 0 and 1")

    normalized_events = []
    seen_ids: set[str] = set()

    for index, event in enumerate(events):
        event_id = event.event_id or (
            f"attribution_{index}_{event.kind}_{event.day}"
        )

        if event_id in seen_ids:
            raise ValueError(
                f"Duplicate simulation event ID: {event_id}"
            )

        seen_ids.add(event_id)

        normalized_events.append(
            SimulationEvent(
                day=event.day,
                kind=event.kind,
                amount=event.amount,
                event_id=event_id,
            )
        )

    shocks = generate_random_shocks(
        events=normalized_events,
        simulations=simulations,
        seed=seed,
        max_inflow_delay_days=max_inflow_delay_days,
        max_outflow_uplift=max_outflow_uplift,
        shock_correlation=shock_correlation,
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
        "random_shocks": shocks,
        "shock_correlation": shock_correlation,
    }

    baseline = simulate_cashflows(
        events=normalized_events,
        **common_args,
    )

    baseline_cvar = baseline["risk_metrics"][
        "minimum_balance_cvar_95"
    ]

    drivers = []

    for event in normalized_events:
        counterfactual_events = [
            candidate
            for candidate in normalized_events
            if candidate.event_id != event.event_id
        ]

        without_event = simulate_cashflows(
            events=counterfactual_events,
            **common_args,
        )

        counterfactual_cvar = without_event["risk_metrics"][
            "minimum_balance_cvar_95"
        ]

        # Positive means the event raises modeled shortfall risk.
        shortfall_contribution = (
            baseline["shortfall_probability"]
            - without_event["shortfall_probability"]
        )

        # Positive means removing the event improves lower-tail balance.
        cvar_improvement_if_removed = (
            counterfactual_cvar - baseline_cvar
        )

        drivers.append(
            {
                "event_id": event.event_id,
                "kind": event.kind,
                "day": event.day,
                "amount": event.amount,
                "shortfall_probability_contribution": (
                    shortfall_contribution
                ),
                "safety_buffer_breach_probability_contribution": (
                    baseline["safety_buffer_breach_probability"]
                    - without_event[
                        "safety_buffer_breach_probability"
                    ]
                ),
                "minimum_balance_cvar_95_improvement_if_removed": (
                    cvar_improvement_if_removed
                ),
                "shortfall_probability_without_event": (
                    without_event["shortfall_probability"]
                ),
                "minimum_balance_cvar_95_without_event": (
                    counterfactual_cvar
                ),
            }
        )

    # Rank events by their modeled contribution to shortfall probability.
    drivers.sort(
        key=lambda item: (
            item["shortfall_probability_contribution"],
            item[
                "minimum_balance_cvar_95_improvement_if_removed"
            ],
        ),
        reverse=True,
    )

    for rank, driver in enumerate(drivers, start=1):
        driver["rank"] = rank

    return {
        "simulations": simulations,
        "horizon_days": horizon_days,
        "baseline": {
            "shortfall_probability": baseline["shortfall_probability"],
            "safety_buffer_breach_probability": (
                baseline["safety_buffer_breach_probability"]
            ),
            "minimum_balance_cvar_95": baseline_cvar,
            "minimum_balance_p05": baseline["minimum_balance_p05"],
        },
        "risk_drivers": drivers,
        "methodology": {
            "method": "one_event_at_a_time_counterfactual_removal",
            "common_random_numbers": True,
            "shock_correlation": shock_correlation,
            "interpretation": (
                "Positive contribution means removing the event improves "
                "the corresponding risk metric. Negative contribution "
                "means the event is protective under this model. "
                "Contributions are counterfactual comparisons and are "
                "not additive or causal estimates."
            ),
        },
    }
