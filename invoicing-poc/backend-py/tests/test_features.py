"""Tests for customer reminders, the LLM layer (LangChain, no real API calls), rate limiting, insights."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import ai, analytics, notifier
from app.auth import AuthUser, current_business, require_auth
from app.main import app
from app.routers import ai as ai_router
from app.routers import customer_reminders as cr

client = TestClient(app, raise_server_exceptions=False)


# ---------- helpers ----------
class FakeQuery:
    """Every chained supabase-py call returns itself; execute() returns canned rows and records inserts."""
    def __init__(self, store, table):
        self.store, self.table_name = store, table

    def __getattr__(self, name):
        def method(*a, **k):
            if name == "insert":
                self.store.setdefault("_inserted", []).append((self.table_name, a[0]))
            return self
        return method

    def execute(self):
        return SimpleNamespace(data=self.store.get(self.table_name, []))


class FakeSupabase:
    def __init__(self, **tables):
        self.store = tables

    def table(self, name):
        return FakeQuery(self.store, name)


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    app.dependency_overrides.clear()


def as_user(uid="user-1"):
    app.dependency_overrides[require_auth] = lambda: AuthUser(uid, "u@x.com")
    app.dependency_overrides[current_business] = lambda: "biz-1"
    from app import auth
    return auth


INVOICE = {"id": "inv-1", "invoice_number": "INV-0001", "status": "overdue", "total_amount": 5000, "amount_paid": 0,
           "due_date": "2026-09-10T22:59:59+00:00", "checkout_url": "https://checkout.paystack.com/abc", "customer_id": "c1"}


# ---------- phone + message building ----------
@pytest.mark.parametrize("raw,expected", [("08012345678", "2348012345678"), ("+234 801 234 5678", "2348012345678"),
                                          ("2348012345678", "2348012345678"), ("0801-234-5678", "2348012345678")])
def test_normalize_phone(raw, expected):
    assert notifier.normalize_ng_phone(raw) == expected


@pytest.mark.parametrize("bad", ["12345", "0801234", "+1 202 555 0100", ""])
def test_normalize_phone_rejects(bad):
    with pytest.raises(ValueError):
        notifier.normalize_ng_phone(bad)


def test_reminder_message_contains_amount_due_and_link():
    subject, body, sms = notifier.build_reminder(business_name="Ebuka Ltd", customer_name="Ada", invoice={**INVOICE, "amount_paid": 1000})
    assert "INV-0001" in subject and "NGN 4,000.00" in body and "2026-09-10" in body
    assert "https://checkout.paystack.com/abc" in body and "https://checkout.paystack.com/abc" in sms
    assert "overdue" in body


# ---------- remind-customer route ----------
def setup_reminder(monkeypatch, *, invoice=INVOICE, recent=None, customer=None, email_ok=True, sms_ok=True):
    as_user()
    fake = FakeSupabase(reminder_log=recent or [], customer=[customer or {"name": "Ada", "email": "ada@x.com", "phone": "08012345678"}],
                        business=[{"name": "Ebuka Ltd"}])
    monkeypatch.setattr(cr, "supabase", fake)
    monkeypatch.setattr(cr, "get_owned_invoice", lambda b, i: invoice)
    monkeypatch.setattr(notifier, "email_configured", lambda: email_ok)
    monkeypatch.setattr(notifier, "sms_configured", lambda: sms_ok)
    sent = []
    monkeypatch.setattr(notifier, "send_email", lambda to, s, b: sent.append(("email", to)))
    monkeypatch.setattr(notifier, "send_sms", lambda to, t: sent.append(("sms", to)))
    return fake, sent


def test_reminder_sends_both_channels_and_logs(monkeypatch):
    fake, sent = setup_reminder(monkeypatch)
    r = client.post("/invoices/inv-1/remind-customer", json={})
    assert r.status_code == 200 and sent == [("email", "ada@x.com"), ("sms", "08012345678")]
    logged = [row for t, row in fake.store["_inserted"] if t == "reminder_log"]
    assert {(x["channel"], x["status"]) for x in logged} == {("email", "sent"), ("sms", "sent")}


def test_reminder_partial_success_when_sms_unconfigured(monkeypatch):
    _, sent = setup_reminder(monkeypatch, sms_ok=False)
    body = client.post("/invoices/inv-1/remind-customer", json={}).json()
    assert sent == [("email", "ada@x.com")]
    assert [x["status"] for x in body["results"]] == ["sent", "skipped"]


def test_reminder_422_explains_when_nothing_could_be_sent(monkeypatch):
    setup_reminder(monkeypatch, email_ok=False, sms_ok=False)
    r = client.post("/invoices/inv-1/remind-customer", json={})
    assert r.status_code == 422 and "SMTP" in r.json()["error"] and "TERMII" in r.json()["error"]


def test_reminder_skips_channel_when_customer_has_no_contact(monkeypatch):
    _, sent = setup_reminder(monkeypatch, customer={"name": "Ada", "email": "ada@x.com", "phone": None})
    body = client.post("/invoices/inv-1/remind-customer", json={}).json()
    assert sent == [("email", "ada@x.com")] and body["results"][1]["status"] == "skipped"


def test_reminder_failure_of_one_channel_does_not_block_the_other(monkeypatch):
    fake, sent = setup_reminder(monkeypatch)
    monkeypatch.setattr(notifier, "send_email", lambda *a: (_ for _ in ()).throw(RuntimeError("SMTP login rejected")))
    body = client.post("/invoices/inv-1/remind-customer", json={}).json()
    assert [x["status"] for x in body["results"]] == ["failed", "sent"]
    assert ("reminder_log", "failed") in [(t, r["status"]) for t, r in fake.store["_inserted"]]


def test_reminder_cooldown(monkeypatch):
    setup_reminder(monkeypatch, recent=[{"sent_at": "2026-09-19T10:00:00+00:00"}])
    assert client.post("/invoices/inv-1/remind-customer", json={}).status_code == 429


@pytest.mark.parametrize("status", ["paid", "draft", "void"])
def test_reminder_only_for_unpaid_sent_or_overdue(monkeypatch, status):
    setup_reminder(monkeypatch, invoice={**INVOICE, "status": status})
    assert client.post("/invoices/inv-1/remind-customer", json={}).status_code == 409


def test_reminder_404_for_someone_elses_invoice(monkeypatch):
    setup_reminder(monkeypatch, invoice=None)
    assert client.post("/invoices/nope/remind-customer", json={}).status_code == 404


# ---------- AI helpers ----------
def test_pct_change():
    assert ai.pct_change(112, 100) == 12.0
    assert ai.pct_change(50, 100) == -50.0
    assert ai.pct_change(50, 0) is None and ai.pct_change(50, None) is None


def test_unverified_figures_flags_invented_numbers_only():
    data = {"revenue": 1250000.5, "expenses": 300000, "net_cash": 950000.5, "week": {"n": 7}}
    assert ai.unverified_figures("Revenue was NGN 1,250,000.50 and net cash NGN 950,000.50 over 7 days (12.5% up).", data) == []
    assert ai.unverified_figures("You made NGN 2,000,000 this month.", data) == ["2,000,000"]


def test_parse_observations_caps_at_three_and_strips_bullets():
    text = "- one\n- two\n\n* three\n- four"
    assert ai.parse_observations(text) == ["one", "two", "three"]


def test_qa_prompt_embeds_data_and_the_grounding_rules():
    # braces inside the JSON data must survive: they are VALUES, not template syntax
    msgs = ai.QA_PROMPT.format_messages(data=ai.to_prompt_json({"revenue": 123, "nested": {"a": 1}}), question="how much?")
    system, human = msgs[0].content, msgs[1].content
    assert '"revenue": 123' in system and '"nested"' in system
    assert "ONLY" in system and "Never estimate" in system and "don't have that data" in system
    assert human == "<question>how much?</question>"   # injection guard wrapper


def test_insight_prompt_demands_specific_non_generic_output():
    system = ai.INSIGHT_PROMPT.format_messages(data="{}")[0].content
    assert "NOT simply a restatement" in system and "Do not do your own percentage maths" in system and 'starting with "- "' in system


def test_chain_end_to_end_with_a_fake_model(monkeypatch):
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from dataclasses import replace
    monkeypatch.setattr(ai, "settings", replace(ai.settings, llm_api_key="k"))
    monkeypatch.setattr(ai, "_llm", lambda max_tokens: FakeListChatModel(responses=["  NGN 435,000 came in.  "]))
    assert ai.run(ai.QA_PROMPT, {"data": "{}", "question": "q?"}) == "NGN 435,000 came in."


def test_llm_configured_rules(monkeypatch):
    from dataclasses import replace
    def cfg(url, key): monkeypatch.setattr(ai, "settings", replace(ai.settings, llm_base_url=url, llm_api_key=key)); return ai.llm_configured()
    assert cfg("https://api.groq.com/openai/v1", "") is False
    assert cfg("https://api.groq.com/openai/v1", "gsk_x") is True
    assert cfg("http://localhost:11434/v1", "") is True      # local Ollama needs no key


def test_ai_not_configured_gives_clear_503(monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(ai, "settings", replace(ai.settings, llm_base_url="https://api.groq.com/openai/v1", llm_api_key=""))
    as_user()
    monkeypatch.setattr(ai_router, "business_id_for", lambda u: "biz-1")
    monkeypatch.setattr(ai_router, "ai_context", lambda b: {"as_of": "now"})
    r = client.post("/ask", json={"question": "how much came in this month?"})
    assert r.status_code == 503 and "LLM_API_KEY" in r.json()["error"]


# ---------- /ask ----------
CONTEXT = {"as_of": "2026-09-19T12:00", "week": {"current": {"revenue": 435000.0}}, "month": {"current": {"revenue": 1235000.0}}}


def test_ask_returns_answer_and_flags_ungrounded_numbers(monkeypatch):
    as_user()
    seen = {}
    monkeypatch.setattr(ai_router, "business_id_for", lambda u: "biz-1")
    monkeypatch.setattr(ai_router, "ai_context", lambda b: CONTEXT)
    monkeypatch.setattr(ai, "run", lambda prompt, variables, max_tokens=500: (seen.update(prompt=prompt, **variables), "NGN 435,000 came in this week, about NGN 9,999,999 overall.")[1])
    r = client.post("/ask", json={"question": "how much came in this week?"})
    assert r.status_code == 200 and r.json()["unverified_figures"] == ["9,999,999"]
    assert seen["prompt"] is ai.QA_PROMPT and '"revenue": 435000.0' in seen["data"] and seen["question"] == "how much came in this week?"


def test_ask_validates_question(monkeypatch):
    as_user()
    assert client.post("/ask", json={"question": "hi"}).status_code == 400
    assert client.post("/ask", json={"question": "x" * 501}).status_code == 400


def test_ai_endpoints_are_rate_limited(monkeypatch):
    from dataclasses import replace
    from app import ratelimit
    monkeypatch.setattr(ratelimit, "settings", replace(ratelimit.settings, ai_requests_per_10min=2))
    ratelimit._hits.clear()
    app.dependency_overrides[require_auth] = lambda: AuthUser("rate-user", None)
    monkeypatch.setattr(ai_router, "business_id_for", lambda u: "biz-1")
    monkeypatch.setattr(ai_router, "ai_context", lambda b: CONTEXT)
    monkeypatch.setattr(ai, "run", lambda *a, **k: "ok")
    codes = [client.post("/ask", json={"question": "how much came in?"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    ratelimit._hits.clear()


# ---------- /insights ----------
def test_insight_payload_precomputes_changes_and_customer_deltas(monkeypatch):
    calls = {"n": 0}

    def summary(business_id, period):
        calls["n"] += 1
        return ({"revenue": 200.0, "expenses": 50.0, "net_cash": 150.0, "average_invoice_value": 100.0, "invoices_issued": 2, "invoices_paid": 2}
                if calls["n"] == 1 else
                {"revenue": 100.0, "expenses": 0, "net_cash": 100.0, "average_invoice_value": 50.0, "invoices_issued": 2, "invoices_paid": 1})

    stats = iter([
        [{"customer_id": "a", "customer_name": "Ada", "revenue": 200, "payments": 1, "avg_days_to_payment": 7.0}],
        [{"customer_id": "a", "customer_name": "Ada", "revenue": 100, "payments": 1, "avg_days_to_payment": 2.0},
         {"customer_id": "b", "customer_name": "Bola", "revenue": 10, "payments": 1, "avg_days_to_payment": 1.0}],
    ])
    monkeypatch.setattr(analytics, "build_summary", summary)
    monkeypatch.setattr(analytics, "_customer_stats", lambda b, p: next(stats))
    p = analytics.insight_payload("biz-1", "week")
    assert p["changes"]["revenue"]["pct_change"] == 100.0
    assert p["changes"]["expenses"]["pct_change"] is None            # previous was 0: no fake percentage
    assert p["customer_changes"] == [{"customer_name": "Ada", "revenue": 200, "previous_revenue": 100,
                                      "avg_days_to_payment": 7.0, "previous_avg_days_to_payment": 2.0, "days_change": 5.0}]
    assert p["previous_period_has_data"] is True


def test_insights_endpoint_caches_identical_data(monkeypatch):
    as_user("ins-user")
    ai_router._CACHE.clear()
    payload = {"as_of": "t1", "range": "week", "previous_period_has_data": True, "x": 1}
    monkeypatch.setattr(ai_router, "business_id_for", lambda u: "biz-1")
    monkeypatch.setattr(ai_router, "insight_payload", lambda b, r: {**payload, "as_of": "t" + str(len(calls))})
    calls = []
    monkeypatch.setattr(ai, "run", lambda *a, **k: (calls.append(1), "- Ada now pays 5 days slower.\n- Overdue is concentrated in Emeka.")[1])
    first, second = client.post("/insights?range=week").json(), client.post("/insights?range=week").json()
    assert first["cached"] is False and second["cached"] is True and len(calls) == 1
    assert first["observations"] == ["Ada now pays 5 days slower.", "Overdue is concentrated in Emeka."]
    assert client.post("/insights?range=year").status_code == 400
    ai_router._CACHE.clear()


# ---------- provider plumbing (mocked) ----------
def test_send_email_uses_starttls_login_and_sends(monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(notifier, "settings", replace(notifier.settings, smtp_host="smtp.test", smtp_port=587, smtp_user="u", smtp_password="p", smtp_from="me@x.com", smtp_starttls=True))
    events = []

    class FakeSMTP:
        def __init__(self, host, port, timeout): events.append(("connect", host, port))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): events.append("starttls")
        def login(self, u, p): events.append(("login", u))
        def send_message(self, msg): events.append(("send", msg["To"], msg["Subject"]))

    monkeypatch.setattr(notifier.smtplib, "SMTP", FakeSMTP)
    notifier.send_email("ada@x.com", "Hi", "Body")
    assert events == [("connect", "smtp.test", 587), "starttls", ("login", "u"), ("send", "ada@x.com", "Hi")]


def test_send_email_auth_failure_is_a_friendly_error(monkeypatch):
    import smtplib
    from dataclasses import replace
    monkeypatch.setattr(notifier, "settings", replace(notifier.settings, smtp_host="smtp.test", smtp_from="me@x.com", smtp_user="u"))

    class BadSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): raise smtplib.SMTPAuthenticationError(535, b"nope")

    monkeypatch.setattr(notifier.smtplib, "SMTP", BadSMTP)
    with pytest.raises(RuntimeError, match="app password"):
        notifier.send_email("a@x.com", "s", "b")


def test_send_sms_posts_normalised_number(monkeypatch):
    import httpx
    from dataclasses import replace
    monkeypatch.setattr(notifier, "settings", replace(notifier.settings, termii_api_key="key", termii_sender_id="ACME", termii_base_url="https://sms.test"))
    captured = {}
    monkeypatch.setattr(notifier.httpx, "post", lambda url, **k: (captured.update(url=url, json=k["json"]), httpx.Response(200, json={"code": "ok"}))[1])
    notifier.send_sms("0801 234 5678", "hello")
    assert captured["url"] == "https://sms.test/api/sms/send" and captured["json"]["to"] == "2348012345678" and captured["json"]["from"] == "ACME"


@pytest.mark.parametrize("exc_name,status,fragment", [
    ("AuthenticationError", 502, "LLM_API_KEY"), ("NotFoundError", 502, "LLM_MODEL"),
    ("RateLimitError", 429, "rate limit"), ("APIConnectionError", 502, "LLM_BASE_URL"),
])
def test_provider_errors_become_friendly_http_errors(monkeypatch, exc_name, status, fragment):
    import httpx, openai
    from dataclasses import replace
    from fastapi import HTTPException
    from langchain_core.runnables import RunnableLambda
    monkeypatch.setattr(ai, "settings", replace(ai.settings, llm_api_key="gsk_secret_value"))
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions?key=gsk_secret_value")

    def boom(_):
        cls = getattr(openai, exc_name)
        raise cls(request=req) if exc_name == "APIConnectionError" else cls("bad", response=httpx.Response(status if status != 502 else 401, request=req), body=None)

    monkeypatch.setattr(ai, "_llm", lambda max_tokens: RunnableLambda(boom))
    with pytest.raises(HTTPException) as e:
        ai.run(ai.QA_PROMPT, {"data": "{}", "question": "q?"})
    assert e.value.status_code == status and fragment in e.value.detail
    assert "gsk_secret_value" not in e.value.detail


def test_real_langchain_client_wire_format_against_a_fake_openai_compatible_server(monkeypatch):
    """No mocks of our code: the REAL ChatOpenAI client talks HTTP to a local stand-in for Groq/Ollama/Together.
    Pins: endpoint path, bearer auth, model, temperature 0, classic `max_tokens`, system+user messages."""
    import json, threading
    from dataclasses import replace
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            seen.update(path=self.path, auth=self.headers.get("authorization"), body=body)
            out = json.dumps({"id": "1", "object": "chat.completion", "created": 0, "model": body["model"],
                              "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "- Ada pays slower."}}]}).encode()
            self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(ai, "settings", replace(ai.settings, llm_base_url=f"http://127.0.0.1:{server.server_port}/v1",
                                                     llm_api_key="gsk_test", llm_model="llama-3.3-70b-versatile"))
        text = ai.run(ai.INSIGHT_PROMPT, {"data": '{"a": {"b": 1}}'}, max_tokens=321)
    finally:
        server.shutdown()
    assert text == "- Ada pays slower."
    assert seen["path"] == "/v1/chat/completions" and seen["auth"] == "Bearer gsk_test"
    b = seen["body"]
    assert b["model"] == "llama-3.3-70b-versatile" and b["temperature"] == 0 and b["max_tokens"] == 321
    assert "max_completion_tokens" not in b
    assert [m["role"] for m in b["messages"]] == ["system", "user"] and '{"a": {"b": 1}}' in b["messages"][0]["content"]
