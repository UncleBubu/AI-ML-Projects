"""Customer-facing reminders: email (any SMTP server) and SMS (Termii).

Design choices:
  * SMTP via the standard library - works with Gmail (app password), Zoho, Mailgun SMTP, etc.
    No vendor lock-in and no extra dependency.
  * Termii for SMS: a Nigerian provider, so local numbers/DND rules are handled properly.
  * Each channel reports "sent" / "failed" / "skipped" - one failing channel never blocks the other.
  * Provider errors are reduced to a short message (never the raw exception: URLs/keys leak).
"""
import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.config import settings

log = logging.getLogger(__name__)


def email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def sms_configured() -> bool:
    return bool(settings.termii_api_key and settings.termii_sender_id)


def normalize_ng_phone(raw: str) -> str:
    """'0801 234 5678' / '+234 801 234 5678' / '2348012345678' -> '2348012345678'. Raises ValueError otherwise."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("0") and len(digits) == 11:
        digits = "234" + digits[1:]
    if digits.startswith("234") and len(digits) == 13:
        return digits
    raise ValueError("not a valid Nigerian mobile number")


def send_email(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError("SMTP login rejected - check SMTP_USER / SMTP_PASSWORD (Gmail needs an app password)") from None
    except (smtplib.SMTPException, OSError) as err:
        raise RuntimeError(f"Email could not be sent ({type(err).__name__})") from None


def send_sms(phone: str, text: str) -> None:
    try:
        resp = httpx.post(f"{settings.termii_base_url}/api/sms/send", timeout=15, json={
            "to": normalize_ng_phone(phone), "from": settings.termii_sender_id, "sms": text,
            "type": "plain", "channel": "generic", "api_key": settings.termii_api_key,
        })
    except httpx.HTTPError:
        raise RuntimeError("SMS provider unreachable (network error)") from None
    if resp.status_code >= 400:
        try:
            reason = resp.json().get("message", "")
        except ValueError:
            reason = ""
        raise RuntimeError(f"SMS provider rejected the message (HTTP {resp.status_code}): {reason}")


def build_reminder(*, business_name: str, customer_name: str, invoice: dict) -> tuple[str, str, str]:
    """Returns (email_subject, email_body, sms_text). Amount owed = total - already paid."""
    owed = float(invoice["total_amount"]) - float(invoice["amount_paid"])
    due = invoice["due_date"][:10]
    link = invoice["checkout_url"]
    overdue = invoice["status"] == "overdue"
    lead = "is now overdue" if overdue else "is due soon"
    subject = f"Payment reminder: invoice {invoice['invoice_number']} from {business_name}"
    body = (
        f"Hello {customer_name},\n\n"
        f"This is a friendly reminder that invoice {invoice['invoice_number']} from {business_name} {lead}.\n\n"
        f"  Amount outstanding: NGN {owed:,.2f}\n"
        f"  Due date: {due}\n\n"
        f"You can pay securely online here:\n{link}\n\n"
        f"If you have already paid, please ignore this message.\n\n"
        f"Thank you,\n{business_name}\n"
    )
    sms = (f"{business_name}: invoice {invoice['invoice_number']} {lead}. "
           f"NGN {owed:,.2f} due {due}. Pay: {link}")
    return subject, body, sms
