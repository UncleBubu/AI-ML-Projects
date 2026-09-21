"""Tiny in-memory sliding-window limiter, per user. It protects your LLM provider quota (or bill) from a
runaway loop or a stuck button. (In-memory = per process; if you scale to several
server processes, move this to Redis.)"""
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from app.auth import AuthUser, require_auth
from app.config import settings

WINDOW_SECONDS = 600
_hits: dict[str, deque[float]] = defaultdict(deque)


def ai_rate_limit(user: AuthUser = Depends(require_auth)) -> AuthUser:
    now = time.monotonic()
    q = _hits[user.user_id]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    if len(q) >= settings.ai_requests_per_10min:
        raise HTTPException(429, "Too many AI requests - please wait a few minutes.")
    q.append(now)
    return user
