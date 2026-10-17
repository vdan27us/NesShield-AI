
from pathlib import Path

import joblib
import pandas as pd

from backend.data.nessie_client import NessieClient


MODEL_PATH = Path("backend/ml/risk_model.joblib")


def main():
    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"]
    features = bundle["features"]

    client = NessieClient()
    account = client.get_account()
    deposits = client.get_deposits()
    withdrawals = client.get_withdrawals()

    starting_balance = float(account["balance"])

    pending_deposits = [
        d for d in deposits if d.get("status") == "pending"
    ]
    pending_withdrawals = [
        w for w in withdrawals if w.get("status") == "pending"
    ]

    expected_inflows = sum(
        float(d["amount"]) for d in pending_deposits
    )
    scheduled_outflows = sum(
        float(w["amount"]) for w in pending_withdrawals
    )

    # Explicit demo assumptions, not learned from Nessie.
    scenario = {
        "starting_balance": starting_balance,
        "expected_inflows": expected_inflows,
        "scheduled_outflows": scheduled_outflows,
        "inflow_delay_days": 3,
        "outflow_uplift": 0.10,
        "other_expenses": 0.0,
    }

    X = pd.DataFrame([scenario], columns=features)
    probability = model.predict_proba(X)[0, 1]
    prediction = int(model.predict(X)[0])

    print("\n=== CashGuard AI: ML Scenario Assessment ===")
    print("Account:", account.get("nickname"))
    print("Starting balance:", f"${starting_balance:,.2f}")
    print("Pending inflows:", f"${expected_inflows:,.2f}")
    print("Pending outflows:", f"${scheduled_outflows:,.2f}")
    print("Assumed inflow delay:", scenario["inflow_delay_days"], "days")
    print("Assumed outflow uplift:", f'{scenario["outflow_uplift"]:.0%}')
    print("Assumed other expenses:", f'${scenario["other_expenses"]:,.2f}')
    print("Predicted shortfall class:", prediction)
    print("Model score:", f"{probability:.1%}")

    print(
        "\nNote: this score comes from a model trained on synthetic data. "
        "It is not a calibrated real-world probability of business failure."
    )


if __name__ == "__main__":
    main()
