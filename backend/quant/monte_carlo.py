
import random
from datetime import date, timedelta

from backend.data.nessie_client import NessieClient


# Explicit demo assumptions — these are NOT learned probabilities.
SIMULATIONS = 10_000
HORIZON_DAYS = 7
DEPOSIT_CLEAR_PROBABILITY = 0.70
MAX_DEPOSIT_DELAY_DAYS = 3
MAX_OUTFLOW_UPLIFT = 0.15
SAFETY_BUFFER = 5_000
RANDOM_SEED = 42


def run_monte_carlo():
    random.seed(RANDOM_SEED)

    client = NessieClient()
    account = client.get_account()
    deposits = client.get_deposits()
    withdrawals = client.get_withdrawals()

    starting_balance = float(account["balance"])
    today = date.today()
    end_date = today + timedelta(days=HORIZON_DAYS)

    # Only pending transactions scheduled within our forecast horizon.
    pending_deposits = [
        item for item in deposits
        if item.get("status") == "pending"
        and today <= date.fromisoformat(item["transaction_date"]) <= end_date
    ]

    pending_withdrawals = [
        item for item in withdrawals
        if item.get("status") == "pending"
        and today <= date.fromisoformat(item["transaction_date"]) <= end_date
    ]

    ending_balances = []
    minimum_balances = []
    shortfalls = 0
    buffer_breaches = 0

    for _ in range(SIMULATIONS):
        balance = starting_balance
        lowest_balance = balance

        # Build daily events for this simulated scenario.
        events = {}

        for deposit in pending_deposits:
            scheduled = date.fromisoformat(deposit["transaction_date"])

            # Assume a pending deposit clears with a configurable probability.
            if random.random() < DEPOSIT_CLEAR_PROBABILITY:
                delay = random.randint(0, MAX_DEPOSIT_DELAY_DAYS)
                arrival = scheduled + timedelta(days=delay)

                if arrival <= end_date:
                    events.setdefault(arrival, []).append(
                        ("inflow", float(deposit["amount"]))
                    )

        for withdrawal in pending_withdrawals:
            scheduled = date.fromisoformat(withdrawal["transaction_date"])

            # Assume the scheduled withdrawal occurs, with an illustrative
            # 0–15% uplift to represent uncertainty in outflow amount.
            uplift = random.uniform(0, MAX_OUTFLOW_UPLIFT)
            amount = float(withdrawal["amount"]) * (1 + uplift)

            events.setdefault(scheduled, []).append(("outflow", amount))

        for offset in range(HORIZON_DAYS + 1):
            current_date = today + timedelta(days=offset)

            for event_type, amount in events.get(current_date, []):
                if event_type == "inflow":
                    balance += amount
                else:
                    balance -= amount

            lowest_balance = min(lowest_balance, balance)

        ending_balances.append(balance)
        minimum_balances.append(lowest_balance)

        if lowest_balance < 0:
            shortfalls += 1

        if lowest_balance < SAFETY_BUFFER:
            buffer_breaches += 1

    ending_balances.sort()

    def percentile(values, p):
        index = int((len(values) - 1) * p)
        return values[index]

    return {
        "starting_balance": round(starting_balance, 2),
        "simulations": SIMULATIONS,
        "horizon_days": HORIZON_DAYS,
        "assumptions": {
            "deposit_clear_probability": DEPOSIT_CLEAR_PROBABILITY,
            "max_deposit_delay_days": MAX_DEPOSIT_DELAY_DAYS,
            "max_outflow_uplift": MAX_OUTFLOW_UPLIFT,
            "safety_buffer": SAFETY_BUFFER,
            "random_seed": RANDOM_SEED,
        },
        "shortfall_probability": round(
            shortfalls / SIMULATIONS, 4
        ),
        "safety_buffer_breach_probability": round(
            buffer_breaches / SIMULATIONS, 4
        ),
        "ending_balance_p05": round(
            percentile(ending_balances, 0.05), 2
        ),
        "ending_balance_median": round(
            percentile(ending_balances, 0.50), 2
        ),
        "ending_balance_p95": round(
            percentile(ending_balances, 0.95), 2
        ),
        "minimum_balance_p05": round(
            percentile(sorted(minimum_balances), 0.05), 2
        ),
    }


if __name__ == "__main__":
    results = run_monte_carlo()

    print("\n=== CashGuard AI: Monte Carlo Risk Report ===")
    for key, value in results.items():
        print(f"{key}: {value}")
