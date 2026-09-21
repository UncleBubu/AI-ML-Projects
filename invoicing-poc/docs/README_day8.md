# Day 8 - Narrative insights (your demo moment)

**Goal:** one click -> 2-3 observations a sharp accountant would make, *not* a restatement of the dashboard.

`POST /insights?range=week|month` -> `analytics.insight_payload()` -> LangChain chain (Llama) -> `{observations[], unverified_figures, ...}`

## What the model gets (that Q&A doesn't)
- Current and previous period summaries, side by side.
- **`changes`: percentage changes precomputed in Python** (`pct_change`), `null` when the previous value is 0 (no fake "+infinity%").
- **Per-customer stats for both periods** (new SQL function `customer_period_stats`: revenue, payments, average days to pay) and **`customer_changes`** for customers who paid in both windows, with `days_change`. This is what makes "your best customer now pays 5 days slower" possible; the all-time average alone would hide it.
- `previous_period_has_data`, so it can say "no baseline yet" instead of inventing a trend.

## Decisions and why
- **Separate endpoint and prompt from Q&A.** Different job: Q&A answers a question; insights *notice* things.
- **The prompt bans weak output** ("revenue was NGN X") and shows what good looks like (slower payers, concentrated overdue money, expenses outrunning revenue). It allows fewer than 3 observations when the data can't support more - inventing filler is worse.
- **Percentages computed by code, not the model.** LLMs are unreliable at arithmetic; we hand over finished numbers and forbid re-computing.
- **Output format: lines starting with "- "**, parsed and capped at 3 (`parse_observations`) - simpler and more robust than asking a model for JSON.
- **15-minute cache keyed by a fingerprint of the data.** Same data -> instant identical result, no cost; a new payment changes the fingerprint -> fresh insight. (`as_of` is excluded from the fingerprint or the cache would never hit.)
- Same `unverified_figures` check and rate limit as Day 7.

## Tuning the prompt (roadmap task 3)
Load the demo data, click **Generate insights** for "This week vs last" and "This month vs last". You want to see things like Ada's slowing payments (2 days -> 7 days) and overdue money concentrated in Emeka Tech Hub / Chidi Bakery. If output is generic, edit `INSIGHT_SYSTEM` in `app/ai.py` (add an example of the tone you want) and regenerate; the cache misses automatically only when *data* changes, so restart the server (or wait 15 min) to see prompt changes.
