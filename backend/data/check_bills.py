
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://prod-api.nessieisreal.com"

# Try retrieving the bills through the customer endpoint.
CUSTOMER_ID = "81aad605-f139-48e1-9868-91cca9170dc0"

response = requests.get(
    f"{BASE_URL}/customers/{CUSTOMER_ID}/bills",
    params={"key": API_KEY},
    timeout=15,
)

print("HTTP status:", response.status_code)
print(response.text[:3000])
