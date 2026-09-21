# Day 7 - Llama-powered questions ("Ask about your finances")

**Goal:** ask a plain-English money question, get a grounded, accurate answer - and a refusal when the data doesn't contain the answer.

`POST /ask {question}` -> `analytics.ai_context()` (fresh numbers) -> **LangChain chain** `prompt | Llama | parser` -> `{answer, unverified_figures, as_of}`

## The design in one sentence
**The model never touches the database and never calculates the business's figures.** SQL computes every number (Day 6); we paste that JSON into the prompt; the model only *reads and explains* it.

## LangChain + Llama: how it's wired (`app/ai.py`)
```python
chain = QA_PROMPT | ChatOpenAI(model=..., base_url=..., temperature=0) | StrOutputParser()
answer = chain.invoke({"data": json_of_numbers, "question": q})
```
- **LCEL chain** (`prompt | model | parser`): the prompt is a `ChatPromptTemplate` with `{data}` and `{question}` variables. Because they are *variables*, braces inside the JSON data can never be mistaken for template syntax.
- **Why `ChatOpenAI` for Llama?** Llama is an open model; you run it through a *host*. Nearly all hosts (Groq, Together, OpenRouter, Meta's Llama API, and local Ollama) expose the OpenAI-compatible chat protocol, and LangChain's `ChatOpenAI(base_url=...)` speaks it. So **switching Llama host = editing 3 lines of `.env`, zero code**. (`langchain-groq` / `langchain-ollama` also exist; they'd lock the code to one host for no gain here.)
- **Default: Groq + `llama-3.3-70b-versatile`** - a free tier, very fast, and 70B is strong enough to follow "use only these numbers". Local option: Ollama + `llama3.1:8b` (private and free, but weaker; see below).

## What is sent to the model
This week and this month, each with its like-for-like previous period (4 calls of `report_summary`), plus `as_of`, timezone and currency. That covers all four target questions: money in this month, average invoice value, red/green this week, slow payers (`customer_payment_speed`).

## Decisions and why
- **Grounding rules in the system prompt (`QA_PROMPT`):** use only supplied numbers; if it isn't in the data say "I don't have that data" and say what you *do* have; never estimate. Field definitions are included so "revenue" means cash received, not invoices issued.
- **Prompt-injection guard:** the question is wrapped in `<question>` tags and the prompt says to treat it purely as a question.
- **`temperature=0`:** the same question on the same data gives the same answer.
- **Open models need a stronger safety net than hosted frontier models, so the number check matters more.** After the model answers, code scans for money-sized numbers (>= 100) that appear *nowhere* in the data and the UI shows "Double-check: ...". It also flags sums the model worked out itself - deliberate. Smaller models (8B) hallucinate and mis-add more often; the 70B default is recommended for the demo.
- **Insight parsing tolerates chatty models:** Llama often writes "Here are 3 observations:" first. Only bullet lines are kept (`parse_observations`).
- **Always fresh data, no caching** for /ask. **Rate limit** 20 AI requests per user per 10 minutes.
- **Clear failures:** no key -> 503 "set LLM_API_KEY"; wrong key -> 502; wrong model name -> 502 "check LLM_MODEL"; provider free-tier limit -> 429; unreachable (Ollama not running) -> 502 "check LLM_BASE_URL". Never the raw exception (it can contain URLs/keys).
- **`max_tokens` is sent as the classic field via `extra_body`.** `ChatOpenAI`'s own `max_tokens=` is now sent as `max_completion_tokens`, which Ollama/Together and others may reject. A test pins the exact wire format against a fake OpenAI-compatible server.

## Setup
**Groq (default):** create a free key at console.groq.com/keys, then in `backend-py/.env`:
```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=gsk_...
LLM_MODEL=llama-3.3-70b-versatile
```
**Local Ollama:** install Ollama, `ollama pull llama3.1:8b`, then `LLM_BASE_URL=http://localhost:11434/v1`, leave `LLM_API_KEY` blank, `LLM_MODEL=llama3.1:8b`. **Together / OpenRouter** presets are in `.env.example`. Install deps: `pip install -r requirements.txt`, restart the backend.

## The most important test (roadmap task 4)
Run these in the UI with the demo data loaded (Day 10):
1. "How much came in this month?" -> should match "Money in" on the summary.
2. "What's my average invoice value?"
3. "Am I in the red or green this week?"
4. "Which customers are slow payers?" -> Bola Logistics / Ada Stores.
5. **Trick question:** "What was my profit margin on shoes last year?" or "Predict next month's revenue" -> it must say it doesn't have that data and must not produce a number. If a Llama model ever invents one, tighten the prompt (rule 2 in `_QA_SYSTEM`) or use a bigger model **before anything else**.

> **Honest caveat:** the prompt rendering, LangChain chain, HTTP wire format, error mapping and number-check are covered by automated tests (the model itself replaced by a fake / a local stand-in server). I could not call a real Llama endpoint from here, so the five checks above, especially the trick question, are yours to run.

## Ollama vs Groq: which one to pick
Ollama is a runner for models on your own machine, Groq is a hosted service running Llama for you; both serve Llama, so the choice is *where* it runs.
- **Groq + 70B:** best accuracy and speed; needs a key, has free-tier rate limits, and sends aggregated numbers to a third party. Use it for demos.
- **Ollama:** free, private, offline. Quality depends on your hardware; with only an 8B model expect more invented numbers. If you have the memory, use a bigger model (`llama3.1:70b`, or `qwen2.5:14b` as a middle ground).
- Whichever you use, rerun the trick-question test above; small local models stress the `unverified_figures` guard the most.
