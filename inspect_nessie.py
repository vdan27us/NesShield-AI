
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"

CUSTOMER_ID = "81aad605-f139-48e1-9868-91cca9170dc0"

if not API_KEY:
    raise SystemExit("API key missing. Check your .env file.")

try:
    response = requests.get(
        f"{BASE_URL}/customers/{CUSTOMER_ID}",
        params={"key": API_KEY},
        headers={"Accept": "application/json"},
        timeout=20,
    )

    print("HTTP status:", response.status_code)

    if response.ok:
        data = response.json()
        print("Customer retrieved successfully!")
        print("Customer data:")

        # Print only non-sensitive test fields
        print("First name:", data.get("first_name", "Not shown"))
        print("Last name:", data.get("last_name", "Not shown"))
        print("Customer ID:", data.get("_id", CUSTOMER_ID))
    else:
        print("Request failed:", response.text[:300])

except requests.RequestException as error:
    print("Connection error:", error)
except ValueError:
    print("The response was not valid JSON.")
