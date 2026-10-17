
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"
ACCOUNT_ID = "4ffb71d7-a090-4b45-a617-f6ae570fd7d0"

response = requests.get(
    f"{BASE_URL}/accounts/{ACCOUNT_ID}/withdrawals",
    params={"key": API_KEY},
    timeout=15,
)

print("HTTP status:", response.status_code)
print(response.text[:3000])
