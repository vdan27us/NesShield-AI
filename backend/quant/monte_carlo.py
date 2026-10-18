
"""Monte Carlo risk analysis using the shared simulation engine."""
from datetime import date, timedelta

from backend.data.ledger import build_ledger
from backend.data.nessie_client import NessieClient
from backend.quant.simulation_engine import (
    SimulationEvent,
    simulate_cashflows,
)


SIMULATIONS = 10_000
HORIZON_DAYS = 7
DEPOSIT_CLEAR_PROBABILITY = 0.70
MAX_DEPOSIT_DELAY_DAYS = 3
MAX_OUTFLOW_UPLIFT = 0.15
SAFETY_BUFFER = 5_000
RANDOM_SEED = 42


def run_monte_carlo():
    """Run risk analysis against pending Nessie transactions."""
    client = NessieClient()

    account = client.get_account()
    deposits = client.get_deposits()
    withdrawals = client.get_withdrawals()

    starting_balance = float(account["balance"])
    today = date.today()
    end_date = today + timedelta(days=HORIZON_DAYS)

    ledger = build_ledger(
        deposits=deposits,
        withdrawals=withdrawals,
        today=today,
    )

    events = []

    for item in ledger:
        # Preserve the existing pending-transaction scope.
        if item.status != "pending":
            continue

        # Include overdue pending transactions as due today.
        # Ignore transactions beyond the simulation horizon.
        if item.effective_date > end_date:
            continue

        event_day = max(
            0,
            (item.effective_date - today).days,
        )

        events.append(
            SimulationEvent(
                day=event_day,
                kind=item.kind,
                amount=item.amount,
                event_id=item.event_id,
            )
        )

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
    )

    # Preserve existing API response fields for the frontend.
    return {
        "starting_balance": round(starting_balance, 2),
        "simulations": result["simulations"],
        "horizon_days": result["horizon_days"],
        "assumptions": {
            "deposit_clear_probability": (
                DEPOSIT_CLEAR_PROBABILITY
            ),
            "max_deposit_delay_days": (
                MAX_DEPOSIT_DELAY_DAYS
            ),
            "max_outflow_uplift": MAX_OUTFLOW_UPLIFT,
            "safety_buffer": SAFETY_BUFFER,
            "random_seed": RANDOM_SEED,
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
        # Additional diagnostics for later dashboard improvements.
        "expected_minimum_balance": round(
            result["expected_minimum_balance"], 2
        ),
        "expected_ending_balance": round(
            result["expected_ending_balance"], 2
        ),
        "probability_of_breach_by_day": result[
            "probability_of_breach_by_day"
        ],
        "time_to_first_buffer_breach": result[
            "time_to_first_buffer_breach"
        ],
    }


if __name__ == "__main__":
    results = run_monte_carlo()

    print("\n=== Nesshield AI: Monte Carlo Risk Report ===")

    for key, value in results.items():
        print(f"{key}: {value}")
