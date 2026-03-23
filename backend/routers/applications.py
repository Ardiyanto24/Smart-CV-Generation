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