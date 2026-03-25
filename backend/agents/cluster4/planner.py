# cv-agent/backend/agents/cluster4/planner.py

"""
Planner Agent — Cluster 4

Menghasilkan CV Strategy Brief berdasarkan gap analysis dan JD/JR context.
Brief adalah "kontrak" yang mengatur seluruh CV generation downstream.

Output disimpan ke cv_strategy_briefs table dengan user_approved=false.
User akan review dan approve brief di Interrupt 2.

Prompts dikelola di: agents/prompts/planner_prompt.py
"""

import json
import logging

from agents.llm_client import call_llm
from agents.prompts.planner_prompt import PLANNER_SYSTEM
from config import get_settings
from db.supabase import get_supabase

logger = logging.getLogger("agents.cluster4.planner")


async def run_planner(
    application_id: str,
    gap_analysis_context: dict,
    jd_jr_context: dict,
) -> dict:
    """
    Generate CV Strategy Brief from gap analysis and JD/JR context.

    Brief terdiri dari tiga zona editabilitas:
    - Zona Merah  : content_instructions (entry UUIDs + top_n per component)
    - Zona Kuning : keyword_targets + narrative_instructions
    - Zona Hijau  : primary_angle + summary_hook_direction + tone

    Saves brief to cv_strategy_briefs table with user_approved=false.
    Returns brief dict including generated brief_id from DB.

    Args:
        application_id: UUID of the application being processed
        gap_analysis_context: Context Package 3 — output dari Gap Analyzer
        jd_jr_context: Context Package 2 — output dari Parser Agent

    Returns:
        dict berisi seluruh brief fields + "brief_id" (UUID dari DB)
    """
    logger.info(f"[run_planner] generating strategy brief for application_id={application_id}")

    settings = get_settings()

    # ── Build TOP_N config dari settings ──────────────────────────────────────
    # Di-inject ke user prompt agar LLM tahu batas per komponen
    # Nilai dikontrol dari .env — tidak hardcode di prompt
    top_n_config = {
        "experience":    settings.top_n_experience,
        "projects":      settings.top_n_projects,
        "education":     settings.top_n_education,
        "awards":        settings.top_n_awards,
        "organizations": settings.top_n_organizations,
        "skills":        settings.top_n_skills,
        "certificates":  settings.top_n_certificates,
    }

    # ── User prompt — kirim gap results + JD/JR context + TOP_N config ────────
    # System prompt dikelola di agents/prompts/planner_prompt.py
    gap_results = gap_analysis_context.get("results", [])

    user_prompt = f"""Generate the CV Strategy Brief for this application.

GAP ANALYSIS RESULTS ({len(gap_results)} items):
{json.dumps(gap_results, ensure_ascii=False, indent=2)}

JD/JR CONTEXT:
{json.dumps(jd_jr_context, ensure_ascii=False, indent=2)}

TOP_N_CONFIG (maximum entries per component — do not exceed):
{json.dumps(top_n_config, ensure_ascii=False, indent=2)}

Return the complete CV Strategy Brief as a single JSON object."""

    # ── LLM call ──────────────────────────────────────────────────────────────
    # max_tokens=2000 karena brief bisa panjang — terutama narrative_instructions
    raw_response = await call_llm(
        system_prompt=PLANNER_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=2000,
    )

    # ── Parse JSON response ───────────────────────────────────────────────────
    try:
        brief = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[run_planner] LLM returned unparseable JSON for "
            f"application_id={application_id}. Raw: {raw_response[:500]}"
        )
        raise ValueError(
            f"Planner Agent returned invalid JSON for "
            f"application_id={application_id}: {e}"
        )

    # ── Validasi dan normalize fields ─────────────────────────────────────────
    # Pastikan semua zona ada — LLM kadang lupa field yang nilainya kosong
    brief.setdefault("content_instructions", {})
    brief.setdefault("keyword_targets", [])
    brief.setdefault("narrative_instructions", [])
    brief.setdefault("primary_angle", "")
    brief.setdefault("summary_hook_direction", "")
    brief.setdefault("tone", "technical_concise")

    # Pastikan semua 7 komponen ada di content_instructions
    for component, top_n in top_n_config.items():
        if component not in brief["content_instructions"]:
            brief["content_instructions"][component] = {"include": [], "top_n": top_n}

    logger.info(
        f"[run_planner] brief generated: "
        f"{len(brief['keyword_targets'])} keywords, "
        f"{len(brief['narrative_instructions'])} narrative instructions"
    )

    # ── Simpan ke cv_strategy_briefs table ────────────────────────────────────
    # user_approved=false — user harus review dan approve di Interrupt 2
    # brief_id di-capture dari response untuk dipakai oleh select_content node
    supabase = get_supabase()
    response = supabase.table("cv_strategy_briefs").insert({
        "application_id": application_id,
        "content_instructions": brief["content_instructions"],
        "narrative_instructions": brief["narrative_instructions"],
        "keyword_targets": brief["keyword_targets"],
        "primary_angle": brief["primary_angle"],
        "summary_hook_direction": brief["summary_hook_direction"],
        "tone": brief["tone"],
        "user_approved": False,
    }).execute()

    brief_id = response.data[0]["id"]
    brief["brief_id"] = brief_id

    logger.info(
        f"[run_planner] brief saved to DB: brief_id={brief_id}, "
        f"application_id={application_id}"
    )

    return brief