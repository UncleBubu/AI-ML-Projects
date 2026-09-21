# Day 9 - Hardening & polish

**Goal:** survive being used slightly wrong; make it feel like one product.

## 1. Misuse handling (roadmap task 1) - what happens now
| Misuse | Behaviour | Test |
|---|---|---|
| Forged / missing webhook signature | 401, nothing recorded | `test_wrong_signature_rejected` |
| Malformed webhook JSON | 400 | `test_malformed_json_with_valid_signature_is_400` |
| Same webhook delivered twice | 200, no double payment | SQL scenario + `test_duplicate_delivery_still_200` |
| Invoice with missing/invalid fields (1.5 qty, 3 decimals, no items) | 400 `{"error": "line_items.0.quantity: ..."}` | `test_validation_errors_use_the_error_key...` |
| Any API call without a token | 401 | `test_api_routes_require_a_token` |
| Scheduler/job failure | logged, recorded in `GET /jobs/status`, API keeps running | `run_overdue_job` try/except |
| Telegram/SMTP/SMS/LLM/Paystack down | friendly error, no secret leaked | provider tests |
| Spamming the AI or a customer | rate limit (429) / cooldown (429) | tests |

## 2. RLS isolation (roadmap task 2) - and two real holes it found
`supabase/tests/rls_isolation.sql` creates two users/businesses, then acts as user A exactly like the browser (anon key + A's login) and asserts A can see only A's rows, cannot read B's by id, and cannot write. It rolls back, leaving no data. **Run it in the Supabase SQL editor after `supabase db push`; you want only PASS lines.**

Writing the test exposed problems in the Day 1 schema, fixed in `..._day9_rls_hardening.sql`:
1. **`profiles` had no RLS** - anyone with your public anon key could list every user's email. Now own-row only.
2. **Browsers could INSERT invoices/expenses directly** (Day 1 INSERT policies) by calling the REST API with the anon key and choosing their own `total_amount` - bypassing server-computed totals, invoice numbering and Paystack. The client-side INSERT policies are dropped and INSERT/UPDATE/DELETE are revoked: RLS is now **read-only for browsers**; all writes go through the backend.
I verified the test really detects problems: on a database *without* the hardening migration it fails ("A sees only its own profile").

## 3. One coherent dashboard (roadmap task 3)
Top to bottom: overdue banner -> summary panel (week/month) -> **Ask** and **Insights** side by side -> tabs for invoices (form + list with status badges and actions) and expenses. Every money-changing action refreshes the summary; AI panels always read the same SQL-computed numbers as the summary panel, so the three features can't disagree.

## 4. Other decisions
- AI rate limiting and insight caching (cost control).
- No secrets in error messages; one JSON error shape (`{"error": ...}`) the UI can always display.
- `DISABLE_SCHEDULER`, `misfire_grace_time` and the boot catch-up keep reminders reliable on sleepy free hosting.

## Known limits (deliberately left for after the PoC)
- Rate limiter and insight cache are in-memory (single server process). Use Redis if you run several.
- One business per user; no roles.
- The seller digest goes to one Telegram chat for all businesses (fine for single-business scope).
