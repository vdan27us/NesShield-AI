
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date
from math import isfinite
from typing import Any, Iterable


logger = logging.getLogger(__name__)

VALID_KINDS = {"inflow", "outflow"}

VALID_STATUSES = {
    "confirmed",
    "pending",
    "scheduled",
    "hypothetical",
    "cancelled",
}

STATUS_ALIASES = {
    "posted": "confirmed",
    "cleared": "confirmed",
    "completed": "confirmed",
    "settled": "confirmed",
    "canceled": "cancelled",
    "void": "cancelled",
    "voided": "cancelled",
    "reversed": "cancelled",
}


@dataclass(frozen=True)
class LedgerEvent:
    """A normalized financial event used by forecasts and simulations."""

    event_id: str
    kind: str
    amount: float
    scheduled_date: date
    effective_date: date
    status: str
    is_overdue: bool
    source: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["scheduled_date"] = self.scheduled_date.isoformat()
        result["effective_date"] = self.effective_date.isoformat()
        return result


def _warn(message: str, warnings: list[str] | None) -> None:
    """Log a data-quality warning and optionally collect it."""
    logger.warning(message)

    if warnings is not None:
        warnings.append(message)


def normalize_event(
    record: dict[str, Any],
    kind: str,
    *,
    today: date | None = None,
    source: str = "nessie",
    warnings: list[str] | None = None,
) -> LedgerEvent:
    """Normalize one external transaction into a canonical ledger event."""
    if kind not in VALID_KINDS:
        raise ValueError(f"Unsupported event kind: {kind!r}")

    if not isinstance(record, dict):
        raise ValueError("Transaction must be a dictionary")

    today = today or date.today()

    raw_amount = record.get("amount")

    try:
        amount = float(raw_amount)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid transaction amount: {raw_amount!r}"
        ) from exc

    if not isfinite(amount) or amount < 0:
        raise ValueError(
            f"Amount must be finite and non-negative: {raw_amount!r}"
        )

    raw_date = record.get("transaction_date") or record.get("date")

    if not isinstance(raw_date, str):
        raise ValueError(
            "Transaction is missing a valid transaction_date"
        )

    try:
        scheduled_date = date.fromisoformat(raw_date[:10])
    except ValueError as exc:
        raise ValueError(
            f"Invalid transaction date: {raw_date!r}"
        ) from exc

    external_status = str(
        record.get("status") or "pending"
    ).strip().lower()

    status = STATUS_ALIASES.get(
        external_status, external_status
    )

    if status not in VALID_STATUSES:
        _warn(
            f"Unknown transaction status {external_status!r}; "
            "using conservative 'pending' fallback.",
            warnings,
        )
        status = "pending"

    is_overdue = (
        status == "pending"
        and scheduled_date < today
    )

    effective_date = (
        today if is_overdue else scheduled_date
    )

    raw_id = record.get("_id") or record.get("id")

    event_id = (
        str(raw_id)
        if raw_id is not None
        else (
            f"{source}:{kind}:"
            f"{scheduled_date.isoformat()}:{amount:.2f}"
        )
    )

    return LedgerEvent(
        event_id=event_id,
        kind=kind,
        amount=amount,
        scheduled_date=scheduled_date,
        effective_date=effective_date,
        status=status,
        is_overdue=is_overdue,
        source=source,
    )


def build_ledger(
    deposits: Iterable[dict[str, Any]],
    withdrawals: Iterable[dict[str, Any]],
    *,
    today: date | None = None,
    hypothetical_events: Iterable[dict[str, Any]] = (),
    warnings: list[str] | None = None,
) -> list[LedgerEvent]:
    """Build a normalized ledger while reporting data-quality issues."""
    today = today or date.today()
    events: list[LedgerEvent] = []

    records = [
        (record, "inflow", "nessie_deposit")
        for record in deposits
    ] + [
        (record, "outflow", "nessie_withdrawal")
        for record in withdrawals
    ]

    for record, kind, source in records:
        try:
            event = normalize_event(
                record,
                kind,
                today=today,
                source=source,
                warnings=warnings,
            )
        except (ValueError, TypeError) as exc:
            _warn(
                f"Skipping invalid {source} record: {exc}",
                warnings,
            )
            continue

        events.append(event)

    for record in hypothetical_events:
        try:
            event = normalize_event(
                record,
                str(record.get("kind", "")),
                today=today,
                source="hypothetical",
                warnings=warnings,
            )
        except (ValueError, TypeError) as exc:
            _warn(
                f"Skipping invalid hypothetical record: {exc}",
                warnings,
            )
            continue

        if event.status != "hypothetical":
            _warn(
                f"Skipping hypothetical event {event.event_id!r}: "
                "status must be 'hypothetical'.",
                warnings,
            )
            continue

        events.append(event)

    # Outflows sort before inflows on the same day.
    events.sort(
        key=lambda event: (
            event.effective_date,
            0 if event.kind == "outflow" else 1,
            event.event_id,
        )
    )

    unique_events: list[LedgerEvent] = []
    seen_ids: set[str] = set()

    for event in events:
        if event.event_id in seen_ids:
            _warn(
                f"Skipping duplicate ledger event ID: "
                f"{event.event_id!r}",
                warnings,
            )
            continue

        seen_ids.add(event.event_id)
        unique_events.append(event)

    return unique_events
