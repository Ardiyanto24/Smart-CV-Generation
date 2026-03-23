# cv-agent/backend/routers/profile.py

from fastapi import APIRouter, Depends, HTTPException

from db.auth import get_current_user
from db.supabase import get_supabase
from models.profile import (
    InferredSkillBatchRequest,
    InferredSkillSuggestion,
    SkillResponse,
)

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, status

from datetime import datetime, timezone

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


@router.post("/{component}", status_code=status.HTTP_201_CREATED)
async def create_entry(
    component: str,
    data: Dict[str, Any] = Body(...),   # terima raw dict karena shape beda per komponen
    current_user=Depends(get_current_user),
):
    """
    Create a new entry for a given Master Data component.
    The user_id is always injected from the authenticated session —
    never trusted from the request body.
    """
    # Validasi component — raise 400 jika tidak valid
    validate_component(component)

    # Buang user_id dari request body kalau user iseng mengirimkannya
    # Ini mencegah user mengklaim ownership atas data milik user lain
    data.pop("user_id", None)

    # Inject user_id yang benar dari authenticated session
    data["user_id"] = str(current_user.id)

    supabase = get_supabase()

    # Insert ke tabel yang sesuai dengan component
    response = (
        supabase.table(component)
        .insert(data)
        .execute()
    )

    # TODO Phase 6: Trigger Profile Ingestion Agent after insert
    # Agent akan: (1) decompose what_i_did menjadi array atomic items
    #             (2) infer skills_used dari konteks entry
    #             (3) suggest standalone skills ke user untuk di-approve

    # response.data adalah list — ambil element pertama (row yang baru dibuat)
    return response.data[0]


@router.put("/{component}/{id}")
async def update_entry(
    component: str,
    id: str,
    data: Dict[str, Any] = Body(...),
    current_user=Depends(get_current_user),
):
    """
    Update an existing entry for a given Master Data component.
    Only fields present in the request body will be updated (partial update).
    Ownership is verified before update — users can only edit their own entries.
    """
    # Validasi component — raise 400 jika tidak valid
    validate_component(component)

    supabase = get_supabase()

    # Ownership check — cari entry dengan id DAN user_id yang cocok
    # Kalau tidak ketemu berarti: entry tidak ada, atau bukan milik user ini
    existing = (
        supabase.table(component)
        .select("id")
        .eq("id", id)
        .eq("user_id", str(current_user.id))
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )

    # Buang field-field yang tidak boleh diubah via endpoint ini
    # Meski user sengaja mengirimkan field ini, kita abaikan
    for protected_field in ["id", "user_id", "created_at", "is_inferred"]:
        data.pop(protected_field, None)

    # Set updated_at ke waktu sekarang (UTC)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Lakukan update — hanya row dengan id dan user_id yang cocok
    response = (
        supabase.table(component)
        .update(data)
        .eq("id", id)
        .eq("user_id", str(current_user.id))
        .execute()
    )

    # TODO Phase 6: Trigger Profile Ingestion Agent re-run after update
    # Agent akan: (1) re-decompose what_i_did yang baru
    #             (2) cek stale skills — skill lama yang tidak lagi relevan
    #             (3) suggest skills baru kalau ada

    return response.data[0]