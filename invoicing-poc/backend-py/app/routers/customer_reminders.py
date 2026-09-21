import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import notifier
from app.auth import current_business
from app.config import settings
from app.db import supabase, first
from app.invoice_service import get_owned_invoice

log = logging.getLogger(__name__)
router = APIRouter()


class RemindBody(BaseModel):
    channels: list[Literal["email", "sms"]] = ["email", "sms"]


def _log(business_id: str, invoice_id: str, channel: str, recipient: str, status: str, error: str | None = None) -> None:
    supabase.table("reminder_log").insert({
        "business_id": business_id, "invoice_id": invoice_id, "channel": channel,
        "recipient": recipient, "status": status, "error": error,
    }).execute()


@router.post("/invoices/{invoice_id}/remind-customer")
def remind_customer(invoice_id: str, body: RemindBody | None = None, business_id: str = Depends(current_business)):
    """Manual, per-invoice reminder to the CUSTOMER by email and/or SMS.

    Safeguards (customer-facing messages are a different risk from alerts to yourself):
      * manual only - nothing is ever auto-sent to customers
      * only unpaid invoices that already have a payment link
      * one successful reminder per invoice per cooldown window (default 24h)
      * every attempt is written to the append-only reminder_log
    """
    channels = (body or RemindBody()).channels
    invoice = get_owned_invoice(business_id, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice["status"] not in ("sent", "overdue") or float(invoice["amount_paid"]) >= float(invoice["total_amount"]):
        raise HTTPException(409, f"Cannot remind: invoice is {invoice['status']}")
    if not invoice["checkout_url"]:
        raise HTTPException(409, "Invoice has no payment link yet")

    since = (datetime.now(timezone.utc) - timedelta(hours=settings.customer_reminder_cooldown_hours)).isoformat()
    recent = first(supabase.table("reminder_log").select("sent_at").eq("invoice_id", invoice_id)
                   .eq("status", "sent").gte("sent_at", since).order("sent_at", desc=True).limit(1).execute())
    if recent:
        raise HTTPException(429, f"This customer was already reminded about {invoice['invoice_number']} in the last "
                                 f"{settings.customer_reminder_cooldown_hours}h")

    customer = first(supabase.table("customer").select("name, email, phone").eq("id", invoice["customer_id"]).limit(1).execute())
    biz = first(supabase.table("business").select("name").eq("id", business_id).limit(1).execute())
    subject, email_body, sms_text = notifier.build_reminder(
        business_name=(biz or {}).get("name", "Your supplier"), customer_name=customer["name"], invoice=invoice)

    results = []
    for channel in channels:
        recipient = (customer.get("email") if channel == "email" else customer.get("phone")) or ""
        if not recipient:
            results.append({"channel": channel, "status": "skipped", "detail": f"customer has no {channel} on file"})
            continue
        if not (notifier.email_configured() if channel == "email" else notifier.sms_configured()):
            results.append({"channel": channel, "status": "skipped",
                            "detail": "email is not configured (SMTP_* in .env)" if channel == "email"
                            else "SMS is not configured (TERMII_* in .env)"})
            continue
        try:
            if channel == "email":
                notifier.send_email(recipient, subject, email_body)
            else:
                notifier.send_sms(recipient, sms_text)
            _log(business_id, invoice_id, channel, recipient, "sent")
            results.append({"channel": channel, "status": "sent", "to": recipient})
        except Exception as err:  # one failing channel must not block the other
            log.warning("Reminder %s via %s failed: %s", invoice["invoice_number"], channel, err)
            _log(business_id, invoice_id, channel, recipient, "failed", str(err)[:300])
            results.append({"channel": channel, "status": "failed", "detail": str(err)})

    if not any(r["status"] == "sent" for r in results):
        # Nothing went out: 422 so the UI shows WHY (usually: channel not configured / no contact details)
        raise HTTPException(422, "; ".join(f"{r['channel']}: {r.get('detail', r['status'])}" for r in results))
    return {"results": results}
