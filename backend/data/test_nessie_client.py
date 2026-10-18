
"""Manual smoke test for the Nessie sandbox client.

Run from the project root with:
    python -m backend.data.test_nessie_client
"""

from backend.data.nessie_client import NessieClient


def main():
    client = NessieClient()

    account = client.get_account()
    deposits = client.get_deposits()
    withdrawals = client.get_withdrawals()

    print("Account retrieved:", bool(account))
    print("Deposits found:", len(deposits))
    print("Withdrawals found:", len(withdrawals))


if __name__ == "__main__":
    main()
