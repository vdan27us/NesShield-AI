
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"
ACCOUNT_ID = "4ffb71d7-a090-4b45-a617-f6ae570fd7d0"



bills = [
    {
        "status": "pending",
        "payee": "Business Payroll",
        "nickname": "Upcoming payroll",
        "payment_date": "2026-10-20",
        "recurring_date": 20,
        "payment_amount": 7000,
    },
    {
        "status": "pending",
        "payee": "Office Supplies Supplier",
        "nickname": "Supplier invoice",
        "payment_date": "2026-10-22",
        "recurring_date": 22,
        "payment_amount": 4500,
    },
]



for bill in bills:
    response = requests.post(
        f"{BASE_URL}/accounts/{ACCOUNT_ID}/bills",
        params={"key": API_KEY},
        json=bill,
        timeout=15,
    )

    print(f"\nCreating: {bill['nickname']}")
    print("HTTP status:", response.status_code)
    print(response.text[:500])
