# cv-agent/backend/routers/output.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from config import get_settings
from db.auth import get_current_user
from db.supabase import get_supabase

logger = logging.getLogger("routers.output")

router = APIRouter(
    prefix="/applications",
    tags=["output"],
)


# ── Helper: Verify Application Ownership ──────────────────────────────────────
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


# ── POST /applications/{id}/render ────────────────────────────────────────────

@router.post("/{id}/render", status_code=status.HTTP_200_OK)
async def render_document(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Manually trigger Document Renderer for the latest approved CV output.

    Queries cv_outputs for the highest version with status 'user_approved'
    or 'final', renders to PDF and DOCX, uploads to Supabase Storage,
    and updates status to 'final'.
    """
    from renderer.document_renderer import render_and_upload

    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()

    # ── Query cv_outputs — versi tertinggi yang sudah approved ────────────────
    response = (
        supabase.table("cv_outputs")
        .select("version, content, status")
        .eq("application_id", id)
        .in_("status", ["user_approved", "final"])
        .order("version", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No approved CV output found for this application. "
                "Complete the review workflow before rendering."
            ),
        )

    cv_row = response.data[0]
    cv_version = cv_row["version"]
    cv_content = cv_row["content"]

    logger.info(
        f"[render_document] triggering render for application_id={id}, "
        f"cv_version={cv_version}"
    )

    # ── Render PDF + DOCX dan upload ke Supabase Storage ─────────────────────
    try:
        result = await render_and_upload(
            cv_output=cv_content,
            application_id=id,
            cv_version=cv_version,
        )
    except RuntimeError as e:
        logger.error(
            f"[render_document] rendering failed for application_id={id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    pdf_path = result["pdf_path"]
    docx_path = result["docx_path"]

    # ── Update status cv_outputs ke "final" ───────────────────────────────────
    supabase.table("cv_outputs").update({
        "status": "final",
    }).eq("application_id", id).eq("version", cv_version).execute()

    logger.info(
        f"[render_document] render complete — "
        f"pdf={pdf_path}, docx={docx_path}"
    )

    return {
        "pdf_path": pdf_path,
        "docx_path": docx_path,
        "message": "CV rendered successfully",
    }


# ── GET /applications/{id}/download ───────────────────────────────────────────

@router.get("/{id}/download", status_code=status.HTTP_200_OK)
async def download_cv(
    id: str,
    format: str = Query(default="pdf", pattern="^(pdf|docx)$"),
    current_user=Depends(get_current_user),
):
    """
    Generate a time-limited signed URL for downloading the rendered CV.

    Query parameter:
        format: "pdf" (default) or "docx"

    Returns signed URL valid for SIGNED_URL_EXPIRY_SECONDS (default 3600s = 1 hour).
    """
    from renderer.storage import generate_signed_url

    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()
    settings = get_settings()

    # ── Query cv_outputs — versi final terbaru ────────────────────────────────
    # Hanya row dengan status "final" yang sudah punya file di Storage
    response = (
        supabase.table("cv_outputs")
        .select("version")
        .eq("application_id", id)
        .eq("status", "final")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No rendered CV found. Please trigger rendering first "
                "via POST /applications/{id}/render."
            ),
        )

    cv_version = response.data[0]["version"]

    # ── Konstruksi storage path berdasarkan format ────────────────────────────
    # Path deterministic: {application_id}/cv_v{version}.{format}
    # Konsisten dengan path yang dibuat oleh render_and_upload di storage.py
    storage_path = f"{id}/cv_v{cv_version}.{format}"

    logger.info(
        f"[download_cv] generating signed URL for "
        f"application_id={id}, format={format}, path={storage_path}"
    )

    # ── Generate signed URL ───────────────────────────────────────────────────
    # generate_signed_url raise RuntimeError jika path tidak ada di Storage
    # atau jika Supabase Storage API gagal
    try:
        signed_url = generate_signed_url(storage_path)
    except RuntimeError as e:
        logger.error(
            f"[download_cv] failed to generate signed URL for "
            f"path={storage_path}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    logger.info(
        f"[download_cv] signed URL generated for path={storage_path}, "
        f"expires_in={settings.signed_url_expiry_seconds}s"
    )

    return {
        "url": signed_url,
        "format": format,
        "expires_in_seconds": settings.signed_url_expiry_seconds,
    }