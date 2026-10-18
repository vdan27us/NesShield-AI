
from datetime import date, timedelta

from backend.data.ledger import build_ledger
from backend.data.nessie_client import NessieClient


def project_cashflow(days=7, snapshot=None):
    if days < 0:
        raise ValueError("days must be non-negative")

    if snapshot is None:
        client = NessieClient()
        account = client.get_account()
        deposits = client.get_deposits()
        withdrawals = client.get_withdrawals()
    else:
        account = snapshot["account"]
        deposits = snapshot["deposits"]
        withdrawals = snapshot["withdrawals"]

    today = date.today()
    ledger = build_ledger(
        deposits=deposits,
        withdrawals=withdrawals,
        today=today,
    )

    balance = float(account["balance"])
    forecast = []

    for offset in range(days + 1):
        current_date = today + timedelta(days=offset)
        starting_balance = balance
        inflows = 0.0
        outflows = 0.0

        for event in ledger:
            if event.effective_date != current_date:
                continue

            # Keep the existing conservative baseline:
            # pending deposits are shown but not credited to the balance.
            if event.kind == "inflow":
                if event.status == "pending":
                    inflows += event.amount
            elif event.kind == "outflow":
                if event.status in {"pending", "scheduled"}:
                    outflows += event.amount

        balance -= outflows

        forecast.append(
            {
                "date": current_date.isoformat(),
                "starting_balance": round(starting_balance, 2),
                "scheduled_inflows": round(inflows, 2),
                "scheduled_outflows": round(outflows, 2),
                "projected_balance": round(balance, 2),
            }
        )

    return forecast


if __name__ == "__main__":
    for day in project_cashflow():
        print(day)
