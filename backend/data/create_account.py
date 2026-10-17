
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"
CUSTOMER_ID = "81aad605-f139-48e1-9868-91cca9170dc0"

if not API_KEY:
    raise RuntimeError("NESSIE_API_KEY was not found in .env")

url = f"{BASE_URL}/customers/{CUSTOMER_ID}/accounts"

payload = {
    "type": "Checking",
    "nickname": "CashGuard Business",
    "rewards": 0,
    "balance": 10000,
    "account_number": "1234567890"
}

response = requests.post(
    url,
    params={"key": API_KEY},
    json=payload,
    timeout=15,
)

print("HTTP status:", response.status_code)

if response.status_code in (200, 201):
    data = response.json()
    print("Account created successfully.")
    print("Account ID:", data.get("objectCreated", {}).get("_id", data.get("_id")))
    print("Response:", data)
else:
    print("Account creation failed.")
    print(response.text[:1000])
