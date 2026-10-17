
from datetime import date, timedelta
from backend.data.nessie_client import NessieClient

def project_cashflow(days=7):
    client = NessieClient()

    account = client.get_account()
    deposits = client.get_deposits()
    withdrawals = client.get_withdrawals()

    balance = float(account["balance"])
    today = date.today()
    forecast = []

    for offset in range(days + 1):
        current_date = today + timedelta(days=offset)
        inflows = 0.0
        outflows = 0.0

        # Count only pending/future transactions on their scheduled dates.
        for deposit in deposits:
            transaction_date = date.fromisoformat(
                deposit["transaction_date"]
            )
            if transaction_date == current_date and deposit.get("status") == "pending":
                inflows += float(deposit["amount"])

        for withdrawal in withdrawals:
            transaction_date = date.fromisoformat(
                withdrawal["transaction_date"]
            )
            if transaction_date == current_date and withdrawal.get("status") == "pending":
                outflows += float(withdrawal["amount"])

        # Conservative baseline excludes pending deposits.
        balance -= outflows

        forecast.append({
            "date": current_date.isoformat(),
            "starting_balance": round(balance + outflows, 2),
            "scheduled_inflows": round(inflows, 2),
            "scheduled_outflows": round(outflows, 2),
            "projected_balance": round(balance, 2),
        })

    return forecast


if __name__ == "__main__":
    for day in project_cashflow():
        print(day)
