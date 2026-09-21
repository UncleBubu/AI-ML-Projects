import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.auth import current_business
from app.dates import end_of_day_utc
from app.db import supabase, first
from app.invoice_service import get_owned_invoice, issue_payment_link
from app.money import kobo_to_naira
from app.paystack import verify_transaction
from app.schemas import CreateInvoice

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/invoices")
def list_invoices(business_id: str = Depends(current_business)):
    rows = (supabase.table("invoice").select("*, customer(name, email, phone)").eq("business_id", business_id)
            .order("issue_date", desc=True).limit(200).execute().data)
    # Attach "last reminded" (customer reminders) in one extra query instead of N.
    if rows:
        logs = (supabase.table("reminder_log").select("invoice_id, sent_at").eq("business_id", business_id)
                .eq("status", "sent").order("sent_at", desc=True).limit(1000).execute().data)
        last: dict[str, str] = {}
        for entry in logs:  # newest first, so the first one seen per invoice is the latest
            last.setdefault(entry["invoice_id"], entry["sent_at"])
        for r in rows:
            r["last_customer_reminder_at"] = last.get(r["id"])
    return rows


@router.post("/invoices", status_code=201)
def create_invoice(body: CreateInvoice, business_id: str = Depends(current_business)):
    # Ownership check (we also need the email for Paystack)
    customer = first(supabase.table("customer").select("id, email").eq("id", body.customer_id).eq("business_id", business_id).limit(1).execute())
    if not customer or not customer.get("email"):
        raise HTTPException(404, "Customer not found for this business")

    # Header + line items + invoice number in ONE SQL transaction; totals computed in SQL,
    # never taken from the client. Decimals are sent as strings to stay exact.
    invoice = supabase.rpc("create_invoice", {
        "p_business_id": business_id,
        "p_customer_id": body.customer_id,
        "p_due_date": end_of_day_utc(body.due_date.isoformat()),
        "p_items": [{"description": i.description, "quantity": i.quantity, "unit_price": str(i.unit_price)} for i in body.line_items],
    }).execute().data

    try:
        return issue_payment_link(invoice, customer["email"])
    except Exception:
        # The invoice is safely saved as a draft; only the payment link failed.
        log.exception("Paystack failed for %s", invoice["invoice_number"])
        return JSONResponse(status_code=502, content={
            "error": f"{invoice['invoice_number']} was saved, but the payment link could not be created. Use \"Retry payment link\" on it.",
            "invoice_id": invoice["id"],
        })


@router.post("/invoices/{invoice_id}/payment-link")
def retry_payment_link(invoice_id: str, business_id: str = Depends(current_business)):
    """Only for invoices that never got a link (replacing one could orphan a payment made on the old link)."""
    invoice = get_owned_invoice(business_id, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice["checkout_url"]:
        raise HTTPException(409, "Invoice already has a payment link")
    if invoice["status"] != "draft":
        raise HTTPException(409, f"Cannot create a link for a {invoice['status']} invoice")
    customer = first(supabase.table("customer").select("email").eq("id", invoice["customer_id"]).limit(1).execute())
    if not customer or not customer.get("email"):
        raise HTTPException(422, "Customer has no email")
    try:
        return issue_payment_link(invoice, customer["email"])
    except Exception:
        log.exception("Retry payment link failed")
        raise HTTPException(502, "Could not create payment link")


@router.post("/invoices/{invoice_id}/verify")
def verify_payment(invoice_id: str, business_id: str = Depends(current_business)):
    """Fallback when the webhook can't reach you: ask Paystack directly, then record through the
    SAME idempotent SQL function the webhook uses - so running both is harmless."""
    invoice = get_owned_invoice(business_id, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not invoice["payment_reference"]:
        raise HTTPException(409, "Invoice has no payment reference yet")
    try:
        result = verify_transaction(invoice["payment_reference"])
    except Exception:
        log.exception("Paystack verify failed")
        raise HTTPException(502, "Could not verify payment with Paystack")
    if result["status"] != "success" or result["currency"] != "NGN":
        return {"result": "not_paid", "paystack_status": result["status"]}
    return supabase.rpc("record_payment", {
        "p_reference": invoice["payment_reference"],
        "p_amount": str(kobo_to_naira(result["amount_kobo"])),
        "p_provider": "paystack",
    }).execute().data


@router.post("/invoices/{invoice_id}/void")
def void_invoice(invoice_id: str, business_id: str = Depends(current_business)):
    """A status change, never a delete. Conditional update: only unpaid, non-final invoices."""
    rows = (supabase.table("invoice").update({"status": "void"}).eq("id", invoice_id).eq("business_id", business_id)
            .in_("status", ["draft", "sent", "overdue"]).eq("amount_paid", 0).execute().data)
    if not rows:
        raise HTTPException(409, "Invoice not found, already paid, or already void")
    return rows[0]
