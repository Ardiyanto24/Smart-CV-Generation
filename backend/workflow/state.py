# cv-agent/backend/workflow/state.py

from typing import Optional
from typing_extensions import TypedDict


class CVAgentState(TypedDict):
    """
    State object yang dibawa sepanjang seluruh LangGraph workflow.
    Setiap node membaca dari dan menulis ke state ini.

    LangGraph merge partial state updates secara otomatis —
    setiap node hanya perlu return dict berisi field yang berubah,
    bukan seluruh state.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    # Set sekali saat workflow dimulai, tidak pernah diubah
    user_id: str                            # UUID user yang sedang login
    application_id: str                     # UUID lamaran yang sedang diproses

    # ── Cluster 2 Output ──────────────────────────────────────────────────────
    # Diisi oleh node parse_jd_jr
    # Struktur: Context Package 2 (lihat system_architecture_guide Section 5)
    jd_jr_context: Optional[dict]

    # ── Cluster 3 Output ──────────────────────────────────────────────────────
    # gap_analysis_context diisi oleh node analyze_gap
    # Struktur: Context Package 3
    gap_analysis_context: Optional[dict]

    # gap_score diisi oleh node score_gap
    # Sub-object dari Package 3 yang berisi quantitative_score, verdict, dll
    gap_score: Optional[dict]

    # Diset oleh Interrupt 1 resume (POST /applications/{id}/resume)
    # True  → user klik "Lanjut Generate CV"
    # False → user klik "Kembali Update Profil" → workflow berakhir
    user_proceed: Optional[bool]

    # ── Cluster 4 Output ──────────────────────────────────────────────────────
    # Diisi oleh node plan_strategy (Planner Agent)
    # Berisi content_instructions, keyword_targets, narrative_instructions, dll
    strategy_brief: Optional[dict]

    # Diset oleh Interrupt 2 resume
    # True → user approve brief (mungkin dengan adjustment di Zona Kuning/Hijau)
    user_brief_approved: Optional[bool]

    # Diisi oleh node select_content (Selection Agent)
    # Struktur: Context Package 4
    selected_content_package: Optional[dict]

    # ── Cluster 5 Output ──────────────────────────────────────────────────────
    # Diisi oleh node generate_content, diupdate oleh revision nodes
    # Struktur: Final Structured Output JSON (lihat cluster5_specification Section 8)
    cv_output: Optional[dict]

    # Counter versi CV — dimulai dari 1, naik setiap siklus revisi
    # Default 1 (bukan None) karena langsung dipakai saat generate_content pertama kali
    cv_version: int

    # ── Cluster 6 Output ──────────────────────────────────────────────────────
    # Diisi oleh node qc_evaluate
    # Struktur: Context Package 5 (QC Report)
    qc_report: Optional[dict]

    # Counter iterasi QC — dimulai dari 0 sebelum QC pertama berjalan
    # Default 0 (bukan None) karena dipakai dalam kondisi edge check_qc_result
    qc_iteration: int

    # ── Revision Fields ───────────────────────────────────────────────────────
    # Diset oleh Revision Handler saat iterasi revisi dimulai
    # Nilai: "qc_driven" atau "user_driven"
    revision_type: Optional[str]

    # Diset oleh Interrupt 3 resume
    # Key: section identifier (e.g., "experience", "projects")
    # Value: "approved" atau "revision_requested"
    user_section_approvals: Optional[dict]

    # Diset oleh Interrupt 3 resume bersamaan dengan user_section_approvals
    # Key: section identifier
    # Value: free-text instruksi revisi dari user
    # Kosong ({}) untuk sections yang di-approve
    user_revision_instructions: Optional[dict]

    # ── Final Output ──────────────────────────────────────────────────────────
    # Diisi oleh node render_document setelah PDF/DOCX berhasil dibuat
    # Format: "{application_id}/cv_v{version}.pdf"
    final_output_path: Optional[str]