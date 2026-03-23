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