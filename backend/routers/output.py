# cv-agent/backend/routers/output.py

from fastapi import APIRouter, Depends, HTTPException, status

from db.auth import get_current_user
from db.supabase import get_supabase

router = APIRouter(
    prefix="/applications",
    tags=["output"],
)


# ─── Helper: Verify Application Ownership ─────────────────────────────────────
# Sama seperti di workflow.py dan applications.py — sengaja tidak di-share
# antar router karena routers tidak boleh saling import

async def verify_application_ownership(
    application_id: str,
    user_id: str,
) -> dict:
    """
    Verify that the given application exists and belongs to the user.
    Raises HTTP 404 if not found or not owned by the current user.
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


# ─── POST /applications/{id}/render ───────────────────────────────────────────
# Trigger Document Renderer untuk mengkonversi Final Structured Output JSON
# menjadi file PDF dan DOCX yang bisa didownload user
# Phase 4: stub — belum ada implementasi
# Phase 7: akan memanggil WeasyPrint (PDF) dan python-docx (DOCX)

@router.post("/{id}/render", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def render_document(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Trigger the Document Renderer to convert the Final Structured Output
    JSON into PDF and DOCX files, then upload to Supabase Storage.
    PHASE 4 STUB: Document renderer will be built in Phase 7.
    """
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    # TODO Phase 7: Trigger Document Renderer (WeasyPrint + python-docx)
    # 1. Fetch latest cv_outputs row for this application
    # 2. Call render_and_upload(cv_output, application_id, cv_version)
    # 3. Update cv_outputs status to "final"
    # 4. Return storage paths

    return {
        "status": "not_implemented",
        "message": "Document renderer will be wired in Phase 7",
    }


# ─── GET /applications/{id}/download ──────────────────────────────────────────
# Generate signed URL untuk download file PDF atau DOCX dari Supabase Storage
# Signed URL bersifat time-limited — expired setelah SIGNED_URL_EXPIRY_SECONDS
# Phase 4: stub — belum ada implementasi
# Phase 7: akan generate signed URL dari Supabase Storage

@router.get("/{id}/download", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def download_cv(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Generate a time-limited signed URL for downloading the rendered CV.
    Accepts optional query parameter 'format' (pdf or docx, default: pdf).
    PHASE 4 STUB: Download will be available after Phase 7.
    """
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    # TODO Phase 7: Generate Supabase Storage signed URL (SIGNED_URL_EXPIRY_SECONDS)
    # 1. Determine format from query param (pdf or docx)
    # 2. Construct storage path: {application_id}/cv_v{version}.{format}
    # 3. Call generate_signed_url(storage_path)
    # 4. Return {"url": signed_url, "format": format, "expires_in_seconds": N}

    return {
        "status": "not_implemented",
        "message": "Download will be available after Phase 7",
    }