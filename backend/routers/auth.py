"""
Auth Router - cv-agent backend

Handles all authentication endpoints:
    POST /auth/register  - create new user account
    POST /auth/login     - authenticate and set session cookie
    POST /auth/logout    - invalidate session and clear cookie
    GET  /auth/me        - get current authenticated user profile

All routes delegate credential validation to Supabase Auth.
JWT tokens are stored exclusively in httpOnly cookies, never in
localStorage or response bodies.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from config import get_settings
from db.auth import get_current_user
from db.supabase import get_supabase
from models.auth import LoginRequest, MessageResponse, RegisterRequest, UserResponse

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    supabase=Depends(get_supabase),
):
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
    settings = get_settings()

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
    settings = get_settings()

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    response.set_cookie(
        key=settings.auth_cookie_name,
        value="",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=0,
    )

    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def me(
    supabase=Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    db_response = supabase.table("users").select("*").eq(
        "id", str(current_user.id)
    ).single().execute()

    if not db_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    user = db_response.data

    return UserResponse(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at"),
    )