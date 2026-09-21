from fastapi import APIRouter, Depends, Response

from app.auth import current_business
from app.db import supabase, first
from app.schemas import CreateCustomer

router = APIRouter()


@router.get("/customers")
def list_customers(business_id: str = Depends(current_business)):
    """Powers the 'pick an existing customer' dropdown."""
    return supabase.table("customer").select("id, name, email, phone").eq("business_id", business_id).order("name").execute().data


@router.post("/customers")
def create_customer(body: CreateCustomer, response: Response, business_id: str = Depends(current_business)):
    """Find-or-create by email (case-insensitive) so repeat invoices reuse the customer."""
    existing = first(supabase.table("customer").select("*").eq("business_id", business_id).ilike("email", body.email).limit(1).execute())
    if existing:
        return existing  # 200
    created = supabase.table("customer").insert(
        {"business_id": business_id, "name": body.name, "email": body.email, "phone": body.phone}
    ).execute().data[0]
    response.status_code = 201
    return created
