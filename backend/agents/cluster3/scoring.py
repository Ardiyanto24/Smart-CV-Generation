# cv-agent/backend/agents/cluster3/scoring.py

"""
Scoring Agent — Cluster 3

Menghitung skor kesesuaian kandidat dalam dua bagian:
  Part 1: Kalkulasi kuantitatif deterministik (tanpa LLM)
  Part 2: Penilaian kualitatif LLM as a Judge

Output disimpan ke gap_analysis_scores table.

Prompts dikelola di: agents/prompts/scoring_prompt.py
"""

import json
import logging

from agents.llm_client import call_llm
from agents.prompts.scoring_prompt import SCORING_SYSTEM
from db.supabase import get_supabase

logger = logging.getLogger("agents.cluster3.scoring")


def _calculate_quantitative_score(gap_results: list) -> tuple[float, str, str]:
    """
    Part 1 — Kalkulasi skor kuantitatif secara deterministik.

    Formula dari spec:
        score = ((exact_match × 1.0) + (implicit_match × 0.7)) / total_items × 100

    Mapping verdict:
        75-100 → sangat_cocok
        50-74  → cukup_cocok
        0-49   → kurang_cocok

    Mapping proceed_recommendation:
        sangat_cocok / cukup_cocok → lanjut
        kurang_cocok               → tinjau

    Args:
        gap_results: list of gap analysis result objects dari run_gap_analyzer

    Returns:
        tuple of (quantitative_score, verdict, proceed_recommendation)
    """
    total_items = len(gap_results)

    if total_items == 0:
        # Edge case: tidak ada items — skor 0, workflow tetap bisa lanjut
        logger.warning("[_calculate_quantitative_score] gap_results is empty")
        return 0.0, "kurang_cocok", "tinjau"

    # Hitung weighted matches
    # exact_match  : bobot 1.0 — bukti eksplisit, confidence penuh
    # implicit_match: bobot 0.7 — transferable, confidence lebih rendah
    # gap          : bobot 0.0 — tidak ada bukti
    exact_count = sum(1 for r in gap_results if r.get("category") == "exact_match")
    implicit_count = sum(1 for r in gap_results if r.get("category") == "implicit_match")

    weighted_sum = (exact_count * 1.0) + (implicit_count * 0.7)
    quantitative_score = round((weighted_sum / total_items) * 100, 2)

    # Map score ke verdict
    if quantitative_score >= 75:
        verdict = "sangat_cocok"
    elif quantitative_score >= 50:
        verdict = "cukup_cocok"
    else:
        verdict = "kurang_cocok"

    # Map verdict ke proceed_recommendation
    # Ini adalah hard business rule — tidak bisa di-override oleh LLM
    if verdict in ("sangat_cocok", "cukup_cocok"):
        proceed_recommendation = "lanjut"
    else:
        proceed_recommendation = "tinjau"

    logger.info(
        f"[_calculate_quantitative_score] "
        f"total={total_items}, exact={exact_count}, implicit={implicit_count}, "
        f"score={quantitative_score}, verdict={verdict}, "
        f"proceed={proceed_recommendation}"
    )

    return quantitative_score, verdict, proceed_recommendation


async def run_scoring(application_id: str, gap_results: list) -> dict:
    """
    Calculate fit score combining deterministic quantitative calculation
    and LLM qualitative assessment.

    Part 1 (no LLM): formula matematika → skor 0-100, verdict, proceed
    Part 2 (LLM as Judge): interpretasi gap results → strength, concern, recommendation

    Hasil digabungkan dan disimpan ke gap_analysis_scores table.

    Args:
        application_id: UUID of the application being scored
        gap_results: list dari run_gap_analyzer output

    Returns:
        dict berisi quantitative score + qualitative assessment:
        {
            "quantitative_score": float,
            "verdict": str,
            "strength": str,
            "concern": str,
            "recommendation": str,
            "proceed_recommendation": str
        }
    """
    logger.info(
        f"[run_scoring] scoring application_id={application_id}, "
        f"gap_results_count={len(gap_results)}"
    )

    # ── Part 1: Kalkulasi kuantitatif — tanpa LLM ─────────────────────────────
    # Deterministik — hasil selalu sama untuk input yang sama
    quantitative_score, verdict, proceed_recommendation = (
        _calculate_quantitative_score(gap_results)
    )

    # ── Part 2: Penilaian kualitatif — LLM as a Judge ─────────────────────────
    # LLM membaca seluruh gap_results dan menghasilkan narasi interpretatif
    # Tidak mengubah skor kuantitatif — hanya menambahkan konteks kualitatif
    # System prompt dikelola di agents/prompts/scoring_prompt.py
    user_prompt = f"""Review this gap analysis and provide your qualitative assessment.

Quantitative score already calculated: {quantitative_score}/100 ({verdict})

Gap analysis results ({len(gap_results)} items):
{json.dumps(gap_results, ensure_ascii=False, indent=2)}

Provide strength, concern, and recommendation based on these results."""

    raw_response = await call_llm(
        system_prompt=SCORING_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=600,
    )

    # ── Parse qualitative assessment ──────────────────────────────────────────
    # JSONDecodeError di-raise sebagai ValueError agar with_retry bisa retry
    try:
        qualitative = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[run_scoring] LLM returned unparseable JSON for "
            f"application_id={application_id}. Raw: {raw_response[:500]}"
        )
        raise ValueError(
            f"Scoring Agent returned invalid JSON for "
            f"application_id={application_id}: {e}"
        )

    # Validasi fields yang diharapkan ada
    for field in ["strength", "concern", "recommendation"]:
        if field not in qualitative:
            logger.warning(
                f"[run_scoring] missing field '{field}' in qualitative response, "
                f"using fallback"
            )
            qualitative[field] = None

    # ── Gabungkan quantitative + qualitative ──────────────────────────────────
    # Satu dict yang berisi hasil kedua bagian
    scoring_result = {
        "quantitative_score": quantitative_score,
        "verdict": verdict,
        "strength": qualitative.get("strength"),
        "concern": qualitative.get("concern"),
        "recommendation": qualitative.get("recommendation"),
        "proceed_recommendation": proceed_recommendation,
    }

    # ── Simpan ke gap_analysis_scores table ───────────────────────────────────
    # Satu row per application — relasi one-to-one dengan applications table
    # Dibutuhkan oleh GET /applications/{id}/gap endpoint
    supabase = get_supabase()
    supabase.table("gap_analysis_scores").insert({
        "application_id": application_id,
        "quantitative_score": scoring_result["quantitative_score"],
        "verdict": scoring_result["verdict"],
        "strength": scoring_result["strength"],
        "concern": scoring_result["concern"],
        "recommendation": scoring_result["recommendation"],
        "proceed_recommendation": scoring_result["proceed_recommendation"],
    }).execute()

    logger.info(
        f"[run_scoring] scoring complete and saved — "
        f"score={quantitative_score}, verdict={verdict}, "
        f"proceed={proceed_recommendation}"
    )

    return scoring_result