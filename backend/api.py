
from datetime import date, timedelta
from pathlib import Path
import logging
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.data.nessie_client import NessieClient
from backend.data.ledger import build_ledger
from backend.quant.cashflow import project_cashflow 
from backend.quant.monte_carlo import run_monte_carlo
from backend.quant.risk_attribution import run_risk_attribution
from backend.quant.simulation_engine import SimulationEvent
from backend.quant.stress_testing import run_stress_tests
from backend.services.gemini_briefing import generate_financial_briefing
from backend.services.what_if import run_what_if_simulation


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "ml" / "risk_model.joblib"

HORIZON_DAYS = 7
DEFAULT_SIMULATIONS = 2_000
SAFETY_BUFFER = 5_000.0
RANDOM_SEED = 42
DEPOSIT_CLEAR_PROBABILITY = 0.70
MAX_DEPOSIT_DELAY_DAYS = 3
MAX_OUTFLOW_UPLIFT = 0.15


app = FastAPI(
    title="Nesshield AI API",
    description=(
        "Predictive cash-flow forecasting, Monte Carlo simulations, "
        "stress testing, transaction-level risk attribution, and "
        "ML-based scenario risk assessment."
    ),
    version="0.3.0",
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


def get_pending_simulation_context():
    """Build the same seven-day pending-event view for risk endpoints."""
    client, account = get_account_data()
    deposits = client.get_deposits()
    withdrawals = client.get_withdrawals()

    today = date.today()
    end_date = today + timedelta(days=HORIZON_DAYS)

    ledger = build_ledger(
        deposits=deposits,
        withdrawals=withdrawals,
        today=today,
    )

    events = []

    for item in ledger:
        if item.status != "pending":
            continue

        if item.effective_date > end_date:
            continue

        events.append(
            SimulationEvent(
                day=max(0, (item.effective_date - today).days),
                kind=item.kind,
                amount=float(item.amount),
                event_id=item.event_id,
            )
        )

    return account, events


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
        results = project_cashflow(days=HORIZON_DAYS)
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


@app.get("/api/stress-test")
def stress_test(
    simulations: int = Query(
        default=DEFAULT_SIMULATIONS,
        ge=100,
        le=10_000,
    ),
    shock_correlation: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
    ),
):
    """Run predefined adverse scenarios against pending Nessie transactions."""
    try:
        account_data, events = get_pending_simulation_context()

        results = run_stress_tests(
            starting_balance=float(account_data["balance"]),
            events=events,
            horizon_days=HORIZON_DAYS,
            simulations=simulations,
            safety_buffer=SAFETY_BUFFER,
            seed=RANDOM_SEED,
            inflow_clear_probability=DEPOSIT_CLEAR_PROBABILITY,
            max_inflow_delay_days=MAX_DEPOSIT_DELAY_DAYS,
            max_outflow_uplift=MAX_OUTFLOW_UPLIFT,
        )

        return {
            "stress_tests": results,
            "data_source": "Nessie sandbox + stress-testing engine",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Stress testing failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to run stress tests. Check backend logs.",
        ) from exc


@app.get("/api/risk-attribution")
def risk_attribution(
    simulations: int = Query(
        default=DEFAULT_SIMULATIONS,
        ge=100,
        le=10_000,
    ),
    shock_correlation: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
    ),
):
    """Rank pending transactions by their modeled contribution to liquidity risk."""
    try:
        account_data, events = get_pending_simulation_context()

        results = run_risk_attribution(
            starting_balance=float(account_data["balance"]),
            events=events,
            horizon_days=HORIZON_DAYS,
            simulations=simulations,
            safety_buffer=SAFETY_BUFFER,
            seed=RANDOM_SEED,
            inflow_clear_probability=DEPOSIT_CLEAR_PROBABILITY,
            max_inflow_delay_days=MAX_DEPOSIT_DELAY_DAYS,
            max_outflow_uplift=MAX_OUTFLOW_UPLIFT,
            shock_correlation=shock_correlation,
        )

        return {
            "risk_attribution": results,
            "data_source": "Nessie sandbox + counterfactual risk attribution",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Risk attribution failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate risk attribution. Check backend logs.",
        ) from exc


@app.get("/api/payment-timing")
def payment_timing():
    """Report whether verified payment-timing history is available."""
    try:
        client = get_client()
        deposits = client.get_deposits()
        withdrawals = client.get_withdrawals()

        # Nessie currently provides scheduled transaction dates,
        # not verified actual settlement dates. Do not use the
        # ledger's calculated effective_date as an actual outcome.
        transactions = deposits + withdrawals

        return {
            "model": "Historical median baseline",
            "status": "unavailable",
            "estimated_delay_days": None,
            "observations": 0,
            "reason": (
                "Nessie transaction records do not currently expose "
                "verified actual settlement dates."
            ),
            "transactions_inspected": len(transactions),
            "data_source": "Nessie sandbox",
            "limitations": [
                "No payment-timing prediction is being made.",
                "The existing shortfall model is unchanged.",
                "Verified settlement outcomes are required "
                "before estimating historical payment delays."
            ],
        }

    except Exception as exc:
        logging.exception("Payment-timing data inspection failed")
        raise HTTPException(
            status_code=502,
            detail="Unable to inspect payment-timing data.",
        ) from exc




@app.get("/api/ml-risk")
def ml_risk():
    """
    Score a scenario using the existing Random Forest model.

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
            item for item in deposits
            if item.get("status") == "pending"
        ]
        pending_withdrawals = [
            item for item in withdrawals
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
            "data_source": (
                "Nessie sandbox account + synthetic-trained model"
            ),
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

        forecast_data = project_cashflow(days=HORIZON_DAYS)
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
            "data_source": (
                "Nessie sandbox + Cash-flow engine + Monte Carlo"
            ),
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