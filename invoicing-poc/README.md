# AI-Powered Invoicing & Cash-Flow Agent (10-day PoC)

Single-business invoicing for Nigerian SMEs: Paystack sandbox payment links, automatic payment confirmation by webhook, overdue alerts to the seller, manual per-invoice reminders to the customer (email and SMS), expense logging, and a Llama assistant (LangChain) that answers questions and writes insights grounded strictly in your own data.

| Part | Tech |
|---|---|
| Frontend | React + Vite + TypeScript (`frontend/`) |
| Backend | Python, FastAPI (`backend-py/`). The old TypeScript `backend/` is superseded and safe to delete |
| Database/Auth | Supabase Postgres with RLS; money logic in SQL functions (`supabase/migrations/`) |
| Payments | Paystack (sandbox) |
| AI | Meta Llama via LangChain `ChatOpenAI` (Groq by default; Ollama, Together, OpenRouter via `.env`) |
| Jobs | APScheduler, daily overdue job at 08:00 Lagos time, plus a catch-up run at boot |
| Notifications | Telegram (seller alerts), SMTP email and Termii SMS (customer reminders) |

## First-time setup checklist
1. `supabase db push` (applies all migrations, including the security hardening).
2. Create `backend-py/.env` from `.env.example` and `frontend/.env` (Supabase URL + anon key + API URL).
3. In `backend-py`: create a virtualenv and `pip install -r requirements.txt`.
4. Optional services, each independent and skipped cleanly if unset:
   - **AI:** `LLM_API_KEY` (free key at console.groq.com/keys). Without it, Ask and Insights return a "not configured" error.
   - **Telegram:** `TELEGRAM_BOT_TOKEN` (bare `123456789:AAF...`, no "HTTP API:" label) and `TELEGRAM_CHAT_ID`.
   - **Email:** `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` (Gmail needs an app password), port 587 with STARTTLS.
   - **SMS:** `TERMII_API_KEY` and `TERMII_SENDER_ID` (the sender ID needs Termii approval, and texts cost credit).
5. Optional: load demo data with `supabase/seed_demo.sql` (edit the email at the top first).

## Run it
```powershell
cd backend-py
minivenv\Scripts\activate                          # your virtualenv
uvicorn app.main:app --reload --port 4000

cd frontend                                        # second terminal
npm install
npm run dev
```
Settings load once at startup, so restart the backend after editing `.env`. For webhooks on localhost, run `ngrok http 4000` and set the Paystack test webhook to `https://<id>.ngrok-free.app/webhooks/paystack`, or use the "Check payment" button instead.

## Test it
- **Python:** `cd backend-py && pytest` (66 tests: webhook signatures, timezones, money, reminders, AI grounding and wire format, rate limits; external services are mocked).
- **Database:** run `supabase/tests/rls_isolation.sql` in the Supabase SQL editor (expect only PASS lines).
- **AI trick question:** ask about a customer or figure that doesn't exist and confirm it declines (see `docs/README_day7.md`).
- **Paystack test card:** `4084 0840 8408 4081`, any future expiry, CVV `408`, OTP `123456`.

## Learning notes (`docs/`)
Start with **`docs/PROJECT_GUIDE.md`**: the whole project, architecture and every day in one document. Then the per-day files go deeper:

Day 2 invoices + payment link, Day 3 webhooks, Day 4 overdue alerts (incl. Telegram setup), Day 5 expenses, Day 6 aggregation, Customer reminders, Day 7 Llama Q&A (incl. Groq vs Ollama), Day 8 insights, Day 9 hardening, Day 10 demo (+ `DEMO_SCRIPT.md`).

## The three rules that make it trustworthy
1. Webhook signatures are always verified, and payments are recorded idempotently.
2. Money is computed once, in SQL, and everything (dashboard, AI) reads that.
3. The LLM only reasons over numbers we hand it, and says "I don't have that data" otherwise.

## Known limits and not built
- **Not verified live from the build environment:** Supabase, Paystack, Groq, SMTP, Termii and Telegram were tested against mocks. Run each once for real.
- **No deployment files** (Procfile/Dockerfile). It runs locally. Free hosts sleep idle servers, which the boot catch-up run covers, but that hasn't been tested on a real host.
- **Email** supports STARTTLS on port 587 only (not implicit SSL on 465). **WhatsApp** was deliberately left out because it needs a paid business account and approved templates.
- **Smaller Llama models** (e.g. 8B via Ollama) invent numbers more often; use the 70B model for demos. The `unverified_figures` guard catches most slips, not all.
- **Scope cuts** from the roadmap still apply: one business per owner, no multi-user roles, no bank import.
