
from datetime import date

from backend.quant import cashflow


class FakeNessieClient:
    def get_account(self):
        return {"balance": 10000}

    def get_deposits(self):
        return [
            {
                "_id": "deposit-future",
                "amount": 3000,
                "transaction_date": "2026-10-19",
                "status": "pending",
            }
        ]

    def get_withdrawals(self):
        return [
            {
                "_id": "payroll-future",
                "amount": 7000,
                "transaction_date": "2026-10-20",
                "status": "pending",
            }
        ]


def test_forecast_preserves_conservative_pending_deposit_behavior(monkeypatch):
    monkeypatch.setattr(
        cashflow, "NessieClient", FakeNessieClient
    )
    monkeypatch.setattr(
        cashflow, "date", type("FixedDate", (), {
            "today": staticmethod(lambda: date(2026, 10, 18)),
        })
    )

    forecast = cashflow.project_cashflow(days=3)

    assert len(forecast) == 4

    # Pending deposit is displayed but not credited.
    assert forecast[1]["scheduled_inflows"] == 3000
    assert forecast[1]["projected_balance"] == 10000

    # Payroll is deducted on its scheduled date.
    assert forecast[2]["scheduled_outflows"] == 7000
    assert forecast[2]["projected_balance"] == 3000


def test_overdue_pending_deposit_is_visible_today(monkeypatch):
    class OverdueNessieClient(FakeNessieClient):
        def get_deposits(self):
            return [
                {
                    "_id": "deposit-overdue",
                    "amount": 500,
                    "transaction_date": "2026-10-17",
                    "status": "pending",
                }
            ]

        def get_withdrawals(self):
            return []

    monkeypatch.setattr(
        cashflow, "NessieClient", OverdueNessieClient
    )
    monkeypatch.setattr(
        cashflow, "date", type("FixedDate", (), {
            "today": staticmethod(lambda: date(2026, 10, 18)),
        })
    )

    forecast = cashflow.project_cashflow(days=0)

    assert forecast[0]["scheduled_inflows"] == 500
    assert forecast[0]["projected_balance"] == 10000
