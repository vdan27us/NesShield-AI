"""Deterministic two-year operating history for the dashboard demo profile.

These generated records make the product demo richer; they are not Nessie
transactions and must never be presented as a real company's financial data.
"""

from __future__ import annotations

import calendar
import random
from collections import defaultdict
from datetime import date, timedelta


BUSINESS_NAME = "Northstar Mechanical Services"
MONTHS = 24


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, count: int) -> date:
    month_index = value.year * 12 + value.month - 1 + count
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _bounded_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def generate_business_history(*, today: date | None = None) -> dict:
    """Return 24 months of seeded, seasonally variable small-business activity."""
    today = today or date.today()
    first_month = _add_months(_month_start(today), -(MONTHS - 1))
    rng = random.Random(104729)
    events: list[dict] = []
    month_starts = [_add_months(first_month, offset) for offset in range(MONTHS)]

    payer_names = [
        "Cedar Ridge Property Group", "Harborlight Retail", "Pinecrest Medical",
        "Summit Office Partners", "Blue Oak Hospitality", "Westline Logistics",
        "Meridian Property Care", "Atlas Food Services", "Redwood Community Bank",
        "Lakeside Manufacturing", "Brightpath Schools", "Evergreen Senior Living",
    ]
    # HVAC service demand tends to peak in hot months and soften in winter.
    seasonal_revenue = [0.77, 0.78, 0.91, 0.98, 1.07, 1.19, 1.31, 1.27, 1.08, 0.96, 0.83, 0.81]

    def add_event(when: date, direction: str, amount: float, category: str,
                  description: str, counterparty: str, status: str = "cleared") -> None:
        events.append({
            "transaction_id": f"demo-{len(events) + 1:05d}",
            "date": when.isoformat(),
            "description": description,
            "category": category,
            "direction": direction,
            "amount": round(amount, 2),
            "counterparty": counterparty,
            "status": status,
        })

    for month_number, month_start in enumerate(month_starts):
        year, month = month_start.year, month_start.month
        month_end = _bounded_day(year, month, calendar.monthrange(year, month)[1])
        active_end = min(month_end, today)
        if month_start > today:
            continue
        year_growth = 1 + 0.045 * (month_number / 12)
        demand = seasonal_revenue[month - 1] * year_growth

        # Lumpy customer receipts settle several days after work/invoicing.
        invoice_count = rng.randint(10, 18)
        for invoice_number in range(invoice_count):
            issue_day = rng.randint(1, max(1, calendar.monthrange(year, month)[1] - 8))
            issue_date = _bounded_day(year, month, issue_day)
            payer = payer_names[(invoice_number + month_number * 3 + rng.randrange(len(payer_names))) % len(payer_names)]
            invoice = rng.lognormvariate(8.62, 0.72) * demand / 1.05
            # Payer-specific reliability drifts modestly over time.
            reliability = 0.72 + 0.16 * ((invoice_number % 5) / 4) - 0.025 * (month_number // 8)
            delay = rng.choices([0, 2, 5, 9, 15, 24], [reliability * 0.55, reliability * 0.23, 0.12, 0.07, 0.025, 0.005])[0]
            receipt_date = min(issue_date + timedelta(days=delay), active_end)
            if issue_date <= active_end:
                add_event(receipt_date, "inflow", invoice, "Customer receipts", "Service invoice settlement", payer)

        # Payroll twice monthly, with a small bonus/overtime swing.
        for payroll_day in (5, 20):
            pay_date = _bounded_day(year, month, payroll_day)
            if pay_date <= active_end:
                payroll = rng.normalvariate(22400 * year_growth, 1100)
                add_event(pay_date, "outflow", max(16000, payroll), "Payroll", "Payroll and field labor", "Northstar payroll")

        scheduled_costs = [
            (1, "Facilities", rng.normalvariate(7900, 180), "Shop lease and storage", "Cypress Industrial Properties"),
            (4, "Insurance", rng.normalvariate(2380, 220), "Commercial and fleet insurance", "Frontier Mutual"),
            (10, "Utilities", rng.normalvariate(2240 * (1.25 if month in (6, 7, 8) else 1), 280), "Utilities and fuel", "Regional utilities"),
            (15, "Software", rng.normalvariate(1160, 110), "Dispatch, accounting and SaaS", "Business software vendors"),
            (25, "Debt service", rng.normalvariate(4650, 90), "Vehicle and equipment financing", "Commercial lender"),
        ]
        for day, category, amount, description, counterparty in scheduled_costs:
            expense_date = _bounded_day(year, month, day)
            if expense_date <= active_end:
                add_event(expense_date, "outflow", max(250, amount), category, description, counterparty)

        # Supplier spend is frequent and irregular; repairs create occasional spikes.
        for _ in range(rng.randint(4, 7)):
            order_day = rng.randint(1, calendar.monthrange(year, month)[1])
            order_date = _bounded_day(year, month, order_day)
            if order_date <= active_end:
                amount = rng.lognormvariate(8.45, 0.58) * (0.85 + 0.16 * demand)
                supplier = rng.choice(["Ferguson HVAC Supply", "Carrier Parts", "Grainger", "Metro Electrical", "Fleet Fuel Card"])
                category = "Materials & fleet" if supplier != "Fleet Fuel Card" else "Fleet & fuel"
                add_event(order_date, "outflow", amount, category, "Parts, materials and field supplies", supplier)

        if rng.random() < 0.24:
            repair_day = rng.randint(1, calendar.monthrange(year, month)[1])
            repair_date = _bounded_day(year, month, repair_day)
            if repair_date <= active_end:
                add_event(repair_date, "outflow", rng.uniform(1800, 9800), "Repairs", "Unplanned vehicle or equipment repair", rng.choice(["Fleet service", "Equipment repair vendor"]))

        if month in (3, 6, 9, 12):
            tax_date = _bounded_day(year, month, 15)
            if tax_date <= active_end:
                add_event(tax_date, "outflow", rng.uniform(6500, 14500), "Taxes", "Quarterly estimated tax payment", "State and federal tax reserve")

    events.sort(key=lambda item: (item["date"], 0 if item["direction"] == "outflow" else 1, item["transaction_id"]))
    monthly = []
    by_month: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_month[event["date"][:7]].append(event)

    running_balance = 128_500.0
    for month_start in month_starts:
        month_key = month_start.strftime("%Y-%m")
        rows = by_month.get(month_key, [])
        inflows = sum(item["amount"] for item in rows if item["direction"] == "inflow")
        outflows = sum(item["amount"] for item in rows if item["direction"] == "outflow")
        opening_balance = running_balance
        running_balance += inflows - outflows
        monthly.append({
            "month": month_key,
            "revenue": round(inflows, 2),
            "expenses": round(outflows, 2),
            "net_cash_flow": round(inflows - outflows, 2),
            "opening_cash": round(opening_balance, 2),
            "ending_cash": round(running_balance, 2),
            "transaction_count": len(rows),
        })

    return {
        "business_name": BUSINESS_NAME,
        "period_start": month_starts[0].isoformat(),
        "period_end": today.isoformat(),
        "months": monthly,
        "transactions": events,
        "summary": {
            "transaction_count": len(events),
            "monthly_revenue_average": round(sum(row["revenue"] for row in monthly) / max(1, len(monthly)), 2),
            "monthly_expense_average": round(sum(row["expenses"] for row in monthly) / max(1, len(monthly)), 2),
            "ending_cash": round(running_balance, 2),
            "profitable_months": sum(row["net_cash_flow"] > 0 for row in monthly),
            "negative_months": sum(row["net_cash_flow"] < 0 for row in monthly),
        },
        "data_source": "synthetic_demo_history",
        "disclosure": "Generated, illustrative two-year operating history for a fictional small business; not retrieved from Nessie and not real company records.",
    }
