
"""Monte Carlo risk analysis using the shared simulation engine."""

from datetime import date, timedelta
from typing import Any

from backend.data.ledger import build_ledger
from backend.data.nessie_client import NessieClient
from backend.quant.simulation_engine import (
    SimulationEvent,
    simulate_cashflows,
)
from backend.ml.payment_timing_model import predict_synthetic_timing


SIMULATIONS = 10_000
HORIZON_DAYS = 14
DEPOSIT_CLEAR_PROBABILITY = 0.70
MAX_DEPOSIT_DELAY_DAYS = 3
MAX_OUTFLOW_UPLIFT = 0.15
SAFETY_BUFFER = 5_000.0
RANDOM_SEED = 42

# Zero preserves independent event shocks. Increase only when justified
# by an explicit modeling assumption or calibration.
SHOCK_CORRELATION = 0.35
UNEXPECTED_EXPENSE_PROBABILITY = 0.03
MAX_UNEXPECTED_EXPENSE = 1_000.0


def run_monte_carlo(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run Monte Carlo liquidity-risk analysis on pending Nessie transactions."""
    if snapshot is None:
        client = NessieClient()
        account = client.get_account()
        deposits = client.get_deposits()
        withdrawals = client.get_withdrawals()
    else:
        account = snapshot["account"]
        deposits = snapshot["deposits"]
        withdrawals = snapshot["withdrawals"]
    if not account:
        raise ValueError("Nessie returned no account.")

    starting_balance = float(account["balance"])
    today = date.today()
    end_date = today + timedelta(days=HORIZON_DAYS)

    ledger = build_ledger(
        deposits=deposits,
        withdrawals=withdrawals,
        today=today,
    )

    events: list[SimulationEvent] = []

    for item in ledger:
        if item.status not in {"pending", "scheduled"}:
            continue

        if item.effective_date > end_date:
            continue

        # Treat overdue pending transactions as occurring on day zero.
        event_day = max(0, (item.effective_date - today).days)

        timing = predict_synthetic_timing(
            amount=float(item.amount), kind=item.kind,
            weekday=(today + timedelta(days=event_day)).weekday(),
        )
        events.append(SimulationEvent(
            day=event_day, kind=item.kind, amount=float(item.amount),
            event_id=item.event_id,
            clear_probability=timing["clear_probability"],
            predicted_delay_days=timing["predicted_delay_days"],
            late_probability=timing["late_probability"],
        ))

    result = simulate_cashflows(
        starting_balance=starting_balance,
        events=events,
        horizon_days=HORIZON_DAYS,
        simulations=SIMULATIONS,
        safety_buffer=SAFETY_BUFFER,
        seed=RANDOM_SEED,
        inflow_clear_probability=DEPOSIT_CLEAR_PROBABILITY,
        max_inflow_delay_days=MAX_DEPOSIT_DELAY_DAYS,
        max_outflow_uplift=MAX_OUTFLOW_UPLIFT,
        shock_correlation=SHOCK_CORRELATION,
        unexpected_expense_probability=UNEXPECTED_EXPENSE_PROBABILITY,
        max_unexpected_expense=MAX_UNEXPECTED_EXPENSE,
    )

    return {
        "starting_balance": round(starting_balance, 2),
        "simulations": result["simulations"],
        "horizon_days": result["horizon_days"],
        "model_metadata": {
            "model_type": "assumption_based_monte_carlo",
            "payment_timing_calibration": "unavailable",
            "verified_settlement_history_available": False,
            "payment_timing_model": "Gradient Boosting trained on synthetic payer histories",
            "synthetic_model_influences_simulated_event_delay": True,
            "interpretation": (
                "Risk estimates are scenario-based and depend on "
                "configured assumptions; they are not validated "
                "real-world predictions."
            ),
        },
        "assumptions": {
            "deposit_clear_probability": DEPOSIT_CLEAR_PROBABILITY,
            "max_deposit_delay_days": MAX_DEPOSIT_DELAY_DAYS,
            "max_outflow_uplift": MAX_OUTFLOW_UPLIFT,
            "safety_buffer": SAFETY_BUFFER,
            "random_seed": RANDOM_SEED,
            "shock_correlation": SHOCK_CORRELATION,
            "unmodeled_event_fallback_clear_probability": DEPOSIT_CLEAR_PROBABILITY,
            "synthetic_timing_probability_used_when_available": True,
            "unexpected_expense_probability": UNEXPECTED_EXPENSE_PROBABILITY,
            "max_unexpected_expense": MAX_UNEXPECTED_EXPENSE,
        },
        "shortfall_probability": round(
            result["shortfall_probability"], 4
        ),
        "safety_buffer_breach_probability": round(
            result["safety_buffer_breach_probability"], 4
        ),
        "ending_balance_p05": round(
            result["ending_balance_p05"], 2
        ),
        "ending_balance_median": round(
            result["ending_balance_median"], 2
        ),
        "ending_balance_p95": round(
            result["ending_balance_p95"], 2
        ),
        "minimum_balance_p05": round(
            result["minimum_balance_p05"], 2
        ),
        "expected_minimum_balance": round(
            result["expected_minimum_balance"], 2
        ),
        "expected_ending_balance": round(
            result["expected_ending_balance"], 2
        ),
        "probability_of_breach_by_day": (
            result["probability_of_breach_by_day"]
        ),
        "time_to_first_buffer_breach": (
            result["time_to_first_buffer_breach"]
        ),
        "risk_metrics": result["risk_metrics"],
        "daily_balance_percentiles": (
            result["daily_balance_percentiles"]
        ),
        "breach_severity": result["breach_severity"],
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_monte_carlo(), indent=2))
