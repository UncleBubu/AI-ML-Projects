# Day 6 - Aggregation layer ("one source of truth")

**Goal:** one endpoint returns every number the dashboard and the AI agent will use.

`GET /reports/summary?range=week|month[&include_previous=true]`

## Architecture

```
app/routers/reports.py -> app/period.py (decides the time window, in Africa/Lagos)
                       -> SQL report_summary(business, from, to)
```
All arithmetic is in **one SQL function** (`migrations/..._day6_report_summary.sql`). The dashboard and (Day 7) the LLM both read its JSON, so they can never disagree.

## The timezone decision (roadmap task 1)
- Business timezone: **Africa/Lagos (WAT, UTC+1, no daylight saving)**, set once in `app/config.py` (`BUSINESS_TIMEZONE`).
- `app/period.py` turns "this week" into absolute UTC instants: week = Monday 00:00 WAT -> now; month = 1st 00:00 WAT -> now. The database only ever sees absolute instants, so it cannot silently fall back to UTC.
- Windows are half-open `[from, to)`: a payment at exactly midnight belongs to exactly one period.
- Proof: `test_sunday_2330_utc_is_already_monday_in_lagos`. Python's `zoneinfo` handles the offset math, so unlike the JS version there is no hand-rolled timezone code to get wrong.

## Metric definitions (what each number means)

| Field | Definition |
|---|---|
| `revenue` | cash **received**: `transaction.amount` with `paid_at` in the window (cash basis, not invoices issued) |
| `expenses` / `expenses_by_category` | expenses dated in the window |
| `net_cash` | `revenue - expenses` |
| `invoices_issued`, `average_invoice_value` | invoices issued in the window, excluding `void` and `draft` |
| `invoices_paid` | invoices now `paid` that received a payment in the window |
| `overdue_now`, `outstanding_now` | **point-in-time**: what is owed *today*, computed from `due_date` (correct even if the cron has not run) |
| `customer_payment_speed` | all-time average days from issue to final payment, per customer, slowest first (per-window samples would be too small to mean anything) |

## Decisions and why
- **Cash basis for revenue.** "How much came in this month" means money received. Invoiced-but-unpaid is `outstanding_now`. The two are never mixed.
- **Period-to-date, and like-for-like comparison.** `include_previous=true` compares to the *same elapsed time* into the previous period (Mon-Wed vs last Mon-Wed), capped so it never overlaps the current period. Comparing 3 days to a full last week would always look like a collapse. This feeds Day 8's "up 12%".
- **SQL function, not JS loops or views.** One round trip, computed next to the data, takes explicit parameters (views can't take a date range), and it is locked to `service_role`.
- **Output includes `timezone`, `currency`, `range`** so the LLM prompt on Day 7 can state exactly what the numbers cover.

## Test it
`curl -H "Authorization: Bearer <access_token>" "http://localhost:4000/reports/summary?range=month&include_previous=true"`
The SQL was verified against a scratch Postgres with paid/overdue/duplicate scenarios and an empty period (returns zeros/`null`, never errors).
