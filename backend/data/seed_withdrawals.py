
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"
ACCOUNT_ID = "4ffb71d7-a090-4b45-a617-f6ae570fd7d0"

withdrawal = {
    "medium": "balance",
    "transaction_date": "2026-10-20",
    "status": "pending",
    "amount": 7000,
    "description": "Simulated upcoming payroll",
}

response = requests.post(
    f"{BASE_URL}/accounts/{ACCOUNT_ID}/withdrawals",
    params={"key": API_KEY},
    json=withdrawal,
    timeout=15,
)

print("HTTP status:", response.status_code)
print(response.text[:2000])
