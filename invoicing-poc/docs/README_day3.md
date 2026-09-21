# Day 3 - Webhook + automatic payment confirmation

**Goal:** pay the sandbox link -> invoice flips to `paid` with zero manual steps.

## The flow

```
customer pays on Paystack
  -> Paystack POST /webhooks/paystack   (header x-paystack-signature)
       1. read the RAW body bytes
       2. HMAC-SHA512(body, PAYSTACK_SECRET_KEY) must equal the header, else 401
       3. only `charge.success` (currency NGN) is acted on; other events get 200 + ignored
       4. rpc record_payment(reference, amount_in_naira)      (SQL, atomic)
            - lock the invoice row
            - INSERT transaction ... ON CONFLICT (provider_reference) DO NOTHING
            - if nothing inserted -> "duplicate", stop
            - amount_paid += amount; status = 'paid' if fully covered
```

## Decisions and why

- **Raw body, not parsed JSON.** The signature is over the exact bytes Paystack sent. Parsing then re-stringifying changes whitespace/key order and breaks it. So in FastAPI we read `await request.body()` - the untouched bytes - instead of declaring a JSON body model. (Test `test_signature_covers_raw_bytes_whitespace_matters` proves this.)
- **Paystack signs with your *secret key*.** There is no separate "webhook secret" for Paystack - the roadmap's wording assumes one; the code uses `PAYSTACK_SECRET_KEY`. Code: `app/routers/webhooks.py`.
- **`hmac.compare_digest`** rather than `==`, so response timing can't leak how much of a forged signature was correct.
- **Payment recording lives in ONE SQL function** (`record_payment`) instead of JS "check, insert, update" steps. In JS, two webhook deliveries arriving together can both pass the "does it exist?" check and both insert. In SQL, the row lock plus the UNIQUE constraint make that impossible. This is the idempotency the roadmap asks for, done at the only level where it is truly safe.
- **Status codes are deliberate:**
  - bad signature -> 401 (Paystack should not retry a forgery)
  - duplicate / unknown reference / ignored event -> **200** (retrying changes nothing; a non-2xx would cause a retry storm)
  - database failure -> **500** (the *only* case where we want Paystack to retry)
- **Partial payments are handled:** `amount_paid` accumulates; status becomes `paid` only when it covers the total. A `void` invoice that gets paid stays `void` but the money is still recorded in `transaction` so a human can refund it.
- **"Check payment" button** (`POST /invoices/{id}/verify`). Paystack cannot reach `localhost`. This calls Paystack's verify API and records the payment through the *same* `record_payment`, so it is a safe stand-in when you have no ngrok, and harmless if the webhook also arrives.

## Testing it

1. `ngrok http 4000` then set the Paystack dashboard test webhook URL to `https://<id>.ngrok-free.app/webhooks/paystack`. Or use "Check payment" without ngrok.
2. Pay a sandbox invoice; watch the backend log line `Webhook <ref>: recorded`; press Refresh - status is `paid`.
3. Replay the same event from the Paystack dashboard: log shows `duplicate`, `amount_paid` unchanged.
4. Automated: `cd backend-py && pytest` (signature, kobo conversion, duplicate, DB-failure cases, auth required).

## Later note
Because the payment path is one SQL function, nothing added later (customer reminders, reports, AI) changes how money is recorded. Reports read `transaction` rows, so the cash-basis revenue in Day 6 is exactly what this webhook wrote.
