
from nessie_client import NessieClient


def main():
    client = NessieClient()

    account = client.get_account()
    deposits = client.get_deposits()
    withdrawals = client.get_withdrawals()

    print("Account:", account.get("nickname"))
    print("Current balance:", account.get("balance"))
    print("Deposits found:", len(deposits))
    print("Withdrawals found:", len(withdrawals))

    print("\nDeposits:")
    for item in deposits:
        print({
            "date": item.get("transaction_date"),
            "amount": item.get("amount"),
            "status": item.get("status"),
            "description": item.get("description"),
        })

    print("\nWithdrawals:")
    for item in withdrawals:
        print({
            "date": item.get("transaction_date"),
            "amount": item.get("amount"),
            "status": item.get("status"),
            "description": item.get("description"),
        })


if __name__ == "__main__":
    main()
