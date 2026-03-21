from supabase import Client, create_client

from config import get_settings

# ── Singleton instance ────────────────────────────────────────────────────────
# Created once when this module is first imported.
# Uses service role key to bypass RLS — backend use only, never expose to frontend.
_settings = get_settings()

_supabase_client: Client = create_client(
    supabase_url=_settings.supabase_url,
    supabase_key=_settings.supabase_service_role_key,
)


def get_supabase() -> Client:
    """
    Returns the shared Supabase client singleton.

    Used as a FastAPI dependency in route handlers:
        @router.get("/example")
        async def example(supabase: Client = Depends(get_supabase)):
            ...

    Uses service role key — bypasses RLS.
    Only used in backend server code, never exposed to frontend.
    """
    return _supabase_client