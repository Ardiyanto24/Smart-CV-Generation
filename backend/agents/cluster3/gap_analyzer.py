# cv-agent/backend/agents/cluster3/gap_analyzer.py

"""
Gap Analyzer Agent — Cluster 3

Menganalisis setiap JD/JR item terhadap Master Data user dan mengkategorikan
sebagai exact_match, implicit_match, atau gap.

Dua fungsi:
- fetch_master_data : query semua 7 tabel Master Data (helper, dipakai juga oleh Cluster 4)
- run_gap_analyzer  : core gap analysis menggunakan LLM

Prompts dikelola di: agents/prompts/gap_analyzer_prompt.py
"""

import json
import logging

from agents.llm_client import call_llm
from agents.prompts.gap_analyzer_prompt import GAP_ANALYZER_SYSTEM
from db.supabase import get_supabase

logger = logging.getLogger("agents.cluster3.gap_analyzer")


async def fetch_master_data(user_id: str) -> dict:
    """
    Query semua 7 tabel Master Data untuk user yang diberikan.

    Dipakai oleh:
    - run_gap_analyzer (node analyze_gap) — untuk gap analysis
    - select_content node (Cluster 4) — untuk content selection

    Returns dict following Context Package 1 structure:
    {
        "experience": [...],
        "education": [...],
        "projects": [...],
        "awards": [...],
        "organizations": [...],
        "certificates": [...],
        "skills": [...]
    }

    Args:
        user_id: UUID user yang Master Data-nya akan di-fetch

    Returns:
        dict dengan 7 keys, setiap key berisi list entries dari tabel yang sesuai
    """
    logger.info(f"[fetch_master_data] fetching all master data for user_id={user_id}")

    supabase = get_supabase()

    # Query 7 tabel secara sequential
    # Urutan: komponen yang paling sering punya banyak data dulu
    components = [
        "experience",
        "education",
        "projects",
        "awards",
        "organizations",
        "certificates",
        "skills",
    ]

    master_data = {}
    for component in components:
        response = (
            supabase.table(component)
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        master_data[component] = response.data

    total_entries = sum(len(v) for v in master_data.values())
    logger.info(
        f"[fetch_master_data] fetched {total_entries} total entries "
        f"across 7 components for user_id={user_id}"
    )

    return master_data


async def run_gap_analyzer(
    application_id: str,
    jd_jr_context: dict,
    master_data: dict,
) -> list:
    """
    Analyze all JD/JR items against user's Master Data.

    Semua items dikirim ke LLM dalam SATU call untuk:
    1. Efisiensi — mengurangi API calls dan latency
    2. Konteks — LLM bisa melihat pola keseluruhan JD/JR

    Hasil di-bulk-insert ke gap_analysis_results table.

    Args:
        application_id: UUID of the application being processed
        jd_jr_context: Context Package 2 — output dari Parser Agent
        master_data: Context Package 1 — output dari fetch_master_data

    Returns:
        List of gap analysis result objects (satu per JD/JR item)
    """
    logger.info(
        f"[run_gap_analyzer] analyzing gap for application_id={application_id}"
    )

    job_descriptions = jd_jr_context.get("job_descriptions", [])
    job_requirements = jd_jr_context.get("job_requirements", [])
    total_items = len(job_descriptions) + len(job_requirements)

    logger.info(
        f"[run_gap_analyzer] analyzing {total_items} items "
        f"({len(job_descriptions)} JD, {len(job_requirements)} JR)"
    )

    # ── Build combined items list dengan dimension label ───────────────────────
    # Label dimension ke setiap item sebelum dikirim ke LLM
    # JD items default priority "must" — responsibilities selalu wajib
    # JR items sudah punya priority dari Parser Agent
    labeled_jd = [
        {**item, "dimension": "JD", "priority": "must"}
        for item in job_descriptions
    ]
    labeled_jr = [
        {**item, "dimension": "JR"}
        for item in job_requirements
    ]
    all_items = labeled_jd + labeled_jr

    # ── User prompt — kirim semua items + master data ─────────────────────────
    # System prompt dikelola di agents/prompts/gap_analyzer_prompt.py
    user_prompt = f"""Analyze these {len(all_items)} JD/JR items against the candidate's Master Data.

ITEMS TO ANALYZE ({len(all_items)} total):
{json.dumps(all_items, ensure_ascii=False, indent=2)}

CANDIDATE MASTER DATA:
{json.dumps(master_data, ensure_ascii=False, indent=2)}

Return a JSON array with exactly {len(all_items)} result objects — one per item above."""

    # ── LLM call ──────────────────────────────────────────────────────────────
    # max_tokens=4000 karena banyak items + evidence arrays yang verbose
    raw_response = await call_llm(
        system_prompt=GAP_ANALYZER_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=4000,
    )

    # ── Parse JSON response ───────────────────────────────────────────────────
    # JSONDecodeError di-raise sebagai ValueError agar with_retry bisa retry
    try:
        results = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[run_gap_analyzer] LLM returned unparseable JSON for "
            f"application_id={application_id}. Raw: {raw_response[:500]}"
        )
        raise ValueError(
            f"Gap Analyzer returned invalid JSON for "
            f"application_id={application_id}: {e}"
        )

    if not isinstance(results, list):
        raise ValueError(
            f"Gap Analyzer returned non-list response for "
            f"application_id={application_id}"
        )

    logger.info(
        f"[run_gap_analyzer] LLM returned {len(results)} results for "
        f"application_id={application_id}"
    )

    # ── Normalize fields — defensive default untuk fields yang mungkin absen ──
    # LLM kadang skip fields yang nilainya null, terutama untuk exact_match
    # yang tidak punya reasoning/suggestion
    for result in results:
        result.setdefault("evidence", [])
        result.setdefault("reasoning", None)
        result.setdefault("suggestion", None)
        result.setdefault("priority", "must")

    # ── Bulk insert ke gap_analysis_results ───────────────────────────────────
    # Satu row per item — batch insert lebih efisien dari loop individual
    # Dibutuhkan oleh GET /applications/{id}/gap endpoint dan Scoring Agent
    supabase = get_supabase()

    rows = [
        {
            "application_id": application_id,
            "item_id": result.get("item_id"),
            "text": result.get("text"),
            "dimension": result.get("dimension"),
            "category": result.get("category"),
            "priority": result.get("priority", "must"),
            # evidence disimpan sebagai JSONB — list of objects
            "evidence": result.get("evidence", []),
            "reasoning": result.get("reasoning"),
            "suggestion": result.get("suggestion"),
        }
        for result in results
    ]

    supabase.table("gap_analysis_results").insert(rows).execute()

    # ── Log ringkasan per kategori ────────────────────────────────────────────
    categories = {"exact_match": 0, "implicit_match": 0, "gap": 0}
    for result in results:
        cat = result.get("category", "gap")
        categories[cat] = categories.get(cat, 0) + 1

    logger.info(
        f"[run_gap_analyzer] results saved — "
        f"exact_match={categories['exact_match']}, "
        f"implicit_match={categories['implicit_match']}, "
        f"gap={categories['gap']}"
    )

    return results