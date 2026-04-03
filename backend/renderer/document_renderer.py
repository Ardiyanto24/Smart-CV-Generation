# cv-agent/backend/renderer/document_renderer.py

"""
Document Renderer Orchestrator — Document Renderer Layer

Mengkoordinasikan rendering PDF dan DOCX, upload ke Supabase Storage,
dan mengembalikan storage paths.

Satu fungsi publik:
- render_and_upload(cv_output, application_id, cv_version) -> dict
"""

import logging

from renderer.pdf_renderer import render_pdf
from renderer.docx_renderer import render_docx
from renderer.storage import upload_file

logger = logging.getLogger("renderer.document_renderer")

# MIME type DOCX — panjang tapi ini adalah string standar resmi
_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".wordprocessingml.document"
)


async def render_and_upload(
    cv_output: dict,
    application_id: str,
    cv_version: int,
) -> dict:
    """
    Render CV output ke PDF dan DOCX, lalu upload keduanya ke Supabase Storage.

    Urutan eksekusi:
    1. render_pdf  — hasilkan PDF bytes
    2. render_docx — hasilkan DOCX bytes
    3. upload PDF  — ke Supabase Storage
    4. upload DOCX — ke Supabase Storage

    Jika langkah 1 atau 2 gagal, RuntimeError di-raise dan tidak ada upload.
    Jika langkah 3 gagal, langkah 4 tidak dijalankan.

    Args:
        cv_output      : Final Structured Output dict dari Cluster 5
        application_id : UUID aplikasi — dipakai sebagai folder di Storage
        cv_version     : nomor versi CV — dipakai sebagai nama file

    Returns:
        dict dengan dua keys:
        {
            "pdf_path":  "{application_id}/cv_v{cv_version}.pdf",
            "docx_path": "{application_id}/cv_v{cv_version}.docx"
        }

    Raises:
        RuntimeError: jika render atau upload gagal
    """
    logger.info(
        f"[render_and_upload] starting for application_id={application_id}, "
        f"cv_version={cv_version}"
    )

    # ── Construct storage paths ───────────────────────────────────────────────
    # Format: {application_id}/cv_v{version}.ext
    # application_id sebagai folder memastikan file antar user tidak bentrok
    pdf_path = f"{application_id}/cv_v{cv_version}.pdf"
    docx_path = f"{application_id}/cv_v{cv_version}.docx"

    # ── Step 1: Render PDF ────────────────────────────────────────────────────
    # render_pdf adalah fungsi sync — WeasyPrint tidak async
    # Jika gagal, RuntimeError di-raise dan proses berhenti di sini
    try:
        logger.info("[render_and_upload] rendering PDF...")
        pdf_bytes = render_pdf(cv_output)
        logger.info(
            f"[render_and_upload] PDF rendered: {len(pdf_bytes)} bytes"
        )
    except Exception as e:
        logger.error(f"[render_and_upload] PDF render failed: {e}")
        raise RuntimeError(f"Document rendering failed: {e}") from e

    # ── Step 2: Render DOCX ───────────────────────────────────────────────────
    # render_docx adalah fungsi sync — python-docx tidak async
    # Jika gagal, RuntimeError di-raise dan tidak ada upload yang terjadi
    try:
        logger.info("[render_and_upload] rendering DOCX...")
        docx_bytes = render_docx(cv_output)
        logger.info(
            f"[render_and_upload] DOCX rendered: {len(docx_bytes)} bytes"
        )
    except Exception as e:
        logger.error(f"[render_and_upload] DOCX render failed: {e}")
        raise RuntimeError(f"Document rendering failed: {e}") from e

    # ── Step 3: Upload PDF ────────────────────────────────────────────────────
    # Upload hanya dimulai setelah kedua render berhasil
    # Jika upload PDF gagal, upload DOCX tidak dijalankan — konsistensi terjaga
    try:
        logger.info(f"[render_and_upload] uploading PDF to {pdf_path}...")
        upload_file(pdf_bytes, pdf_path, "application/pdf")
        logger.info(f"[render_and_upload] PDF uploaded: {pdf_path}")
    except Exception as e:
        logger.error(f"[render_and_upload] PDF upload failed: {e}")
        raise RuntimeError(f"Document rendering failed: {e}") from e

    # ── Step 4: Upload DOCX ───────────────────────────────────────────────────
    try:
        logger.info(f"[render_and_upload] uploading DOCX to {docx_path}...")
        upload_file(docx_bytes, docx_path, _DOCX_CONTENT_TYPE)
        logger.info(f"[render_and_upload] DOCX uploaded: {docx_path}")
    except Exception as e:
        logger.error(f"[render_and_upload] DOCX upload failed: {e}")
        raise RuntimeError(f"Document rendering failed: {e}") from e

    # ── Return storage paths ──────────────────────────────────────────────────
    logger.info(
        f"[render_and_upload] complete — "
        f"pdf={pdf_path}, docx={docx_path}"
    )

    return {
        "pdf_path": pdf_path,
        "docx_path": docx_path,
    }