# Day 5 - Expense logging

**Goal:** record money going out in under 10 seconds; it shows up immediately.

## Pieces
- `POST /expenses`, `GET /expenses` - `app/routers/expenses.py`
- `components/ExpenseSection.tsx` - form + list + running total

## Decisions and why

- **Fixed category enum, chosen by the user.** Enforced three times: the UI dropdown, the pydantic model (`ExpenseCategory` = `Literal[...]` in `app/schemas.py`) and the Postgres `expense_category` enum. The AI never guesses categories - as the roadmap says, that is not where it adds value.
- **Speed:** amount field is auto-focused; after saving, the amount and note clear but **category and date stay**, so logging several expenses in a row is: type amount, Enter.
- **Date defaults to now.** A picked date is stored as *noon in Lagos time*, so it lands safely inside that calendar day for the Day 6 boundaries (midnight would flip to the previous day in UTC).
- **Running total computed with `Decimal`** on the server (`0.1 + 0.2 != 0.3` in floating point) and returned with the list, so the UI never adds money up itself.
- **Business scoping:** `business_id` comes from the authenticated user, never from the client; the service-role client would otherwise let a client write to anyone's business.
- **Limit of 500 rows** on the list keeps the response small; pagination is a later problem for a PoC.
- Expenses are immutable like everything financial: there is no edit/delete endpoint (and since the Day 9 hardening, browsers have no write policy on expenses at all: only this API writes). A wrong entry is fixed with a corrective record later.
