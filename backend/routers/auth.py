"""
Auth Router — cv-agent backend

Handles all authentication endpoints:
    POST /auth/register  — create new user account
    POST /auth/login     — authenticate and set session cookie
    POST /auth/logout    — invalidate session and clear cookie
    GET  /auth/me        — get current authenticated user profile

All routes delegate credential validation to Supabase Auth.
JWT tokens are stored exclusively in httpOnly cookies — never in
localStorage or response bodies.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from db.supabase import get_supabase
from models.auth import RegisterRequest, UserResponse

from fastapi import Response
from models.auth import LoginRequest

from db.auth import get_current_user
from models.auth import MessageResponse

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    supabase=Depends(get_supabase),
):
    """
    Register a new user account.

    Creates a Supabase Auth entry and a corresponding public.users profile row.
    Does NOT set a session cookie — user must login separately after registering.
    """
    # Step 1 — Create user in Supabase Auth
    try:
        auth_response = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Email may already be in use.",
        )

    user_id = str(auth_response.user.id)

    # Step 2 — Insert profile into public.users
    # Uses service role client to bypass RLS — backend operation only
    try:
        db_response = supabase.table("users").insert({
            "id": user_id,
            "name": body.name,
            "email": body.email,
        }).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create user profile: {str(e)}",
        )

    inserted_user = db_response.data[0]

    return UserResponse(
        id=inserted_user["id"],
        name=inserted_user["name"],
        email=inserted_user["email"],
        created_at=inserted_user.get("created_at"),
        updated_at=inserted_user.get("updated_at"),
    )


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    supabase=Depends(get_supabase),
):
    """
    Authenticate user and set session cookie.

    Sets JWT token as httpOnly cookie — token is never included in response body.
    User must call GET /auth/me to get their profile after login.
    """
    settings = get_settings()

    from config import get_settings

    # Step 1 — Authenticate with Supabase Auth
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not auth_response.user or not auth_response.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Step 2 — Set JWT as httpOnly cookie
    # Token never appears in response body — lives only in the cookie
    access_token = auth_response.session.access_token
    expires_in = auth_response.session.expires_in or 3600

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=expires_in,
    )

    # Step 3 — Fetch user profile from public.users
    db_response = supabase.table("users").select("*").eq(
        "id", str(auth_response.user.id)
    ).single().execute()

    user = db_response.data

    return UserResponse(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at"),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    supabase=Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    """
    Invalidate the current session and clear the session cookie.

    Two-step logout:
    1. Sign out from Supabase Auth (invalidates the token server-side)
    2. Clear the httpOnly cookie from the browser (max_age=0)
    """
    settings = get_settings()

    # Step 1 — Invalidate session in Supabase Auth
    try:
        supabase.auth.sign_out()
    except Exception:
        # Even if sign_out fails, we still clear the cookie
        pass

    # Step 2 — Delete cookie by setting max_age=0
    response.set_cookie(
        key=settings.auth_cookie_name,
        value="",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=0,
    )

    return MessageResponse(message="Logged out successfully")