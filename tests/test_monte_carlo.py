
from datetime import date

from backend.quant import monte_carlo


class FakeNessieClient:
    def get_account(self):
        return {"balance": 10_000}

    def get_deposits(self):
        return [
            {
                "_id": "future-deposit",
                "amount": 2_000,
                "transaction_date": "2026-10-19",
                "status": "pending",
            },
            {
                "_id": "posted-deposit",
                "amount": 5_000,
                "transaction_date": "2026-10-18",
                "status": "posted",
            },
        ]

    def get_withdrawals(self):
        return [
            {
                "_id": "future-withdrawal",
                "amount": 1_000,
                "transaction_date": "2026-10-20",
                "status": "pending",
            },
            {
                "_id": "outside-horizon",
                "amount": 9_000,
                "transaction_date": "2026-10-30",
                "status": "pending",
            },
        ]


class FixedDate:
    @staticmethod
    def today():
        return date(2026, 10, 18)


def configure_test(monkeypatch):
    monkeypatch.setattr(
        monte_carlo, "NessieClient", FakeNessieClient
    )
    monkeypatch.setattr(monte_carlo, "date", FixedDate)
    monkeypatch.setattr(monte_carlo, "SIMULATIONS", 100)
    monkeypatch.setattr(monte_carlo, "HORIZON_DAYS", 7)
    monkeypatch.setattr(
        monte_carlo, "DEPOSIT_CLEAR_PROBABILITY", 1.0
    )
    monkeypatch.setattr(
        monte_carlo, "MAX_DEPOSIT_DELAY_DAYS", 0
    )
    monkeypatch.setattr(monte_carlo, "MAX_OUTFLOW_UPLIFT", 0.0)
    monkeypatch.setattr(monte_carlo, "SAFETY_BUFFER", 5_000)
    monkeypatch.setattr(monte_carlo, "RANDOM_SEED", 42)


def test_monte_carlo_preserves_api_response_fields(monkeypatch):
    configure_test(monkeypatch)

    result = monte_carlo.run_monte_carlo()

    expected_keys = {
        "starting_balance",
        "simulations",
        "horizon_days",
        "assumptions",
        "shortfall_probability",
        "safety_buffer_breach_probability",
        "ending_balance_p05",
        "ending_balance_median",
        "ending_balance_p95",
        "minimum_balance_p05",
    }

    assert expected_keys.issubset(result.keys())
    assert result["starting_balance"] == 10_000
    assert result["simulations"] == 100
    assert result["horizon_days"] == 7


def test_monte_carlo_is_reproducible(monkeypatch):
    configure_test(monkeypatch)

    first = monte_carlo.run_monte_carlo()
    second = monte_carlo.run_monte_carlo()

    assert first == second


def test_overdue_pending_withdrawal_is_included(monkeypatch):
    configure_test(monkeypatch)

    class OverdueNessieClient(FakeNessieClient):
        def get_deposits(self):
            return []

        def get_withdrawals(self):
            return [
                {
                    "_id": "overdue-withdrawal",
                    "amount": 12_000,
                    "transaction_date": "2026-10-17",
                    "status": "pending",
                }
            ]

    monkeypatch.setattr(
        monte_carlo, "NessieClient", OverdueNessieClient
    )

    result = monte_carlo.run_monte_carlo()

    assert result["shortfall_probability"] == 1.0


def test_posted_transactions_are_not_simulated(monkeypatch):
    configure_test(monkeypatch)

    class PostedOnlyNessieClient(FakeNessieClient):
        def get_deposits(self):
            return [
                {
                    "_id": "posted-deposit",
                    "amount": 5_000,
                    "transaction_date": "2026-10-18",
                    "status": "posted",
                }
            ]

        def get_withdrawals(self):
            return [
                {
                    "_id": "posted-withdrawal",
                    "amount": 9_000,
                    "transaction_date": "2026-10-18",
                    "status": "posted",
                }
            ]

    monkeypatch.setattr(
        monte_carlo, "NessieClient", PostedOnlyNessieClient
    )

    result = monte_carlo.run_monte_carlo()

    assert result["ending_balance_median"] == 10_000
    assert result["shortfall_probability"] == 0.0
