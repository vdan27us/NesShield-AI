
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"
ACCOUNT_ID = "4ffb71d7-a090-4b45-a617-f6ae570fd7d0"

if not API_KEY:
    raise RuntimeError("NESSIE_API_KEY was not found in .env")

url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/deposits"

payload = {
    "medium": "balance",
    "transaction_date": "2026-10-17",
    "status": "pending",
    "amount": 3000,
    "description": "Expected customer payment"
}

response = requests.post(
    url,
    params={"key": API_KEY},
    json=payload,
    timeout=15,
)

print("HTTP status:", response.status_code)

try:
    print(response.json())
except ValueError:
    print(response.text[:1000])
