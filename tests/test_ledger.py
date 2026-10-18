
from datetime import date

import pytest

from backend.data.ledger import build_ledger, normalize_event


TODAY = date(2026, 10, 18)


def test_overdue_pending_deposit_is_not_dropped():
    event = normalize_event(
        {
            "_id": "deposit-1",
            "amount": 3000,
            "transaction_date": "2026-10-17",
            "status": "pending",
        },
        "inflow",
        today=TODAY,
    )

    assert event.amount == 3000
    assert event.scheduled_date == date(2026, 10, 17)
    assert event.effective_date == TODAY
    assert event.is_overdue is True


def test_future_pending_withdrawal_keeps_its_date():
    event = normalize_event(
        {
            "_id": "payroll-1",
            "amount": 7000,
            "transaction_date": "2026-10-20",
            "status": "pending",
        },
        "outflow",
        today=TODAY,
    )

    assert event.effective_date == date(2026, 10, 20)
    assert event.is_overdue is False


def test_hypothetical_event_is_explicit():
    events = build_ledger(
        deposits=[],
        withdrawals=[],
        today=TODAY,
        hypothetical_events=[
            {
                "id": "scenario-deposit",
                "kind": "inflow",
                "amount": 500,
                "transaction_date": "2026-10-19",
                "status": "hypothetical",
            }
        ],
    )

    assert len(events) == 1
    assert events[0].status == "hypothetical"
    assert events[0].source == "hypothetical"


def test_invalid_amount_is_rejected():
    with pytest.raises(ValueError):
        normalize_event(
            {
                "amount": -100,
                "transaction_date": "2026-10-20",
                "status": "pending",
            },
            "outflow",
            today=TODAY,
        )


def test_duplicate_event_ids_are_rejected():
    transaction = {
        "_id": "duplicate-1",
        "amount": 100,
        "transaction_date": "2026-10-20",
        "status": "pending",
    }

    with pytest.raises(ValueError, match="Duplicate ledger event ID"):
        build_ledger(
            deposits=[transaction],
            withdrawals=[transaction],
            today=TODAY,
        )
