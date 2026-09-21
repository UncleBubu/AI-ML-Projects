from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from app.db import supabase


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str | None


def require_auth(authorization: str | None = Header(default=None)) -> AuthUser:
    """FastAPI dependency: verifies the bearer token with Supabase and returns the real user.
    Every route that touches business data declares `user: AuthUser = Depends(require_auth)`."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    try:
        result = supabase.auth.get_user(authorization[7:])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if not result or not result.user:
        raise HTTPException(401, "Invalid or expired token")
    return AuthUser(result.user.id, result.user.email)


def business_id_for(user: AuthUser) -> str:
    """The caller's business id, created on first use (Day 1 never created one).
    If multi-business support is ever added, this is the one function to change."""
    from postgrest.exceptions import APIError

    row = supabase.table("business").select("id").eq("owner_id", user.user_id).limit(1).execute().data
    if row:
        return row[0]["id"]
    name = f"{user.email.split('@')[0]}'s business" if user.email else "My business"
    try:
        return supabase.table("business").insert({"name": name, "owner_id": user.user_id}).execute().data[0]["id"]
    except APIError as err:
        if err.code == "23505":  # unique violation: a parallel request created it first
            return supabase.table("business").select("id").eq("owner_id", user.user_id).limit(1).execute().data[0]["id"]
        raise


def current_business(user: AuthUser = Depends(require_auth)) -> str:
    return business_id_for(user)
