import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.db import supabase

log = logging.getLogger(__name__)

# Record of the last run, exposed via GET /jobs/status so you can SEE the scheduler is alive
# (free hosts can silently put it to sleep).
last_run: dict | None = None


# A real bot token looks like 123456789:AAH... (digits, colon, 30+ url-safe chars).
_TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")


def telegram_configured() -> bool:
    token = settings.telegram_bot_token.strip()
    if token and not _TOKEN_RE.match(token):
        # Catch copy-paste slips (e.g. pasting the label "HTTP API:" instead of the token)
        log.warning("TELEGRAM_BOT_TOKEN does not look like a bot token (expected 123456789:AAH...); "
                    "falling back to log-only. Check backend-py/.env")
        return False
    return bool(token and settings.telegram_chat_id.strip())


def _send_telegram(text: str) -> None:
    try:
        r = httpx.post(f"https://api.telegram.org/bot{settings.telegram_bot_token.strip()}/sendMessage",
                       json={"chat_id": settings.telegram_chat_id.strip(), "text": text}, timeout=10)
    except httpx.HTTPError:
        # Deliberately don't echo the exception: httpx errors contain the URL, which contains the token.
        raise RuntimeError("Could not reach Telegram (network error)") from None
    if r.status_code >= 400:
        try:
            reason = r.json().get("description", "")
        except ValueError:
            reason = ""
        # e.g. "chat not found" => you haven't pressed Start / messaged the bot yet, or wrong chat id
        raise RuntimeError(f"Telegram rejected the message (HTTP {r.status_code}): {reason}")


def run_overdue_job(business_id: str | None = None) -> dict:
    """The whole Day 4 cycle. business_id scopes it to one business (manual button);
    None = all businesses (the daily cron)."""
    global last_run
    delivered = "telegram" if telegram_configured() else "log-only"
    result = {"ranAt": datetime.now(timezone.utc).isoformat(), "markedOverdue": 0, "alerted": 0, "delivered": delivered}
    try:
        # 1) sent -> overdue in ONE SQL statement
        result["markedOverdue"] = supabase.rpc("mark_overdue_invoices", {"p_business_id": business_id}).execute().data

        # 2) overdue invoices not alerted recently (or ever)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=settings.reminder_interval_hours)).isoformat()
        q = (supabase.table("invoice").select("id, invoice_number, due_date, total_amount, amount_paid, customer(name)")
             .eq("status", "overdue").or_(f"reminder_sent_at.is.null,reminder_sent_at.lt.{cutoff}").order("due_date"))
        if business_id:
            q = q.eq("business_id", business_id)
        due = q.execute().data
        if due:
            # 3) ONE digest message instead of N pings
            lines = []
            for inv in due:
                owed = float(inv["total_amount"]) - float(inv["amount_paid"])
                days = max(1, (datetime.now(timezone.utc) - datetime.fromisoformat(inv["due_date"])).days)
                who = (inv.get("customer") or {}).get("name", "customer")
                lines.append(f"- {inv['invoice_number']} - {who} - NGN {owed:,.2f} - {days}d overdue")
            text = f"Overdue invoices ({len(due)}):\n" + "\n".join(lines)
            if delivered == "telegram":
                _send_telegram(text)
            else:
                log.info("[reminders] %s", text)

            # 4) stamp only AFTER a successful send, so a failed send is retried next run
            supabase.table("invoice").update({"reminder_sent_at": datetime.now(timezone.utc).isoformat()}) \
                .in_("id", [d["id"] for d in due]).execute()
            result["alerted"] = len(due)
    except Exception as err:  # log, never crash: a job failure must not take the API down
        log.exception("[reminders] job failed")
        result["error"] = str(err)
    last_run = result
    return result
