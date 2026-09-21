import httpx

from app.config import settings
from app.money import naira_to_kobo

BASE = "https://api.paystack.co"


def _call(method: str, path: str, json: dict | None = None) -> dict:
    # timeout: never let a slow third party hang our request forever
    resp = httpx.request(method, BASE + path, json=json, timeout=15,
                         headers={"Authorization": f"Bearer {settings.paystack_secret_key}"})
    body = resp.json() if resp.content else {}
    if resp.status_code >= 400 or not body.get("status"):
        raise RuntimeError(f"Paystack {path} failed: {body.get('message', resp.reason_phrase)}")
    return body["data"]


def initialize_transaction(*, email: str, amount_naira, reference: str, metadata: dict) -> str:
    """Returns the hosted checkout URL."""
    data = _call("POST", "/transaction/initialize", {
        "email": email,
        "amount": naira_to_kobo(amount_naira),  # kobo!
        "currency": "NGN",
        "reference": reference,
        "metadata": metadata,
    })
    return data["authorization_url"]


def verify_transaction(reference: str) -> dict:
    """Used by the manual 'check payment' fallback when the webhook can't reach localhost."""
    data = _call("GET", f"/transaction/verify/{reference}")
    return {"status": data["status"], "amount_kobo": data["amount"], "currency": data["currency"]}
