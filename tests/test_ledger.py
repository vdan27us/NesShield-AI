
from datetime import date

import pytest

from backend.data.ledger import build_ledger, normalize_event


TODAY = date(2026, 10, 18)


def test_overdue_pending_deposit_is_not_dropped():
    warnings = []

    ledger = build_ledger(
        deposits=[
            {
                "_id": "old-deposit",
                "amount": 500,
                "transaction_date": "2026-10-17",
                "status": "pending",
            }
        ],
        withdrawals=[],
        today=TODAY,
        warnings=warnings,
    )

    assert len(ledger) == 1
    assert ledger[0].is_overdue is True
    assert ledger[0].scheduled_date == date(2026, 10, 17)
    assert ledger[0].effective_date == TODAY


def test_future_pending_withdrawal_keeps_its_date():
    ledger = build_ledger(
        deposits=[],
        withdrawals=[
            {
                "_id": "future-withdrawal",
                "amount": 700,
                "transaction_date": "2026-10-20",
                "status": "pending",
            }
        ],
        today=TODAY,
    )

    assert len(ledger) == 1
    assert ledger[0].kind == "outflow"
    assert ledger[0].effective_date == date(2026, 10, 20)


def test_hypothetical_event_is_explicit():
    ledger = build_ledger(
        deposits=[],
        withdrawals=[],
        today=TODAY,
        hypothetical_events=[
            {
                "_id": "what-if-deposit",
                "kind": "inflow",
                "amount": 250,
                "transaction_date": "2026-10-19",
                "status": "hypothetical",
            }
        ],
    )

    assert len(ledger) == 1
    assert ledger[0].status == "hypothetical"
    assert ledger[0].source == "hypothetical"


def test_invalid_amount_is_rejected_by_normalizer():
    with pytest.raises(ValueError):
        normalize_event(
            {
                "_id": "bad-amount",
                "amount": -100,
                "transaction_date": "2026-10-19",
                "status": "pending",
            },
            "outflow",
            today=TODAY,
        )


def test_duplicate_event_ids_are_deduplicated_with_warning():
    warnings = []

    ledger = build_ledger(
        deposits=[
            {
                "_id": "duplicate-id",
                "amount": 500,
                "transaction_date": "2026-10-19",
                "status": "pending",
            },
            {
                "_id": "duplicate-id",
                "amount": 900,
                "transaction_date": "2026-10-20",
                "status": "pending",
            },
        ],
        withdrawals=[],
        today=TODAY,
        warnings=warnings,
    )

    assert len(ledger) == 1
    assert ledger[0].amount == 500
    assert any("duplicate" in warning.lower() for warning in warnings)


def test_unknown_status_uses_pending_fallback_with_warning():
    warnings = []

    ledger = build_ledger(
        deposits=[
            {
                "_id": "unknown-status",
                "amount": 100,
                "transaction_date": "2026-10-19",
                "status": "awaiting_review",
            }
        ],
        withdrawals=[],
        today=TODAY,
        warnings=warnings,
    )

    assert len(ledger) == 1
    assert ledger[0].status == "pending"
    assert warnings


def test_posted_status_normalizes_to_confirmed():
    ledger = build_ledger(
        deposits=[
            {
                "_id": "posted-deposit",
                "amount": 100,
                "transaction_date": "2026-10-18",
                "status": "posted",
            }
        ],
        withdrawals=[],
        today=TODAY,
    )

    assert len(ledger) == 1
    assert ledger[0].status == "confirmed"


def test_invalid_external_record_is_skipped_with_warning():
    warnings = []

    ledger = build_ledger(
        deposits=[
            {
                "_id": "bad-record",
                "amount": "not-a-number",
                "transaction_date": "2026-10-19",
                "status": "pending",
            }
        ],
        withdrawals=[],
        today=TODAY,
        warnings=warnings,
    )

    assert ledger == []
    assert len(warnings) == 1
