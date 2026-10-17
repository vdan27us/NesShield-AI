
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://prod-api.nessieisreal.com"
API_KEY = os.getenv("NESSIE_API_KEY")
ACCOUNT_ID = "4ffb71d7-a090-4b45-a617-f6ae570fd7d0"


class NessieClient:
    def __init__(self):
        if not API_KEY:
            raise RuntimeError(
                "NESSIE_API_KEY is missing. Check your .env file."
            )

        self.session = requests.Session()
        self.session.params = {"key": API_KEY}

    def get_account(self):
        response = self.session.get(
            f"{BASE_URL}/accounts/{ACCOUNT_ID}", timeout=15
        )
        response.raise_for_status()
        return response.json()

    def get_deposits(self):
        response = self.session.get(
            f"{BASE_URL}/accounts/{ACCOUNT_ID}/deposits", timeout=15
        )
        response.raise_for_status()
        return response.json()

    def get_withdrawals(self):
        response = self.session.get(
            f"{BASE_URL}/accounts/{ACCOUNT_ID}/withdrawals", timeout=15
        )
        response.raise_for_status()
        return response.json()
