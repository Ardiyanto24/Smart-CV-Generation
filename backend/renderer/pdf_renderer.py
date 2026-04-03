# cv-agent/backend/renderer/pdf_renderer.py

"""
PDF Renderer — Document Renderer Layer

Mengkonversi Final Structured Output JSON menjadi PDF bytes
menggunakan Jinja2 (template engine) + WeasyPrint (HTML-to-PDF).

Satu fungsi publik:
- render_pdf(cv_output) -> bytes
"""

import logging
from pathlib import Path

import jinja2
import weasyprint

logger = logging.getLogger("renderer.pdf_renderer")

# ── Template directory ────────────────────────────────────────────────────────
# Path absolut dihitung dari lokasi file ini, bukan dari working directory.
# Ini memastikan template ditemukan tidak peduli dari mana uvicorn dijalankan.
_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_jinja_env() -> jinja2.Environment:
    """
    Buat Jinja2 Environment dengan FileSystemLoader ke direktori templates.

    Environment di-instantiate setiap render_pdf dipanggil — ringan karena
    belum load template apapun. Template baru di-load saat .get_template()
    dipanggil dan di-cache otomatis oleh Jinja2.
    """
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=False,  # CV content tidak perlu HTML escaping
    )


def render_pdf(cv_output: dict) -> bytes:
    """
    Render Final Structured Output JSON menjadi PDF bytes.

    Args:
        cv_output: Final Structured Output dict dari Cluster 5.
                   Dipass ke template sebagai variabel 'cv'.

    Returns:
        Raw PDF bytes — siap di-upload ke Supabase Storage atau ditulis ke disk.

    Raises:
        FileNotFoundError: jika cv_template.html tidak ditemukan di templates dir
        Exception        : WeasyPrint errors dibiarkan propagate ke orchestrator
    """
    logger.info("[render_pdf] starting PDF render")

    # ── Load template ─────────────────────────────────────────────────────────
    env = _get_jinja_env()

    try:
        template = env.get_template("cv_template.html")
    except jinja2.TemplateNotFound:
        raise FileNotFoundError(
            f"Template 'cv_template.html' tidak ditemukan di: {_TEMPLATES_DIR}. "
            f"Pastikan file ada di renderer/templates/cv_template.html"
        )

    # ── Render HTML ───────────────────────────────────────────────────────────
    # cv_output di-pass sebagai variabel 'cv' sesuai konvensi di template:
    # {{ cv.header.name }}, {{ cv.experience }}, dst.
    html_string = template.render(cv=cv_output)

    logger.debug(
        f"[render_pdf] HTML rendered, length={len(html_string)} chars"
    )

    # ── Convert HTML → PDF bytes ──────────────────────────────────────────────
    # WeasyPrint menerima HTML string dan menghasilkan PDF bytes.
    # base_url di-set ke templates dir agar WeasyPrint bisa resolve
    # asset relatif (font, gambar) jika ada di masa depan.
    # WeasyPrint errors dibiarkan propagate — orchestrator yang handle.
    pdf_bytes = weasyprint.HTML(
        string=html_string,
        base_url=str(_TEMPLATES_DIR),
    ).write_pdf()

    logger.info(
        f"[render_pdf] PDF render complete, size={len(pdf_bytes)} bytes"
    )

    return pdf_bytes
