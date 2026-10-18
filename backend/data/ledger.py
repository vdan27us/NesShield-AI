
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from math import isfinite
from typing import Any, Iterable


VALID_KINDS = {"inflow", "outflow"}

VALID_STATUSES = {
    "confirmed",
    "pending",
    "scheduled",
    "hypothetical",
}

# External status names mapped to our canonical ledger vocabulary.
STATUS_ALIASES = {
    "posted": "confirmed",
    "cleared": "confirmed",
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


def normalize_event(
    record: dict[str, Any],
    kind: str,
    *,
    today: date | None = None,
    source: str = "nessie",
) -> LedgerEvent:
    """
    Convert an external transaction into a canonical ledger event.

    Overdue pending events remain visible and become effective today.
    Posted and cleared transactions are normalized to confirmed.
    """
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
        raise ValueError(
            f"Unsupported transaction status: {external_status!r}"
        )

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
) -> list[LedgerEvent]:
    """Normalize inflows and outflows into one sorted event ledger."""
    today = today or date.today()
    events: list[LedgerEvent] = []

    for record in deposits:
        events.append(
            normalize_event(
                record,
                "inflow",
                today=today,
                source="nessie_deposit",
            )
        )

    for record in withdrawals:
        events.append(
            normalize_event(
                record,
                "outflow",
                today=today,
                source="nessie_withdrawal",
            )
        )

    for record in hypothetical_events:
        event = normalize_event(
            record,
            str(record.get("kind", "")),
            today=today,
            source="hypothetical",
        )

        if event.status != "hypothetical":
            raise ValueError(
                "Hypothetical events must use "
                "status='hypothetical'"
            )

        events.append(event)

    # Outflows sort before inflows on the same date.
    events.sort(
        key=lambda event: (
            event.effective_date,
            0 if event.kind == "outflow" else 1,
            event.event_id,
        )
    )

    seen_ids: set[str] = set()

    for event in events:
        if event.event_id in seen_ids:
            raise ValueError(
                f"Duplicate ledger event ID: {event.event_id}"
            )

        seen_ids.add(event.event_id)

    return events
