# cv-agent/backend/renderer/storage.py

"""
Supabase Storage helper untuk Document Renderer.

Dua fungsi:
- upload_file        : upload PDF/DOCX bytes ke Supabase Storage
- generate_signed_url: buat time-limited download URL
"""

import logging

from config import get_settings
from db.supabase import get_supabase

logger = logging.getLogger("renderer.storage")


def upload_file(file_bytes: bytes, storage_path: str, content_type: str) -> str:
    """
    Upload file bytes ke Supabase Storage bucket cv-outputs.

    Args:
        file_bytes   : raw bytes hasil render (PDF atau DOCX)
        storage_path : path di bucket, format: {application_id}/cv_v{version}.pdf
        content_type : MIME type — "application/pdf" atau
                       "application/vnd.openxmlformats-officedocument
                       .wordprocessingml.document"

    Returns:
        storage_path string jika upload berhasil

    Raises:
        RuntimeError jika upload gagal
    """
    settings = get_settings()
    supabase = get_supabase()
    bucket = settings.cv_storage_bucket

    logger.info(
        f"[upload_file] uploading to bucket={bucket}, "
        f"path={storage_path}, content_type={content_type}, "
        f"size={len(file_bytes)} bytes"
    )

    # upsert=True — timpa file lama jika sudah ada di path yang sama
    # Ini penting untuk re-render: versi baru tidak gagal karena file lama masih ada
    response = (
        supabase.storage
        .from_(bucket)
        .upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    )

    # Supabase Storage client tidak selalu raise exception saat error —
    # response bisa berisi error object. Kita cek secara eksplisit.
    if hasattr(response, "error") and response.error:
        raise RuntimeError(
            f"[upload_file] upload gagal untuk path={storage_path}: "
            f"{response.error}"
        )

    logger.info(f"[upload_file] upload berhasil: {storage_path}")
    return storage_path


def generate_signed_url(storage_path: str) -> str:
    """
    Generate time-limited signed URL untuk download file dari Supabase Storage.

    Expiry diambil dari settings.signed_url_expiry_seconds (default 3600 = 1 jam).
    Setelah expired, URL tidak bisa dipakai lagi — user harus request URL baru
    via GET /applications/{id}/download.

    Args:
        storage_path: path di bucket, format: {application_id}/cv_v{version}.pdf

    Returns:
        signed URL string yang bisa langsung diakses browser untuk download

    Raises:
        RuntimeError jika URL generation gagal
    """
    settings = get_settings()
    supabase = get_supabase()
    bucket = settings.cv_storage_bucket
    expiry = settings.signed_url_expiry_seconds

    logger.info(
        f"[generate_signed_url] generating URL for path={storage_path}, "
        f"expiry={expiry}s"
    )

    response = (
        supabase.storage
        .from_(bucket)
        .create_signed_url(path=storage_path, expires_in=expiry)
    )

    # Response berisi dict dengan key "signedURL" jika berhasil
    # atau "error" jika gagal
    if "error" in response and response["error"]:
        raise RuntimeError(
            f"[generate_signed_url] gagal generate URL untuk "
            f"path={storage_path}: {response['error']}"
        )

    signed_url = response.get("signedURL") or response.get("signedUrl")

    if not signed_url:
        raise RuntimeError(
            f"[generate_signed_url] response tidak mengandung signed URL "
            f"untuk path={storage_path}. Response: {response}"
        )

    logger.info(f"[generate_signed_url] URL berhasil dibuat untuk {storage_path}")
    return signed_url