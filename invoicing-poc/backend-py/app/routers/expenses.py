from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends

from app.auth import current_business
from app.dates import noon_utc
from app.db import supabase
from app.schemas import CreateExpense

router = APIRouter()


@router.post("/expenses", status_code=201)
def create_expense(body: CreateExpense, business_id: str = Depends(current_business)):
    return supabase.table("expense").insert({
        "business_id": business_id,
        "category": body.category,
        "amount": str(body.amount),
        # picked date -> noon Lagos time (safely inside that day); default -> now
        "expense_date": noon_utc(body.expense_date.isoformat()) if body.expense_date else datetime.now(timezone.utc).isoformat(),
        "note": body.note,
    }).execute().data[0]


@router.get("/expenses")
def list_expenses(business_id: str = Depends(current_business)):
    rows = (supabase.table("expense").select("id, category, amount, expense_date, note").eq("business_id", business_id)
            .order("expense_date", desc=True).limit(500).execute().data)
    # Decimal sum: no floating-point drift (0.1 + 0.2 != 0.3)
    total = sum((Decimal(str(r["amount"])) for r in rows), Decimal("0"))
    return {"expenses": rows, "total": float(total)}
