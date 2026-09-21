"""Request models. Pydantic validates at runtime AND gives us typed objects."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text500 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
# Naira: > 0, capped, at most 2 decimals (so kobo conversion is exact).
Naira = Annotated[Decimal, Field(gt=0, le=1_000_000_000, max_digits=12, decimal_places=2)]

ExpenseCategory = Literal["rent", "transport", "supplies", "utilities", "salaries", "other"]


class CreateCustomer(BaseModel):
    name: Name
    email: EmailStr
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None = None

    @field_validator("email", mode="after")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class LineItem(BaseModel):
    description: Text500
    quantity: Annotated[int, Field(gt=0, le=1_000_000)]
    unit_price: Naira


class CreateInvoice(BaseModel):
    customer_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    due_date: date  # "YYYY-MM-DD"
    line_items: Annotated[list[LineItem], Field(min_length=1, max_length=100)]


class CreateExpense(BaseModel):
    category: ExpenseCategory  # fixed enum, chosen by the user - the AI never guesses
    amount: Naira
    expense_date: date | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
