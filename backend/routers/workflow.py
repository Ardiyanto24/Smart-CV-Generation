# cv-agent/backend/routers/workflow.py

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response, status

from db.auth import get_current_user
from db.limiter import limiter
from db.supabase import get_supabase
from models.application import JobPostingCreate
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
    tags=["workflow"],
)


# ─── Helper: Verify Application Ownership ─────────────────────────────────────
# Versi workflow router dari ownership check
# Sengaja tidak di-share dengan applications.py — routers tidak saling import
# Mengembalikan application row kalau valid, raise 404 kalau tidak

async def verify_application_ownership(
    application_id: str,
    user_id: str,
) -> dict:
    """
    Verify that the given application exists and belongs to the user.
    Raises HTTP 404 if not found or not owned by the current user.
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