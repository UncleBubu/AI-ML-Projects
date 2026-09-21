import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.money import kobo_to_naira, naira_to_kobo
from app.routers import webhooks

client = TestClient(app, raise_server_exceptions=False)
SECRET = b"sk_test_secret"


class FakeRpc:
    """Stands in for supabase.rpc(...).execute(): records calls, returns/raises what we set."""
    def __init__(self):
        self.calls, self.result, self.error = [], {"result": "recorded"}, None

    def __call__(self, fn, args):
        self.calls.append((fn, args))
        return self

    def execute(self):
        if self.error:
            raise self.error
        return type("R", (), {"data": self.result})()


@pytest.fixture
def rpc(monkeypatch):
    fake = FakeRpc()
    monkeypatch.setattr(webhooks.supabase, "rpc", fake)
    return fake


def sign(body: bytes) -> str:
    return hmac.new(SECRET, body, hashlib.sha512).hexdigest()


def post(body: bytes, sig: str | None = None):
    headers = {"content-type": "application/json", **({"x-paystack-signature": sig} if sig else {})}
    return client.post("/webhooks/paystack", content=body, headers=headers)


GOOD = b'{"event":"charge.success","data":{"reference":"INV-0001-abc","amount":310099,"currency":"NGN"}}'


def test_missing_signature_rejected(rpc):
    assert post(GOOD).status_code == 401


def test_wrong_signature_rejected(rpc):
    assert post(GOOD, "deadbeef").status_code == 401 and not rpc.calls


def test_valid_signature_records_payment_in_naira(rpc):
    assert post(GOOD, sign(GOOD)).status_code == 200
    assert rpc.calls == [("record_payment", {"p_reference": "INV-0001-abc", "p_amount": "3100.99", "p_provider": "paystack"})]


def test_signature_covers_raw_bytes_whitespace_matters(rpc):
    spaced = GOOD.replace(b",", b", ")
    assert post(spaced, sign(GOOD)).status_code == 401
    assert post(spaced, sign(spaced)).status_code == 200


def test_malformed_json_with_valid_signature_is_400(rpc):
    assert post(b"{nope", sign(b"{nope")).status_code == 400


def test_other_events_acknowledged_not_recorded(rpc):
    body = b'{"event":"transfer.success","data":{}}'
    assert post(body, sign(body)).status_code == 200 and not rpc.calls


def test_non_ngn_ignored(rpc):
    body = b'{"event":"charge.success","data":{"reference":"x","amount":100,"currency":"USD"}}'
    assert post(body, sign(body)).status_code == 200 and not rpc.calls


def test_duplicate_delivery_still_200(rpc):
    rpc.result = {"result": "duplicate"}
    assert post(GOOD, sign(GOOD)).status_code == 200


def test_db_failure_returns_500_so_paystack_retries(rpc):
    rpc.error = RuntimeError("db down")
    assert post(GOOD, sign(GOOD)).status_code == 500


@pytest.mark.parametrize("path", ["/invoices", "/expenses", "/reports/summary", "/customers", "/reminders/overdue"])
def test_api_routes_require_a_token(path):
    r = client.get(path)
    assert r.status_code == 401 and r.json() == {"error": "Missing bearer token"}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_money_conversion_is_exact():
    assert naira_to_kobo("19.99") == 1999          # float math gives 1998.99999...
    assert naira_to_kobo(1500.5 * 2 + 99.99) == 310099
    assert str(kobo_to_naira(310099)) == "3100.99"


def test_validation_errors_use_the_error_key_the_frontend_reads():
    from app.auth import current_business
    app.dependency_overrides[current_business] = lambda: "biz-1"
    try:
        bad_qty = {"customer_id": "33333333-3333-3333-3333-333333333333", "due_date": "2026-10-01",
                   "line_items": [{"description": "x", "quantity": 1.5, "unit_price": "10"}]}
        r = client.post("/invoices", json=bad_qty)
        assert r.status_code == 400 and "line_items.0.quantity" in r.json()["error"]
        too_precise = {**bad_qty, "line_items": [{"description": "x", "quantity": 1, "unit_price": "10.999"}]}
        assert client.post("/invoices", json=too_precise).status_code == 400
        assert client.post("/expenses", json={"category": "snacks", "amount": "5"}).status_code == 400
        assert client.post("/expenses", json={"category": "rent", "amount": "-5"}).status_code == 400
        assert client.get("/reports/summary?range=year").status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_malformed_telegram_token_falls_back_to_log_only(monkeypatch):
    from dataclasses import replace
    from app.jobs import overdue
    good = "123456789:AAFREEGasmSQl9zvR1fi2dBWIbNh644ewPY"
    for token, chat, expected in [("HTTP API:", "42", False), ("", "42", False),
                                  (good, "", False), (good, "42", True)]:
        monkeypatch.setattr(overdue, "settings", replace(overdue.settings, telegram_bot_token=token, telegram_chat_id=chat))
        assert overdue.telegram_configured() is expected


def test_telegram_errors_never_leak_the_token(monkeypatch):
    import httpx
    from dataclasses import replace
    from app.jobs import overdue
    token = "123456789:AAFREEGasmSQl9zvR1fi2dBWIbNh644ewPY"
    monkeypatch.setattr(overdue, "settings", replace(overdue.settings, telegram_bot_token=token, telegram_chat_id="42"))

    def boom(*a, **k):
        raise httpx.ConnectError(f"failed for https://api.telegram.org/bot{token}/sendMessage")
    monkeypatch.setattr(overdue.httpx, "post", boom)
    with pytest.raises(RuntimeError) as e:
        overdue._send_telegram("hi")
    assert token not in str(e.value)

    monkeypatch.setattr(overdue.httpx, "post", lambda *a, **k: httpx.Response(400, json={"description": "Bad Request: chat not found"}))
    with pytest.raises(RuntimeError, match="chat not found"):
        overdue._send_telegram("hi")
