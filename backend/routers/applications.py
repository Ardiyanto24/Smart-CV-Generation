# cv-agent/backend/routers/applications.py

from fastapi import APIRouter, Depends, HTTPException, status

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
