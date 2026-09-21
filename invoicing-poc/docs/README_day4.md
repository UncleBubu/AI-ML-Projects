# Day 4 - Overdue invoices + reminders

**Goal:** an unpaid invoice past its due date raises a visible alert without you looking.

## Pieces

| File | Job |
|---|---|
| `migrations/..._day4_overdue.sql` | `mark_overdue_invoices()` - one UPDATE: `sent` -> `overdue` where `due_date < now()` |
| `app/jobs/overdue.py` | the whole cycle: mark, find un-alerted, send digest, stamp `reminder_sent_at` |
| `app/jobs/scheduler.py` | `APScheduler`, daily at 08:00 **Lagos time**, plus a catch-up run at boot |
| `app/routers/reminders.py` | `GET /reminders/overdue` (banner), `POST /reminders/run` (manual button), `GET /jobs/status` |
| `components/OverdueBanner.tsx` | red banner + "Send reminder now" |

## Decisions and why

- **Alerts go to you (the seller), not the customer** - as the roadmap says, avoiding the customer-channel verification problem.
- **Two delivery modes.** With `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` set it sends a Telegram message; otherwise it logs and the dashboard banner is the alert. (Create a bot with @BotFather, message it once, read your chat id from `https://api.telegram.org/bot<token>/getUpdates`.)
- **One digest message, not N pings.** Five overdue invoices = one message.
- **`reminder_sent_at` is stamped only after a successful send.** If Telegram is down, the next run retries instead of silently dropping the alert. The interval (`REMINDER_INTERVAL_HOURS`, default 24) controls how often you get nagged.
- **The banner is computed from `due_date`, not from the `overdue` status.** So it is correct even if the cron has not run yet.
- **Catch-up run on boot.** The roadmap's pitfall: free hosts sleep idle servers. If the server was asleep at 08:00, it runs the job when it wakes. It is safe to repeat because of `reminder_sent_at`.
- **Set-based SQL, not a JS loop,** for marking overdue: one round trip however many invoices there are.
- **`misfire_grace_time=3600` + `coalesce=True`** (APScheduler): if the process was busy or asleep at 08:00 the job still runs when it can (up to an hour late), and several missed runs collapse into one.
- **A job failure logs and is recorded in `lastRun.error`; it never crashes the API.** `GET /jobs/status` shows if the scheduler is alive.
- **Payment beats overdue:** `record_payment` accepts `overdue` invoices, so paying a late invoice makes it `paid`.
- Cut-list fallback is already there: "Send reminder now" works even with `DISABLE_SCHEDULER=true`.

## Setting up Telegram (the parts that tripped people up)
- **Bot token:** from @BotFather. It looks like `123456789:AAF...`. Paste *only* that. Do not include the words "HTTP API:" from BotFather's message; that produces a 404 on `sendMessage`. The code now validates the format and logs a clear error instead of calling a broken URL.
- **Chat ID:** send your bot any message first, then open `https://api.telegram.org/bot<token>/getUpdates` and read `message.chat.id`. It is a number (can be negative for groups).
- **`REMINDER_CRON`:** standard 5-field cron, evaluated in Lagos time. `0 8 * * *` = every day 08:00. Leave the default unless you want a different hour.
- Not configured? The job logs instead of sending. That is the "log-only" in the result line.

## Reading the result of "Send reminder now"
- `Marked N overdue` = invoices flipped from `sent` to `overdue` in this run. `0` just means none newly crossed their due date.
- `alerted M` = invoices included in the Telegram digest. `0` happens when there are no overdue invoices, or every one was already alerted within `REMINDER_INTERVAL_HOURS` (the `reminder_sent_at` stamp). To re-test, clear it: `update invoice set reminder_sent_at = null;`.
- **Where alerts arrive:** the dashboard banner (always), your Telegram chat (if configured), and the server log. Customers are never messaged by this job; that is the separate manual button in `README_customer_reminders.md`.

## Test it
1. Create an invoice with a due date of yesterday (or `update invoice set due_date = now() - interval '2 days'` in the Supabase SQL editor).
2. Click "Send reminder now" -> status becomes `overdue`, a message/log appears, `reminder_sent_at` is set.
3. Click again -> `alerted: 0` (no duplicate until the interval passes).
