# Day 2 - Invoice creation + payment link

> **Stack note:** you code in Python, so the backend is now **FastAPI (Python)** in `backend-py/`. Python is a genuinely good fit here: `Decimal` for exact money, `pydantic` for validation, `zoneinfo` for timezones, `APScheduler` for jobs. The parts that *can't* be Python stay as they are: **SQL** (Postgres functions) and the **React/TSX frontend** (browsers only run JavaScript). The old TypeScript `backend/` folder is superseded and safe to delete: nothing in `backend-py/` or the frontend imports from it. Keep only its `.env` values (copied into `backend-py/.env`).

**Goal:** create an invoice in the UI and get back a real, clickable Paystack sandbox link.

## What happens when you click "Create invoice"

```
InvoiceForm  ->  POST /customers (find-or-create by email)
             ->  POST /invoices
                    1. pydantic validates the body            (app/schemas.py)
                    2. business id comes from the JWT, never from the request
                    3. rpc create_invoice(...)  ONE SQL transaction:
                          invoice number + invoice row + line items, total computed in SQL
                    4. Paystack "initialize transaction"       (app/paystack.py)
                    5. save reference + checkout_url, status draft -> sent
```

## What was broken in the Day 1/2 code (and how it was fixed)

| Problem | Effect | Fix |
|---|---|---|
| (TS backend) `index.ts` imported `./invoices.route` (file is in `routes/`) | server would not start | correct import |
| (TS backend) `invoices.route.ts` imported `../lib/supabaseAdmin` and `./lib/business` (neither exists at that path) | compile errors | use `supabaseClient` / `../lib/...` |
| (TS backend) `/invoices` had no `requireAuth`, then read `req.auth.userId` | crash / unauthenticated access | in Python every route declares `Depends(current_business)`, which itself depends on `require_auth`, so forgetting auth is structurally hard |
| Nothing ever created a `business` row | every request for a new user failed with "No business found" | `business_id_for()` in `app/auth.py` creates it on first use |
| Frontend imported `../lib/supabaseClient` (real path `../supabaseClient`) | Vite build error | fixed |
| `import { LineItemInput }` of a type without `type` under `verbatimModuleSyntax` | build error | `import type` |
| `alert()`-based login feedback | poor UX | inline messages |

## Decisions and why

- **Totals are computed in SQL (`create_invoice`)**, not JS. The roadmap says "never trust a client-sent total"; doing the sum in the database as well means the number stored is the number written by the same transaction that wrote the line items. If any step fails, everything rolls back - no half-made invoices, no burned invoice numbers.
- **`pydantic` validation.** One model gives you runtime validation *and* a typed object. Your old hand-written checks missed things like `quantity: 1.5`, `unit_price: "abc"` or 3-decimal prices. Failures are returned as `{"error": "line_items.0.quantity: ..."}` because the React app reads `body.error`.
- **Due date = end of that day in Lagos.** A bare `2026-10-01` parsed as UTC midnight would make the invoice overdue ~1 day early for a Lagos business (`app/dates.py`, using `zoneinfo`).
- **Kobo/naira in one file** (`app/money.py`) using `Decimal`, never `float`. Paystack wants integer kobo, and `19.99 * 100` is `1998.9999999999998` as a float (a test pins this).
- **If Paystack is down, the invoice is still saved as `draft`** and the API returns 502 with a hint. `POST /invoices/{id}/payment-link` retries. Better than losing the invoice.
- **A payment link is never replaced once it exists.** Replacing the reference could orphan a payment made on the old link.
- **`create_invoice` etc. are locked to `service_role`.** Supabase exposes every `public` function to the anon key by default (`/rest/v1/rpc/...`). These functions take a `business_id` parameter and skip RLS, so leaving them open would let anyone call them. See migration `..._day2_hardening_and_create_invoice.sql`.
- **Indexes + unique constraints** (`business_id + invoice_number`, `payment_reference`, one business per owner) - cheap now, painful to retrofit.
- **`transaction` is append-only, enforced by a trigger**, not just by promise.
- **CORS locked** to `FRONTEND_ORIGIN` instead of `*`.
- **Startup env validation** (`app/config.py`): a missing key fails at boot with its name, not as a mysterious 500 later.

## Run it

```bash
supabase db push                 # applies the new migrations
cd backend-py
python -m venv .venv && .venv\Scripts\activate     # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 4000

cd frontend && npm install && npm run dev
```
Copy `backend-py/.env.example` to `backend-py/.env` and fill it in. The server refuses to start if `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` or `PAYSTACK_SECRET_KEY` is missing. The frontend has its own `frontend/.env` (Supabase URL, anon key, API URL). Test card (Paystack sandbox): `4084 0840 8408 4081`, any future expiry, CVV `408`, OTP `123456`.

## Things to know
- The service-role client bypasses RLS, so **every query must filter by `business_id`** (routes do). That is the price of using it, and why `get_owned_invoice` exists.
- Try it: create an invoice with a decimal price like 1500.50 x 2 and check the Paystack dashboard shows 300100 kobo.

## Changes made after Day 2 (so this README matches the code today)
- **Customer phone** is now an optional field on the invoice form. It is stored on the customer and used by the per-invoice "Remind customer" button (see `README_customer_reminders.md`).
- **Browsers can no longer write invoices directly.** The Day 1 RLS INSERT policies let a logged-in browser insert an invoice with any total, bypassing `create_invoice`. Migration `day9_rls_hardening` removed them: every write goes through this API (details in `README_day9.md`).
- **Extra invoice actions:** "Retry payment link" (if Paystack was down at creation), "Check payment" and "Void", all in `app/routers/invoices.py`.
