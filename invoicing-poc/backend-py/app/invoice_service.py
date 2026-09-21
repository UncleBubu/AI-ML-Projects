import uuid

from app.db import supabase, first
from app.paystack import initialize_transaction


def get_owned_invoice(business_id: str, invoice_id: str) -> dict | None:
    """Fetch an invoice ONLY if it belongs to this business. The service-role client
    bypasses RLS, so this filter is what stops user A touching user B's invoice by guessing an id."""
    return first(supabase.table("invoice").select("*").eq("id", invoice_id).eq("business_id", business_id).limit(1).execute())


def issue_payment_link(invoice: dict, customer_email: str) -> dict:
    """Create the Paystack checkout and store reference + URL. Used right after creation
    and as the retry path if Paystack was down then."""
    reference = f"{invoice['invoice_number']}-{uuid.uuid4().hex[:8]}"  # unique per attempt
    url = initialize_transaction(
        email=customer_email, amount_naira=invoice["total_amount"], reference=reference,
        metadata={"invoice_id": invoice["id"], "invoice_number": invoice["invoice_number"]},
    )
    update = {"payment_reference": reference, "checkout_url": url}
    if invoice["status"] == "draft":
        update["status"] = "sent"
    return supabase.table("invoice").update(update).eq("id", invoice["id"]).execute().data[0]
