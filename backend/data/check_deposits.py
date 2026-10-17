
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"
ACCOUNT_ID = "4ffb71d7-a090-4b45-a617-f6ae570fd7d0"

response = requests.get(
    f"{BASE_URL}/accounts/{ACCOUNT_ID}/deposits",
    params={"key": API_KEY},
    timeout=15,
)

print("HTTP status:", response.status_code)

if response.ok:
    deposits = response.json()
    print("Deposits found:", len(deposits))

    for deposit in deposits:
        print({
            "id": deposit.get("_id"),
            "amount": deposit.get("amount"),
            "status": deposit.get("status"),
            "date": deposit.get("transaction_date"),
            "description": deposit.get("description"),
        })
else:
    print(response.text[:1000])
