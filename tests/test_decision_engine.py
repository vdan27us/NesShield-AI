from backend.quant.simulation_engine import SimulationEvent
from backend.services.decision_engine import compare_interventions


def test_safe_baseline_recommends_no_action():
    result = compare_interventions(
        starting_balance=100_000,
        events=[SimulationEvent(1, "outflow", 200, "rent")],
        horizon_days=5, simulations=100, safety_buffer=5_000,
    )
    assert result["recommended_action"]["name"] == "No action"
    assert result["recommended_action"]["risk_reduction"] == 0


def test_stressed_case_includes_large_bill_and_credit_line_options():
    result = compare_interventions(
        starting_balance=2_000,
        events=[SimulationEvent(1, "outflow", 8_000, "payroll"),
                SimulationEvent(3, "inflow", 6_000, "receivable")],
        horizon_days=7, simulations=200, safety_buffer=5_000,
    )
    names = [row["name"] for row in result["comparisons"]]
    assert any("payroll" in name for name in names)
    assert any("credit line" in name.lower() for name in names)
    assert any("and draw" in name for name in names)
    assert result["common_random_scenarios"] is True


def test_decision_cost_assumptions_are_reported():
    result = compare_interventions(
        starting_balance=10_000,
        events=[SimulationEvent(1, "outflow", 1_000, "bill")],
        horizon_days=4, simulations=100,
    )
    assert result["assumptions"]["costs_are_illustrative"] is True
    assert result["assumptions"]["deferral_fee_rate"] == 0.01
