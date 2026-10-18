
from fastapi.testclient import TestClient

from backend import api


client = TestClient(api.app)


def test_health_endpoint():
    response = client.get("/api/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Nesshield AI"


def test_forecast_endpoint_preserves_response_shape(monkeypatch):
    fake_forecast = [
        {
            "date": "2026-10-18",
            "starting_balance": 10_000,
            "scheduled_inflows": 500,
            "scheduled_outflows": 200,
            "projected_balance": 9_800,
        }
    ]

    monkeypatch.setattr(
        api,
        "project_cashflow",
        lambda days=7: fake_forecast,
    )

    response = client.get("/api/forecast")

    assert response.status_code == 200
    assert response.json() == {"forecast": fake_forecast}


def test_risk_endpoint_preserves_response_shape(monkeypatch):
    fake_risk = {
        "starting_balance": 10_000,
        "simulations": 100,
        "horizon_days": 7,
        "shortfall_probability": 0.05,
        "safety_buffer_breach_probability": 0.15,
    }

    monkeypatch.setattr(
        api,
        "run_monte_carlo",
        lambda: fake_risk,
    )

    response = client.get("/api/risk")

    assert response.status_code == 200
    assert response.json() == {"monte_carlo": fake_risk}


def test_what_if_endpoint_preserves_response_shape(monkeypatch):
    fake_account = {
        "nickname": "Test account",
        "balance": 10_000,
        "type": "Checking",
    }

    monkeypatch.setattr(
        api,
        "get_account_data",
        lambda: (object(), fake_account),
    )

    fake_risk = {
        "simulations": 100,
        "shortfall_probability": 0.0,
        "safety_buffer_breach_probability": 0.1,
    }

    fake_forecast = [
        {
            "day": day,
            "label": "Today" if day == 0 else f"Day {day}",
            "projected_balance": 10_000.0,
        }
        for day in range(8)
    ]

    monkeypatch.setattr(
        api,
        "run_what_if_simulation",
        lambda **kwargs: (fake_risk, fake_forecast, 10_000.0),
    )

    monkeypatch.setattr(
        api,
        "generate_financial_briefing",
        lambda data: "Test briefing",
    )

    response = client.post(
        "/api/what-if",
        json={
            "payroll_amount": 3_000,
            "deposit_amount": 2_000,
            "deposit_delay_days": 2,
            "safety_buffer": 5_000,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["projected_ending_balance"] == 10_000.0
    assert data["forecast"] == fake_forecast
    assert data["monte_carlo"] == fake_risk
    assert data["briefing"] == "Test briefing"
    assert "scenario" in data
    assert "data_source" in data


def test_what_if_rejects_invalid_request():
    response = client.post(
        "/api/what-if",
        json={
            "payroll_amount": -1,
            "deposit_amount": 2_000,
            "deposit_delay_days": 2,
            "safety_buffer": 5_000,
        },
    )

    assert response.status_code == 422


def test_stress_test_endpoint_validates_simulation_count():
    response = client.get("/api/stress-test?simulations=10")
    assert response.status_code == 422


def test_risk_attribution_endpoint_validates_simulation_count():
    response = client.get("/api/risk-attribution?simulations=10")
    assert response.status_code == 422


def test_stress_test_endpoint_validates_correlation():
    response = client.get("/api/stress-test?shock_correlation=1.5")
    assert response.status_code == 422


def test_risk_attribution_endpoint_validates_correlation():
    response = client.get(
        "/api/risk-attribution?shock_correlation=-0.1"
    )
    assert response.status_code == 422



def test_payment_timing_endpoint_reports_missing_settlement_history(
    monkeypatch,
):
    class FakeClient:
        def get_deposits(self):
            return [{"amount": 100, "transaction_date": "2026-10-10"}]

        def get_withdrawals(self):
            return [{"amount": 50, "transaction_date": "2026-10-11"}]

    monkeypatch.setattr(api, "get_client", lambda: FakeClient())

    response = client.get("/api/payment-timing")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["estimated_delay_days"] is None
    assert data["transactions_inspected"] == 2
    assert "settlement" in data["reason"].lower()


def test_payment_timing_endpoint_handles_nessie_errors(monkeypatch):
    class BrokenClient:
        def get_deposits(self):
            raise RuntimeError("Simulated upstream failure")

    monkeypatch.setattr(api, "get_client", lambda: BrokenClient())

    response = client.get("/api/payment-timing")

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Unable to inspect payment-timing data."
    )
