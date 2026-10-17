
from pathlib import Path

import logging

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.data.nessie_client import NessieClient
from backend.quant.cashflow import project_cashflow
from backend.quant.monte_carlo import run_monte_carlo

from backend.services.gemini_briefing import generate_financial_briefing

from pydantic import BaseModel, Field
from backend.services.what_if import run_what_if_simulation

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "ml" / "risk_model.joblib"

app = FastAPI(
    title="Nesshield AI API",
    description=(
        "Predictive cash-flow forecasting, Monte Carlo simulations, "
        "and ML-based scenario risk assessment."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client():
    return NessieClient()


def get_account_data():
    client = get_client()
    account = client.get_account()

    if not account:
        raise ValueError("Nessie returned no account.")

    return client, account


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "Nesshield AI",
        "version": app.version,
    }


@app.get("/api/account")
def account():
    try:
        _, data = get_account_data()

        return {
            "nickname": data.get("nickname"),
            "balance": data.get("balance"),
            "type": data.get("type"),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve account: {exc}",
        ) from exc


@app.get("/api/forecast")
def forecast():
    try:
        results = project_cashflow(days=7)
        return {"forecast": results}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to calculate cash-flow forecast: {exc}",
        ) from exc


@app.get("/api/risk")
def risk():
    try:
        results = run_monte_carlo()
        return {"monte_carlo": results}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to calculate Monte Carlo risk: {exc}",
        ) from exc


@app.get("/api/ml-risk")
def ml_risk():
    """
    Score a scenario using the existing Random Forest model.

    IMPORTANT:
    The model was trained on synthetic scenarios. Its score is not
    a calibrated real-world probability of business failure.
    """
    try:
        if not MODEL_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail="Trained ML model not found. Train the model first.",
            )

        bundle = joblib.load(MODEL_PATH)
        model = bundle["model"]
        features = bundle["features"]

        client, account_data = get_account_data()

        deposits = client.get_deposits()
        withdrawals = client.get_withdrawals()

        pending_deposits = [
            item
            for item in deposits
            if item.get("status") == "pending"
        ]

        pending_withdrawals = [
            item
            for item in withdrawals
            if item.get("status") == "pending"
        ]

        expected_inflows = sum(
            float(item.get("amount", 0))
            for item in pending_deposits
        )

        scheduled_outflows = sum(
            float(item.get("amount", 0))
            for item in pending_withdrawals
        )

        scenario = {
            "starting_balance": float(account_data["balance"]),
            "expected_inflows": expected_inflows,
            "scheduled_outflows": scheduled_outflows,
            "inflow_delay_days": 3,
            "outflow_uplift": 0.10,
            "other_expenses": 0.0,
        }

        # Match the feature names and order used during training.
        input_data = pd.DataFrame(
            [{name: scenario[name] for name in features}],
            columns=features,
        )

        prediction = int(model.predict(input_data)[0])
        probabilities = model.predict_proba(input_data)[0]

        classes = list(model.classes_)
        positive_class_index = (
            classes.index(1) if 1 in classes else None
        )

        score = (
            float(probabilities[positive_class_index])
            if positive_class_index is not None
            else None
        )

        return {
            "model": "Random Forest",
            "prediction": prediction,
            "prediction_label": (
                "Potential shortfall scenario"
                if prediction == 1
                else "No shortfall predicted by the model"
            ),
            "model_score": score,
            "score_interpretation": (
                "Model score for the synthetic shortfall class; "
                "not a calibrated real-world probability."
            ),
            "data_source": "Nessie sandbox account + synthetic-trained model",
            "scenario": scenario,
            "limitations": [
                "The model was trained on synthetic data.",
                "The score is not a calibrated real-world probability.",
                "Pending transactions and scenario assumptions may not "
                "represent final posted activity.",
            ],
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to calculate ML risk assessment: {exc}",
        ) from exc


    
@app.get("/api/briefing")
def briefing():
    try:
        client, account_data = get_account_data()

        forecast_data = project_cashflow(days=7)
        monte_carlo_data = run_monte_carlo()

        deposits = client.get_deposits()
        withdrawals = client.get_withdrawals()

        pending_deposits = [
            {
                "date": item.get("transaction_date"),
                "amount": item.get("amount", 0),
                "description": item.get("description", "Deposit"),
            }
            for item in deposits
            if item.get("status") == "pending"
        ]

        pending_withdrawals = [
            {
                "date": item.get("transaction_date"),
                "amount": item.get("amount", 0),
                "description": item.get("description", "Withdrawal"),
            }
            for item in withdrawals
            if item.get("status") == "pending"
        ]

        financial_data = {
            "account": {
                "nickname": account_data.get("nickname"),
                "balance": account_data.get("balance"),
                "type": account_data.get("type"),
                "environment": "Nessie sandbox",
            },
            "forecast": forecast_data,
            "monte_carlo": monte_carlo_data,
            "pending_deposits": pending_deposits,
            "pending_withdrawals": pending_withdrawals,
            "ml_limitation": (
                "The Random Forest was trained on synthetic scenarios. "
                "Its score is not a calibrated real-world probability."
            ),
        }

        text = generate_financial_briefing(financial_data)

        return {
            "briefing": text,
            "generated_by": "Gemini",
            "data_source": "Nessie sandbox + Cash-flow engine + Monte Carlo",
        }

    except Exception as exc:
        logging.exception("Financial briefing generation failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not generate the financial briefing. "
                "Check the backend terminal for the actual error."
            ),
        ) from exc


class WhatIfRequest(BaseModel):
    payroll_amount: float = Field(ge=0, le=10_000_000)
    deposit_amount: float = Field(ge=0, le=10_000_000)
    deposit_delay_days: int = Field(ge=0, le=7)
    safety_buffer: float = Field(ge=0, le=10_000_000)


@app.post("/api/what-if")
def what_if(request: WhatIfRequest):
    try:
        _, account_data = get_account_data()
        starting_balance = float(account_data.get("balance", 0))

        monte_carlo, forecast_data, projected_ending_balance = (
            run_what_if_simulation(
                starting_balance=starting_balance,
                payroll_amount=request.payroll_amount,
                deposit_amount=request.deposit_amount,
                deposit_delay_days=request.deposit_delay_days,
                safety_buffer=request.safety_buffer,
            )
        )

        scenario = {
            "payroll_amount": request.payroll_amount,
            "deposit_amount": request.deposit_amount,
            "deposit_delay_days": request.deposit_delay_days,
            "safety_buffer": request.safety_buffer,
        }

        financial_data = {
            "account": {
                "nickname": account_data.get("nickname"),
                "starting_balance": starting_balance,
                "environment": "Nessie sandbox",
            },
            "what_if_scenario": scenario,
            "projected_ending_balance": projected_ending_balance,
            "forecast": forecast_data,
            "monte_carlo": monte_carlo,
            "limitations": (
                "This is a prototype using Nessie sandbox data. "
                "The simulation uses a 70% deposit-clearance probability, "
                "up to 3 additional days of deposit delay, and up to "
                "15% payroll outflow uplift. Results are not calibrated "
                "real-world probabilities or guarantees."
            ),
        }

        # Gemini explains the results; Python calculates the metrics.
        try:
            briefing_text = generate_financial_briefing(financial_data)
        except Exception:
            briefing_text = (
                "## Scenario summary\n\n"
                f"The projected ending balance is "
                f"${projected_ending_balance:,.2f}.\n\n"
                f"The simulated safety-buffer breach rate is "
                f"{monte_carlo['safety_buffer_breach_probability']:.1%}. "
                f"The simulated actual-shortfall rate is "
                f"{monte_carlo['shortfall_probability']:.1%}.\n\n"
                "## Limitations\n\n"
                "Gemini was unavailable for this request. "
                "Simulation results depend on the assumptions provided."
            )

        return {
            "scenario": scenario,
            "projected_ending_balance": projected_ending_balance,
            "forecast": forecast_data,
            "monte_carlo": monte_carlo,
            "briefing": briefing_text,
            "data_source": (
                "Nessie sandbox + Monte Carlo simulation + "
                "Gemini when available"
            ),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to run what-if simulation: {exc}",
        ) from exc
