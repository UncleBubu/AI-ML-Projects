import hashlib
import json
import logging
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import ai
from app.analytics import ai_context, insight_payload
from app.auth import AuthUser, business_id_for
from app.ratelimit import ai_rate_limit

log = logging.getLogger(__name__)
router = APIRouter()


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.post("/ask")
def ask(body: AskBody, user: AuthUser = Depends(ai_rate_limit)):
    """Day 7: plain-English financial question, answered ONLY from freshly computed numbers (Llama via LangChain)."""
    business_id = business_id_for(user)
    data = ai_context(business_id)  # always fresh: a payment made a minute ago must be reflected
    answer = ai.run(ai.QA_PROMPT, {"data": ai.to_prompt_json(data), "question": body.question.strip()})
    return {"answer": answer, "unverified_figures": ai.unverified_figures(answer, data), "as_of": data["as_of"]}


# Insights are cached per (business, range, data fingerprint) for 15 minutes: the same data
# gives the same insight instantly and costs nothing; changed data (a new payment) misses the cache.
_CACHE: dict[tuple, tuple[float, dict]] = {}
_CACHE_TTL = 900


@router.post("/insights")
def insights(range: str = "week", user: AuthUser = Depends(ai_rate_limit)):
    """Day 8: 2-3 non-obvious observations comparing this period with the previous one."""
    from fastapi import HTTPException
    if range not in ("week", "month"):
        raise HTTPException(400, "range: must be 'week' or 'month'")
    business_id = business_id_for(user)
    payload = insight_payload(business_id, range)

    stable = {k: v for k, v in payload.items() if k != "as_of"}  # as_of changes every minute; don't let it defeat the cache
    key = (business_id, range, hashlib.sha1(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest())
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL:
        return {**hit[1], "cached": True}

    text = ai.run(ai.INSIGHT_PROMPT, {"data": ai.to_prompt_json(payload)}, max_tokens=600)
    result = {"observations": ai.parse_observations(text),
              "unverified_figures": ai.unverified_figures(text, payload),
              "range": range, "as_of": payload["as_of"], "previous_period_has_data": payload["previous_period_has_data"]}
    _CACHE[key] = (time.monotonic(), result)
    return {**result, "cached": False}
