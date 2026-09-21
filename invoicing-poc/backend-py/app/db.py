"""Supabase service-role client.

It bypasses RLS on purpose (trusted server code), so EVERY query made with it
must be scoped by business_id ourselves - the business id always comes from the
verified user, never from the request body.
"""
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions

from app.config import settings

supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
    options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
)


def first(response) -> dict | None:
    """First row of a query result, or None. (Avoids maybe_single() quirks across supabase-py versions.)"""
    return response.data[0] if response.data else None
