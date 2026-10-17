
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"
CUSTOMER_ID = "81aad605-f139-48e1-9868-91cca9170dc0"

url = f"{BASE_URL}/customers/{CUSTOMER_ID}/accounts"

response = requests.get(
    url,
    params={"key": API_KEY},
    timeout=15,
)

print("HTTP status:", response.status_code)

if response.ok:
    accounts = response.json()
    print("Accounts found:", len(accounts))

    for account in accounts:
        print({
            "id": account.get("_id"),
            "type": account.get("type"),
            "nickname": account.get("nickname"),
            "balance": account.get("balance"),
        })
else:
    print("Request failed:", response.text[:500])
