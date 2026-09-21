# Customer reminders (email + SMS, per invoice)

**What you asked for:** a "Remind customer" button beside each unpaid invoice that emails / texts the customer.

## How it works
`Remind customer` (InvoiceList) -> confirm dialog showing exactly who will be contacted -> `POST /invoices/{id}/remind-customer` -> for each channel: email via SMTP, SMS via Termii -> one row per attempt in `reminder_log`.

The message states the amount still owed (total minus payments), the due date and **the Paystack payment link** - so the customer can pay in one tap.

## Decisions and why
- **Manual only, never automatic.** Earlier the roadmap warned against auto-messaging customers (wrong number/email = embarrassing or a privacy problem). A person pressing a button, after a confirm dialog naming the recipient, keeps you in control. The daily cron still only alerts *you*.
- **Cooldown: one successful reminder per invoice per 24h** (`CUSTOMER_REMINDER_COOLDOWN_HOURS`). A double-click or an enthusiastic afternoon can't spam a customer.
- **Audit log (`reminder_log`, append-only, RLS read-only).** Powers the cooldown and the "Reminded 19 Sep" label, and answers "did we actually contact them?".
- **Only `sent`/`overdue` invoices with a payment link.** Paid, void and draft invoices are refused (409) - no reminding someone who already paid.
- **Channels fail independently.** If SMTP is misconfigured but SMS works, the SMS still goes; the response says which channel did what. If *nothing* could be sent you get a 422 explaining why (not configured / no phone on file) instead of a fake "success".
- **Email = plain SMTP (stdlib `smtplib`).** Works with Gmail, Zoho, Mailgun SMTP... no vendor lock-in, no new dependency. **SMS = Termii**, a Nigerian provider (local number formats, DND rules).
- **Phone normalisation:** `0801 234 5678`, `+234 801 234 5678`, `2348012345678` are all accepted and converted to Termii's `234...` format; anything else is rejected with a clear message.
- **Errors never leak secrets.** Provider exceptions are reduced to short messages (an SMTP/HTTP exception can contain URLs or keys).

## Setup (in `backend-py/.env`)
**Email (Gmail example):** enable 2-step verification, create an *App password* at myaccount.google.com/apppasswords, then:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=<the 16-char app password>
SMTP_FROM=you@gmail.com
```
**SMS (Termii):** create an account at termii.com, get an API key and register a **Sender ID** (approval can take a day or two; until then SMS to Nigerian numbers may be blocked or use a generic route). Then:
```
TERMII_API_KEY=...
TERMII_SENDER_ID=YourBiz
TERMII_BASE_URL=https://api.ng.termii.com   # use the base URL shown in YOUR Termii dashboard docs
```
Leave either block blank and that channel is simply reported as "not configured".

> **Honest caveat:** the SMTP and Termii code is covered by tests with the network mocked, but I could not send a real email or SMS from here. Your first real send is the true test - use your own email/phone as the customer.

## Phone numbers
The invoice form now has an optional phone field for new customers. Existing customers created earlier have no phone (the SMS channel says "customer has no sms on file").
