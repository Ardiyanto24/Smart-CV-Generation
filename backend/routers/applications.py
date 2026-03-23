# cv-agent/backend/routers/applications.py

from fastapi import APIRouter, Depends, HTTPException, Response, status
from datetime import datetime, timezone

from db.auth import get_current_user
from db.supabase import get_supabase
from models.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStatusUpdate,
    JobPostingCreate,
    JobPostingResponse,
    JobDescriptionResponse,
    JobRequirementResponse,
)
from models.cv_output import (
    CVOutputResponse,
    CVStrategyBriefResponse,
    GapAnalysisFullResponse,
    GapAnalysisResultResponse,
    GapAnalysisScoreResponse,
    QCReportResponse,
    QCResultResponse,
)

router = APIRouter(
    prefix="/applications",
    tags=["applications"],
)


# ─── Helper: Verify Application Ownership ─────────────────────────────────────
# Dipanggil di awal setiap endpoint untuk memastikan application
# yang diminta memang milik user yang sedang login
# Mengembalikan application row kalau valid, raise 404 kalau tidak

async def verify_ownership(application_id: str, user_id: str) -> dict:
    """
    Verify that the given application exists and belongs to the user.
    Raises HTTP 404 if not found or not owned by the user.
    Returns the application row if valid.
    """
    supabase = get_supabase()

    response = (
        supabase.table("applications")
        .select("*")
        .eq("id", application_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    return response.data[0]


# ─── POST /applications ───────────────────────────────────────────────────────
# Membuat lamaran kerja baru
# Status selalu dimulai dari "draft" — tidak bisa diset oleh user saat create

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApplicationResponse)
async def create_application(
    data: ApplicationCreate,
    current_user=Depends(get_current_user),
):
    """
    Create a new job application.
    Status is always set to 'draft' on creation regardless of what user sends.
    user_id is injected from the authenticated session.
    """
    supabase = get_supabase()

    # Bangun payload — user_id dari session, status selalu "draft"
    payload = {
        "company_name": data.company_name,
        "position": data.position,
        "user_id": str(current_user.id),
        "status": "draft",              # selalu draft, tidak bisa dioverride user
    }

    response = (
        supabase.table("applications")
        .insert(payload)
        .execute()
    )

    return response.data[0]


# ─── GET /applications ────────────────────────────────────────────────────────
# Mengembalikan semua lamaran milik user yang sedang login
# Dipakai di dashboard untuk menampilkan list lamaran

@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    current_user=Depends(get_current_user),
):
    """
    Return all job applications belonging to the authenticated user.
    Ordered by created_at descending (most recent first).
    """
    supabase = get_supabase()

    response = (
        supabase.table("applications")
        .select("*")
        .eq("user_id", str(current_user.id))
        .order("created_at", desc=True)
        .execute()
    )

    return response.data


# ─── GET /applications/{id} ───────────────────────────────────────────────────
# Mengembalikan detail satu lamaran berdasarkan ID
# Dipakai ketika user membuka halaman detail lamaran

@router.get("/{id}", response_model=ApplicationResponse)
async def get_application(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Return full detail for a single job application.
    Raises HTTP 404 if not found or not owned by the current user.
    """
    # verify_ownership sudah handle: cek exist + cek ownership + return row
    application = await verify_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    return application


# ─── DELETE /applications/{id} ───────────────────────────────────────────────
# Menghapus satu lamaran beserta SELURUH data terkait
# ON DELETE CASCADE di DB memastikan semua child data ikut terhapus:
# job_postings, job_requirements, job_descriptions, gap_analysis_results,
# gap_analysis_scores, cv_strategy_briefs, selected_content_packages,
# revision_history, cv_outputs, qc_results, qc_overall_scores

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Delete a job application and all its related data.
    ON DELETE CASCADE handles cleanup of all child tables automatically.
    Returns HTTP 204 with no response body on success.
    """
    # Ownership check — raise 404 kalau tidak ada atau bukan milik user ini
    await verify_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()

    # Satu delete ini akan cascade ke 11 tabel child secara otomatis
    supabase.table("applications").delete().eq("id", id).execute()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── PATCH /applications/{id}/status ─────────────────────────────────────────
# Mengubah status lamaran — untuk tracking progress di dunia nyata
# Contoh: draft → applied → interview → offer → accepted/rejected

@router.patch("/{id}/status", response_model=ApplicationResponse)
async def update_application_status(
    id: str,
    data: ApplicationStatusUpdate,
    current_user=Depends(get_current_user),
):
    """
    Update the status of a job application.
    Only the status field and updated_at timestamp are changed.
    Valid status values: draft, applied, interview, offer, rejected, accepted.
    """
    # Ownership check — raise 404 kalau tidak ada atau bukan milik user ini
    await verify_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()

    # Update hanya status dan updated_at — tidak ada field lain yang berubah
    response = (
        supabase.table("applications")
        .update({
            "status": data.status.value,    # .value karena ApplicationStatus adalah Enum
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", id)
        .execute()
    )

    return response.data[0]