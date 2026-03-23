# cv-agent/backend/routers/profile.py

from fastapi import APIRouter, Depends, HTTPException

from db.auth import get_current_user
from db.supabase import get_supabase
from models.profile import (
    InferredSkillBatchRequest,
    InferredSkillSuggestion,
    SkillResponse,
)

router = APIRouter(
    prefix="/profile",
    tags=["profile"],
)

# ─── Valid Components ──────────────────────────────────────────────────────────
# Tujuh komponen Master Data yang valid
# Dipakai untuk memvalidasi path parameter {component} di semua dynamic routes

VALID_COMPONENTS = [
    "education",
    "experience",
    "projects",
    "awards",
    "organizations",
    "certificates",
    "skills",
]


# ─── Helper: Validate Component ───────────────────────────────────────────────
# Dipanggil di awal setiap route handler yang menerima {component}
# Mencegah user mengakses tabel yang tidak valid, misalnya:
# GET /profile/users → harus ditolak
# GET /profile/experience → valid

def validate_component(component: str) -> str:
    if component not in VALID_COMPONENTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid component '{component}'. "
                f"Must be one of: {', '.join(VALID_COMPONENTS)}"
            ),
        )
    return component


# ─── GET /profile/{component} ─────────────────────────────────────────────────
# Mengembalikan semua entries untuk satu komponen milik user yang sedang login
# Contoh: GET /profile/experience → semua experience entries user ini

@router.get("/{component}")
async def list_entries(
    component: str,
    current_user=Depends(get_current_user),
):
    """
    List all entries for a given Master Data component.
    Returns entries belonging to the authenticated user only,
    ordered by created_at descending (most recent first).
    """
    # Validasi component — raise 400 jika tidak valid
    validate_component(component)

    supabase = get_supabase()

    # Query tabel yang namanya sama dengan component
    # user_id filter memastikan user hanya bisa lihat data miliknya sendiri
    # (defence in depth — RLS di Supabase juga melindungi, tapi kita filter eksplisit)
    response = (
        supabase.table(component)
        .select("*")
        .eq("user_id", str(current_user.id))
        .order("created_at", desc=True)
        .execute()
    )

    # response.data adalah list of dicts — langsung return, FastAPI serialisasi otomatis
    return response.data