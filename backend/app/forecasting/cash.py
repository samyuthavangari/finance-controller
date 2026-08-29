from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.policy import policy
from app.core.ids import new_id
from app.core.money import money
from app.models import CashForecast, Invoice, LedgerEntry, Settlement


def _base_flows(db: Session, as_of: date) -> list[dict]:
    invoices = db.execute(select(Invoice)).scalars().all()
    settlements = db.execute(select(Settlement)).scalars().all()
    ledger = db.execute(select(LedgerEntry)).scalars().all()
    events = []
    for inv in invoices:
        due = inv.due_date or (inv.invoice_date + timedelta(days=30))
        events.append({"date": due, "amount": money(inv.total_amount), "kind": "receivable" if inv.status == "receivable" else "payable"})
        # synthetic invoices are payables (we pay vendors) unless marked
        if inv.status != "receivable":
            events[-1]["kind"] = "payable"
            events[-1]["amount"] = -money(inv.total_amount)
        else:
            events[-1]["amount"] = money(inv.total_amount)
    for st in settlements:
        events.append({"date": st.settlement_date, "amount": -money(st.amount), "kind": "settlement"})
    for le in ledger:
        sign = money(le.amount) if le.direction == "in" else -money(le.amount)
        events.append({"date": le.entry_date, "amount": sign, "kind": "ledger"})
    return [e for e in events if e["date"] >= as_of]


def forecast(
    db: Session,
    run_id: str | None,
    scenario: str = "base",
    delay_receivables_days: int = 0,
    delay_settlement_days: int = 0,
    expense_increase_pct: Decimal = Decimal("0"),
    early_collect: Decimal = Decimal("0"),
    horizon: int = 30,
) -> CashForecast:
    as_of = date.today()
    cash = money(policy.current_cash)
    monthly = money(policy.scheduled_monthly_expenses) * (Decimal("1") + expense_increase_pct / Decimal("100"))
    events = _base_flows(db, as_of)
    adjusted = []
    remaining_early = money(early_collect)
    for e in events:
        d = e["date"]
        amt = e["amount"]
        if e["kind"] == "receivable" and delay_receivables_days:
            d = d + timedelta(days=delay_receivables_days)
        if e["kind"] == "settlement" and delay_settlement_days:
            d = d + timedelta(days=delay_settlement_days)
        if e["kind"] == "receivable" and remaining_early > 0 and amt > 0:
            take = min(remaining_early, amt)
            remaining_early -= take
            adjusted.append({"date": as_of, "amount": take, "kind": "early_collect"})
            amt = amt - take
        adjusted.append({"date": d, "amount": amt, "kind": e["kind"]})

    series = []
    min_bal = cash
    min_date = as_of.isoformat()
    running = cash
    for i in range(horizon + 1):
        day = as_of + timedelta(days=i)
        day_delta = sum((x["amount"] for x in adjusted if x["date"] == day), Decimal("0"))
        if day.day == 1 or i == 0:
            day_delta -= monthly / Decimal("30")
        else:
            day_delta -= monthly / Decimal("30")
        running = money(running + day_delta)
        series.append({"date": day.isoformat(), "cash": f"{running:.2f}"})
        if running < min_bal:
            min_bal = running
            min_date = day.isoformat()

    def at_day(n: int) -> str:
        if n >= len(series):
            return series[-1]["cash"]
        return series[n]["cash"]

    summary = {
        "current_cash": f"{cash:.2f}",
        "forecast_7d": at_day(7),
        "forecast_14d": at_day(14),
        "forecast_30d": at_day(min(30, horizon)),
        "minimum_expected_balance": f"{min_bal:.2f}",
        "minimum_cash_date": min_date,
        "currency": policy.currency,
        "scenario": scenario,
    }
    row = CashForecast(
        id=new_id("CASH"),
        run_id=run_id,
        scenario=scenario,
        current_cash=cash,
        horizon_days=horizon,
        series=series,
        summary=summary,
    )
    db.add(row)
    db.flush()
    return row
