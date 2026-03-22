from fastapi import Depends, HTTPException, Request, status

from config import get_settings
from db.supabase import get_supabase


async def get_current_user(
    request: Request,
    supabase=Depends(get_supabase),
):
    """
    FastAPI dependency — validates the session cookie and returns the
    authenticated Supabase user object.

    Usage in any protected route:
        @router.get("/example")
        async def example(user = Depends(get_current_user)):
            return {"user_id": user.id}

    Raises:
        HTTP 401 — if cookie is missing or session is invalid/expired
    """
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
            )
        return response.user
    except HTTPException:
        # Re-raise HTTP exceptions as-is (don't wrap them)
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )