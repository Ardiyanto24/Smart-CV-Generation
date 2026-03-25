# cv-agent/backend/routers/profile.py

from fastapi import APIRouter, Depends, HTTPException

from db.auth import get_current_user
from db.supabase import get_supabase
from models.profile import (
    InferredSkillBatchRequest,
    InferredSkillSuggestion,
    SkillResponse,
)

from agents.cluster1.profile_ingestion import (
    check_stale_skills,
    run_stage1,
    run_stage2,
)

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, status, Response

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



@router.get("/inferred-skills", response_model=list[SkillResponse])
async def get_inferred_skills(
    current_user=Depends(get_current_user),
):
    """
    Return all agent-inferred skill suggestions pending user decision.
    These are skills the Profile Ingestion Agent detected from profile entries
    but has not yet been approved or rejected by the user.
    """
    supabase = get_supabase()

    response = (
        supabase.table("skills")
        .select("*")
        .eq("user_id", str(current_user.id))
        .eq("is_inferred", True)
        .order("created_at", desc=True)
        .execute()
    )

    return response.data


# ─── POST /profile/inferred-skills/batch ─────────────────────────────────────
# Memproses keputusan user atas skill suggestions secara batch
# approved → insert ke DB dengan is_inferred=true
# rejected → buang begitu saja, tidak disimpan ke DB

@router.post("/inferred-skills/batch")
async def batch_process_inferred_skills(
    batch: InferredSkillBatchRequest,
    current_user=Depends(get_current_user),
):
    """
    Process a batch of skill suggestions — approve some, reject others.
    Approved skills are inserted into the skills table.
    Rejected skills are simply discarded (not saved to DB).
    Duplicate skills (case-insensitive) are silently skipped.
    """
    supabase = get_supabase()

    # Ambil semua skills user yang sudah ada untuk duplicate check
    existing_response = (
        supabase.table("skills")
        .select("name")
        .eq("user_id", str(current_user.id))
        .execute()
    )

    # Buat set nama skills yang sudah ada — lowercase untuk case-insensitive comparison
    existing_names = {
        row["name"].lower()
        for row in existing_response.data
    }

    approved_count = 0

    for skill in batch.approved:
        # Skip kalau nama skill sudah ada (case-insensitive)
        if skill.name.lower() in existing_names:
            continue

        # Insert skill baru ke DB
        supabase.table("skills").insert({
            "user_id": str(current_user.id),
            "name": skill.name,
            "category": skill.category.value,  # .value karena category adalah Enum
            "source": skill.source,
            "is_inferred": True,
        }).execute()

        # Tambahkan ke existing_names untuk mencegah duplikat
        # dalam batch yang sama (kalau user kirim dua skill dengan nama sama)
        existing_names.add(skill.name.lower())
        approved_count += 1

    return {
        "approved_count": approved_count,
        "rejected_count": len(batch.rejected),
    }


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
    data: Dict[str, Any] = Body(...),
    current_user=Depends(get_current_user),
):
    """
    Create a new entry for a given Master Data component.
    After insert, Profile Ingestion Agent runs Stage 1 (decompose) and
    Stage 2 (infer standalone skills). Skill suggestions are returned
    in the response for user to approve or reject.
    """
    validate_component(component)

    # Buang user_id dari request body kalau dikirim — security measure
    data.pop("user_id", None)
    data["user_id"] = str(current_user.id)

    supabase = get_supabase()

    # ── Insert raw entry ke DB ────────────────────────────────────────────────
    response = (
        supabase.table(component)
        .insert(data)
        .execute()
    )

    inserted_row = response.data[0]
    entry_id = inserted_row["id"]

    # ── Stage 1: Dekomposisi + inferensi contextual skills ────────────────────
    # Memecah what_i_did, challenge, impact menjadi atomic arrays
    # Mengupdate DB row secara langsung — tidak perlu konfirmasi user
    decomposed_entry = await run_stage1(
        component=component,
        entry=inserted_row,
        entry_id=entry_id,
    )

    # ── Stage 2: Inferensi standalone skills ──────────────────────────────────
    # Skills yang tidak eksplisit tapi bisa disimpulkan dari konteks
    # TIDAK langsung ke DB — dikembalikan sebagai suggestion untuk user
    skill_suggestions = await run_stage2(
        component=component,
        entry_id=entry_id,
        entry=decomposed_entry,
        user_id=str(current_user.id),
    )

    # ── Build response ────────────────────────────────────────────────────────
    # Fetch updated row dari DB — setelah Stage 1 mengupdate arrays
    updated_response = (
        supabase.table(component)
        .select("*")
        .eq("id", entry_id)
        .execute()
    )
    updated_row = updated_response.data[0]

    # skill_suggestions hanya disertakan kalau ada isinya
    # Frontend cek keberadaan key ini untuk menampilkan suggestion panel
    if skill_suggestions:
        updated_row["skill_suggestions"] = skill_suggestions

    return updated_row


@router.put("/{component}/{id}")
async def update_entry(
    component: str,
    id: str,
    data: Dict[str, Any] = Body(...),
    current_user=Depends(get_current_user),
):
    """
    Update an existing entry for a given Master Data component.
    After update, Profile Ingestion Agent re-runs Stage 1 (re-decompose),
    checks for stale skills, and runs Stage 2 (new suggestions).
    """
    validate_component(component)

    supabase = get_supabase()

    # ── Ownership check ───────────────────────────────────────────────────────
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

    # Buang protected fields
    for protected_field in ["id", "user_id", "created_at", "is_inferred"]:
        data.pop(protected_field, None)

    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    # ── Update DB ─────────────────────────────────────────────────────────────
    response = (
        supabase.table(component)
        .update(data)
        .eq("id", id)
        .eq("user_id", str(current_user.id))
        .execute()
    )

    updated_row = response.data[0]

    # ── Stage 1: Re-dekomposisi entry yang baru di-update ─────────────────────
    # Entry sudah berubah — perlu dekomposisi ulang untuk menghasilkan
    # arrays yang akurat berdasarkan konten terbaru
    decomposed_entry = await run_stage1(
        component=component,
        entry=updated_row,
        entry_id=id,
    )

    # ── Stale skill check ─────────────────────────────────────────────────────
    # Cek apakah ada skills lama yang diinfer dari entry ini
    # yang tidak lagi relevan setelah konten berubah
    # new_skills_used adalah hasil Stage 1 yang baru
    stale_skill_names = await check_stale_skills(
        component=component,
        entry_id=id,
        user_id=str(current_user.id),
        new_skills_used=decomposed_entry.get("skills_used", []),
    )

    # ── Stage 2: Inferensi skills baru dari konten yang sudah diupdate ────────
    new_skill_suggestions = await run_stage2(
        component=component,
        entry_id=id,
        entry=decomposed_entry,
        user_id=str(current_user.id),
    )

    # ── Fetch updated row dari DB ─────────────────────────────────────────────
    final_response = (
        supabase.table(component)
        .select("*")
        .eq("id", id)
        .execute()
    )
    final_row = final_response.data[0]

    # ── Build response ────────────────────────────────────────────────────────
    # Kedua field opsional — hanya disertakan kalau ada isinya
    if new_skill_suggestions:
        final_row["skill_suggestions"] = new_skill_suggestions

    if stale_skill_names:
        final_row["stale_skills"] = stale_skill_names

    return final_row


@router.delete("/{component}/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    component: str,
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Delete an existing entry for a given Master Data component.
    No agent is triggered — this is a direct DB operation.
    Returns HTTP 204 with no response body on success.
    """
    # Validasi component — raise 400 jika tidak valid
    validate_component(component)

    supabase = get_supabase()

    # Ownership check — pastikan entry ada dan milik user ini
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

    # Hapus entry dari DB
    supabase.table(component).delete().eq("id", id).execute()

    # HTTP 204 — tidak ada response body
    return Response(status_code=status.HTTP_204_NO_CONTENT)