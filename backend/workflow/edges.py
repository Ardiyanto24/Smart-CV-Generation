# cv-agent/backend/workflow/edges.py

"""
Conditional edge functions untuk LangGraph CV Agent workflow.

Setiap fungsi menerima CVAgentState dan mengembalikan string nama node berikutnya.
Edge functions adalah pure logic — tidak ada DB calls, tidak ada LLM calls.
Hanya membaca state dan memutuskan routing berdasarkan kondisi.

Tiga conditional edges dalam sistem:
1. after_gap_review    — setelah Interrupt 1, routing berdasarkan user_proceed
2. check_qc_result     — setelah qc_evaluate, routing berdasarkan QC results
3. after_cv_review     — setelah Interrupt 3, routing berdasarkan user approvals
"""

from langgraph.graph import END

from config import get_settings
from workflow.state import CVAgentState


def after_gap_review(state: CVAgentState) -> str:
    """
    Conditional edge — dipanggil setelah Interrupt 1 (user_gap_review).

    User sudah melihat gap analysis report dan memutuskan:
    - "Lanjut Generate CV" → user_proceed = True → lanjut ke plan_strategy
    - "Kembali Update Profil" → user_proceed = False → workflow berakhir

    Returns:
        "plan_strategy" jika user_proceed = True
        END             jika user_proceed = False (workflow terminate)
    """
    user_proceed = state.get("user_proceed", False)

    if user_proceed:
        # User memilih lanjut — mulai planning phase (Cluster 4)
        return "plan_strategy"
    else:
        # User memilih kembali update profil
        # END adalah LangGraph constant yang menghentikan workflow
        # State tetap tersimpan di checkpoint — user bisa start workflow baru
        # setelah update profil di Cluster 1
        return END


def check_qc_result(state: CVAgentState) -> str:
    """
    Conditional edge — dipanggil setelah qc_evaluate selesai.

    Menentukan apakah perlu revisi, pilih best version, atau lanjut ke user review.

    Logic (tiga kemungkinan):
    1. Ada section gagal DAN masih ada iterasi tersisa → revise_content (Jalur A)
    2. Ada section gagal DAN iterasi habis → select_best_version
    3. Semua section passed → user_cv_review (Interrupt 3)

    Returns:
        "revise_content"      jika ada yang gagal dan iterasi < MAX
        "select_best_version" jika ada yang gagal dan iterasi >= MAX
        "user_cv_review"      jika semua passed
    """
    settings = get_settings()
    max_iterations = settings.max_qc_iterations

    qc_report = state.get("qc_report", {})
    sections = qc_report.get("sections", [])
    qc_iteration = state.get("qc_iteration", 0)

    # Cek apakah ada section yang masih butuh revisi
    # any() return True kalau minimal satu section punya action_required=True
    has_failed_sections = any(
        section.get("action_required", False)
        for section in sections
    )

    if has_failed_sections and qc_iteration < max_iterations:
        # Masih ada yang gagal DAN masih ada iterasi tersisa
        # → kirim ke revise_content untuk diperbaiki
        return "revise_content"

    elif has_failed_sections and qc_iteration >= max_iterations:
        # Masih ada yang gagal TAPI iterasi sudah habis
        # → daripada pakai versi terakhir, pilih versi terbaik dari semua iterasi
        return "select_best_version"

    else:
        # Semua section passed QC
        # → lanjut ke Interrupt 3 untuk user review
        return "user_cv_review"


def after_cv_review(state: CVAgentState) -> str:
    """
    Conditional edge — dipanggil setelah Interrupt 3 (user_cv_review).

    User sudah mereview CV section per section dan memberikan verdict:
    - Semua section "approved" → render_document (workflow selesai)
    - Ada section "revision_requested" → apply_user_revisions (Jalur B)

    Returns:
        "render_document"      jika semua section approved
        "apply_user_revisions" jika ada section yang minta revisi
    """
    approvals = state.get("user_section_approvals", {})

    # all() return True kalau SEMUA nilai adalah "approved"
    # all() pada empty dict juga return True — edge case yang aman
    # karena kalau tidak ada approvals, kita anggap semua selesai
    all_approved = all(
        value == "approved"
        for value in approvals.values()
    )

    if all_approved:
        # Semua section diapprove user → render CV ke PDF/DOCX
        return "render_document"
    else:
        # Ada section yang minta revisi → Jalur B user-driven revision
        # user_revision_instructions sudah diisi di state oleh Interrupt 3 resume
        return "apply_user_revisions"