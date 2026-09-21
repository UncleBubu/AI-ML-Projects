import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import supabase
from app.money import kobo_to_naira

log = logging.getLogger(__name__)
router = APIRouter()


def is_valid_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """Paystack signs the RAW body with HMAC-SHA512 using your SECRET KEY (there is no
    separate webhook secret) and sends the hex digest in x-paystack-signature."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    # compare_digest: constant-time, so timing can't leak how much of a forgery matched
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/paystack")
async def paystack_webhook(request: Request):
    # request.body() gives the untouched bytes - exactly what was signed. (Parsing then
    # re-serialising JSON would change whitespace and invalidate every signature.)
    raw = await request.body()

    if not is_valid_signature(raw, request.headers.get("x-paystack-signature"), settings.paystack_secret_key):
        log.warning("Rejected Paystack webhook: bad signature")
        return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        event = json.loads(raw)
    except ValueError:
        return JSONResponse({"error": "Malformed JSON"}, status_code=400)

    # Acknowledge events we intentionally ignore with 200 so Paystack doesn't keep retrying them.
    if event.get("event") != "charge.success":
        return {"received": True, "ignored": event.get("event")}

    data = event.get("data") or {}
    reference, amount, currency = data.get("reference"), data.get("amount"), data.get("currency")
    if not isinstance(reference, str) or not isinstance(amount, int):
        return JSONResponse({"error": "charge.success without reference/amount"}, status_code=400)
    if currency != "NGN":
        log.warning("Ignoring non-NGN payment %s (%s)", reference, currency)
        return {"received": True, "ignored": "currency"}

    try:
        # ONE atomic, idempotent SQL function (row lock + UNIQUE(provider_reference)).
        result = supabase.rpc("record_payment", {
            "p_reference": reference, "p_amount": str(kobo_to_naira(amount)), "p_provider": "paystack",
        }).execute().data
    except Exception:
        log.exception("Webhook %s failed to record", reference)
        # 500 => Paystack retries. The ONLY case where we want a retry.
        return JSONResponse({"error": "Failed to record payment"}, status_code=500)

    log.info("Webhook %s: %s", reference, result)
    # 200 for recorded / duplicate / invoice_not_found: retrying can't change those outcomes.
    return {"received": True, **(result or {})}
