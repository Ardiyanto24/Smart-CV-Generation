# cv-agent/backend/agents/cluster6/qc_combiner.py

"""
QC Combiner — Cluster 6

Pure logic function — tidak ada LLM call.
Menggabungkan output ATS Scoring Agent dan Semantic Reviewer Agent
menjadi QC Report (Context Package 5) yang dikirim ke Cluster 4.

Logika AND dengan toleransi asimetris (dari spec Section 6):
  ATS passed  DAN Semantic passed  → action_required: false
  ATS passed  DAN Semantic failed  → action_required: true
  ATS failed  DAN Semantic passed  → action_required: true
  ATS failed  DAN Semantic failed  → action_required: true
"""

import logging

logger = logging.getLogger("agents.cluster6.qc_combiner")


def combine_qc_results(
    ats_result: dict,
    semantic_results: list,
    cv_version: int,
    qc_iteration: int,
    settings,
) -> dict:
    """
    Merge ATS Scoring + Semantic Reviewer results into final QC Report.

    Pure logic — tidak ada LLM call, tidak ada DB call, tidak ada I/O.
    Semua I/O (DB insert) dilakukan oleh qc_evaluate node setelah fungsi ini.

    ATS status menggunakan global ATS score untuk semua sections karena
    ATS score dihitung secara global (satu score untuk seluruh CV), bukan
    per-section. Kalau overall ATS lolos threshold, semua sections pass ATS;
    kalau gagal, semua sections fail ATS.

    Args:
        ats_result: output dari run_ats_scoring — berisi weighted_score,
                    keywords_found, keywords_missed, section_analysis
        semantic_results: output dari run_semantic_review — list of per-section
                          review result dicts
        cv_version: nomor versi CV yang dievaluasi
        qc_iteration: iterasi QC saat ini (sudah di-increment oleh node)
        settings: Settings object dari config.get_settings() — dipakai untuk
                  threshold dan weight constants

    Returns:
        QC Report dict (Context Package 5) siap disimpan ke DB dan
        dikembalikan ke state["qc_report"]
    """
    ats_threshold = settings.ats_threshold
    semantic_threshold = settings.semantic_threshold
    weight_ats = settings.qc_combined_weight_ats
    weight_semantic = settings.qc_combined_weight_semantic

    global_ats_score = ats_result.get("weighted_score", 0.0)
    keywords_missed = ats_result.get("keywords_missed", [])

    # ATS status berlaku global untuk semua sections
    ats_passed_globally = global_ats_score >= ats_threshold
    ats_status_global = "passed" if ats_passed_globally else "failed"

    logger.info(
        f"[combine_qc_results] "
        f"global_ats_score={global_ats_score}, "
        f"ats_threshold={ats_threshold}, "
        f"ats_passed_globally={ats_passed_globally}, "
        f"semantic_threshold={semantic_threshold}"
    )

    # ── Build ATS section analysis lookup ────────────────────────────────────
    # Key: (section_name, entry_id) → ats section analysis dict
    # Dipakai untuk match preserve list ke setiap semantic section result
    ats_section_map: dict[tuple, dict] = {}
    for ats_section in ats_result.get("section_analysis", []):
        key = (ats_section.get("section"), ats_section.get("entry_id"))
        ats_section_map[key] = ats_section

    # ── Build combined sections ───────────────────────────────────────────────
    sections = []

    for sem_section in semantic_results:
        section_name = sem_section.get("section")
        entry_id = sem_section.get("entry_id")
        semantic_score = sem_section.get("semantic_score", 0)

        # Semantic status
        semantic_passed = semantic_score >= semantic_threshold
        semantic_status = "passed" if semantic_passed else "failed"

        # AND logic — action_required true kalau salah satu gagal
        action_required = not (ats_passed_globally and semantic_passed)

        # Preserve list dari ATS section analysis
        # Lookup by (section, entry_id) — fallback ke empty list kalau tidak ada
        ats_match = ats_section_map.get((section_name, entry_id), {})
        preserve = ats_match.get("preserve", [])

        # Revise list dari Semantic section result
        revise = sem_section.get("revise", [])

        # Missed keywords — global list, sama untuk semua sections
        # Dipakai oleh Revision Handler untuk keyword injection guidance
        missed_keywords = keywords_missed

        # Combined score untuk best version selection saat MAX_QC_ITERATIONS habis
        combined_score = round(
            (global_ats_score * weight_ats) + (semantic_score * weight_semantic),
            2,
        )

        sections.append({
            "section":          section_name,
            "entry_id":         entry_id,
            "ats_score":        global_ats_score,
            "ats_status":       ats_status_global,
            "semantic_score":   semantic_score,
            "semantic_status":  semantic_status,
            "action_required":  action_required,
            "preserve":         preserve,
            "revise":           revise,
            "missed_keywords":  missed_keywords,
            "combined_score":   combined_score,
        })

    # ── Compute aggregate stats ───────────────────────────────────────────────
    sections_passed = sum(1 for s in sections if not s["action_required"])
    sections_failed = sum(1 for s in sections if s["action_required"])

    logger.info(
        f"[combine_qc_results] "
        f"sections={len(sections)}, "
        f"passed={sections_passed}, failed={sections_failed}"
    )

    # ── Build QC Report — Context Package 5 ──────────────────────────────────
    # application_id tidak di-inject di sini — node yang menambahkannya
    # karena combine_qc_results tidak punya akses ke state
    qc_report = {
        "cv_version":       cv_version,
        "iteration":        qc_iteration,
        "overall_ats_score": global_ats_score,
        "sections":         sections,
        "sections_passed":  sections_passed,
        "sections_failed":  sections_failed,
    }

    return qc_report