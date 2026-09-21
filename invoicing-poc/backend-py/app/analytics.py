"""Builds the data blocks handed to the dashboard and to the LLM. ALL arithmetic that matters
lives in SQL (report_summary, customer_period_stats); this module only assembles and compares."""
from datetime import datetime, timezone

from app.ai import pct_change
from app.config import settings
from app.db import supabase
from app.period import Period, current_period, previous_period


def build_summary(business_id: str, period: Period) -> dict:
    """Thin wrapper around the report_summary SQL function + the window metadata, so consumers
    (dashboard, LLM prompts) know exactly what the numbers cover."""
    data = supabase.rpc("report_summary", {
        "p_business_id": business_id,
        "p_from": period.start.isoformat(),
        "p_to": period.end.isoformat(),
    }).execute().data
    return {"range": period.range, "timezone": period.timezone, "currency": "NGN", **data}


def ai_context(business_id: str) -> dict:
    """Day 7: everything the Q&A agent may use - this week and this month, each with its like-for-like previous period."""
    ctx: dict = {"as_of": datetime.now(timezone.utc).astimezone(settings.tz).isoformat(timespec="minutes"),
                 "timezone": settings.timezone, "currency": "NGN"}
    for rng in ("week", "month"):
        ctx[rng] = {"current": build_summary(business_id, current_period(rng)),
                    "previous": build_summary(business_id, previous_period(rng))}
    return ctx


def _customer_stats(business_id: str, period: Period) -> list[dict]:
    return supabase.rpc("customer_period_stats", {
        "p_business_id": business_id, "p_from": period.start.isoformat(), "p_to": period.end.isoformat(),
    }).execute().data


def insight_payload(business_id: str, rng: str) -> dict:
    """Day 8: this period vs the previous one, with the percentage changes PRECOMPUTED here so the
    model quotes them instead of doing its own maths."""
    cur_p, prev_p = current_period(rng), previous_period(rng)
    cur, prev = build_summary(business_id, cur_p), build_summary(business_id, prev_p)
    cur_c, prev_c = _customer_stats(business_id, cur_p), _customer_stats(business_id, prev_p)

    changes = {k: {"current": cur.get(k), "previous": prev.get(k), "pct_change": pct_change(cur.get(k), prev.get(k))}
               for k in ("revenue", "expenses", "net_cash", "average_invoice_value", "invoices_issued", "invoices_paid")}

    prev_by_id = {c["customer_id"]: c for c in prev_c}
    customer_changes = []
    for c in cur_c:
        p = prev_by_id.get(c["customer_id"])
        if not p:
            continue  # only customers with payments in BOTH windows can be compared
        customer_changes.append({
            "customer_name": c["customer_name"],
            "revenue": c["revenue"], "previous_revenue": p["revenue"],
            "avg_days_to_payment": c["avg_days_to_payment"], "previous_avg_days_to_payment": p["avg_days_to_payment"],
            "days_change": round(float(c["avg_days_to_payment"]) - float(p["avg_days_to_payment"]), 1),
        })

    return {
        "as_of": datetime.now(timezone.utc).astimezone(settings.tz).isoformat(timespec="minutes"),
        "range": rng, "timezone": settings.timezone, "currency": "NGN",
        "current": cur, "previous": prev,
        "changes": changes,
        "customers_this_period": cur_c, "customers_previous_period": prev_c,
        "customer_changes": customer_changes,
        "previous_period_has_data": bool(prev["revenue"] or prev["expenses"] or prev["invoices_issued"]),
    }
