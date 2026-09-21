# Day 10 - Buffer & demo rehearsal

## 1. Seed data
`supabase/seed_demo.sql` - sign up in the app, open the Supabase SQL editor, paste the file, change `v_email` to your login email, run **once**. It creates 5 customers, 16 invoices (paid / sent / overdue / one draft / one void) over ~5 weeks, and 13 expenses. The story in the data (so the AI has something real to say):
- **Ada Stores** is your best customer but has slowed from paying in ~2 days to ~7.
- **Chidi Bakery** and **Emeka Tech Hub** have overdue invoices (Emeka's is large).
- Expenses across all six categories, rent/salaries at the start of the month.

It's idempotent (refuses to run twice). To remove it later run `supabase/cleanup_demo.sql` (it lifts the append-only triggers only for the duration of the script, and only deletes rows belonging to the demo customers).

(Seeded pay links are placeholders; the live payment step of the demo uses a *fresh* invoice with a real Paystack sandbox link.)

## 2. The demo, timed (~5 minutes) - see `DEMO_SCRIPT.md`

## 3. What to say when asked "what's real?"
> "This is a proof-of-concept with a deliberately narrow scope: one business, no multi-user roles, no bank-statement import. Within that scope everything is real, not a mockup: invoices carry real Paystack sandbox payment links; when a payment succeeds, Paystack's signed webhook flips the invoice to paid automatically, with signature verification and duplicate protection; the numbers come from a Postgres database with row-level security; and the AI answers and insights are produced by a Llama model (via LangChain) reasoning over those real computed numbers, with instructions to say 'I don't have that data' rather than guess. What's simulated is only the money itself - it's Paystack's test mode - and the demo data I loaded so the dashboard isn't empty."

## 4. Pre-demo checklist
- [ ] `supabase db push` done; `tests/rls_isolation.sql` shows only PASS
- [ ] `backend-py/.env`: Supabase, Paystack, `LLM_API_KEY` (Groq) or a running Ollama (and Telegram/SMTP/Termii if you'll show them)
- [ ] Backend and frontend running; ngrok + Paystack test webhook URL set (or plan to use "Check payment")
- [ ] Seed data loaded; log in; Ask + Insights both return answers (this also warms nothing - just proves the key works)
- [ ] Rotate any keys that were pasted into chats/screenshots
