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