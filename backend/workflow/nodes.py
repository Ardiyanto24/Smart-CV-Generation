# cv-agent/backend/workflow/nodes.py

"""
LangGraph node functions untuk CV Agent workflow.

Setiap node adalah async function yang:
1. Menerima CVAgentState sebagai input
2. Melakukan satu unit pekerjaan (LLM call, DB query, atau kalkulasi)
3. Mengembalikan dict berisi HANYA field state yang berubah

LangGraph otomatis merge partial dict ini ke full state —
node tidak perlu return seluruh state, hanya yang berubah.

Phase 5: semua node adalah stubs dengan placeholder data berstruktur benar.
Phase 6: setiap stub diganti dengan real LLM agent call.
"""

import logging
from datetime import datetime, timezone

from config import get_settings
from db.supabase import get_supabase
from workflow.state import CVAgentState

# ── Logger ────────────────────────────────────────────────────────────────────
# Module-level logger — dipakai oleh semua node di file ini
# Format: "workflow.nodes" sebagai logger name untuk mudah difilter di log output
# Contoh log: "workflow.nodes - INFO - [parse_jd_jr] called for application uuid-123"

logger = logging.getLogger("workflow.nodes")


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER 2 — Job Analyzer
# Node: parse_jd_jr
# ══════════════════════════════════════════════════════════════════════════════

async def parse_jd_jr(state: CVAgentState) -> dict:
    """
    Node 1: Parse raw JD/JR text into structured atomic requirement items.

    Reads raw JD/JR from job_postings table, calls Parser Agent to decompose
    into atomic items, and returns structured jd_jr_context (Context Package 2).

    Input  : state.application_id
    Output : state.jd_jr_context
    Cluster: 2 — Parser Agent
    """
    application_id = state["application_id"]
    logger.info(f"[parse_jd_jr] called for application_id={application_id}")

    supabase = get_supabase()

    # Query raw JD/JR yang sudah disimpan oleh POST /applications/{id}/start
    # Di Phase 6, data ini akan dikirim ke Parser Agent untuk diproses
    response = (
        supabase.table("job_postings")
        .select("jd_raw, jr_raw")
        .eq("application_id", application_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    # Log apa yang ditemukan di DB untuk membantu debugging
    if response.data:
        logger.info(
            f"[parse_jd_jr] found job_posting for application_id={application_id}"
        )
    else:
        logger.warning(
            f"[parse_jd_jr] no job_posting found for application_id={application_id}"
        )

    # TODO Phase 6: Replace with real Parser Agent call
    # from agents.cluster2.parser import run_parser
    # jd_raw = response.data[0]["jd_raw"]
    # jr_raw = response.data[0]["jr_raw"]
    # return {"jd_jr_context": await run_parser(application_id, jd_raw, jr_raw)}

    # ── Placeholder data — struktur harus persis sesuai Context Package 2 ──────
    # Downstream nodes (analyze_gap, plan_strategy, content_writer) membaca dari
    # jd_jr_context ini — kalau strukturnya salah, mereka akan error
    jd_jr_context = {
        "application_id": application_id,

        # job_descriptions: hasil parsing JD — satu item = satu tanggung jawab
        "job_descriptions": [
            {
                "responsibility_id": "d001",
                "text": "Menganalisis data pelanggan untuk mendukung keputusan bisnis",
            },
            {
                "responsibility_id": "d002",
                "text": "Membangun dashboard reporting untuk tim bisnis",
            },
        ],

        # job_requirements: hasil parsing JR — satu item = satu requirement
        "job_requirements": [
            {
                "requirement_id": "r001",
                "text": "Menguasai Python",
                "source": "JR",
                "priority": "must",
            },
            {
                "requirement_id": "r002",
                "text": "Pengalaman dengan SQL",
                "source": "JR",
                "priority": "must",
            },
            {
                "requirement_id": "r003",
                "text": "Pengalaman dengan AWS atau GCP",
                "source": "JR",
                "priority": "nice_to_have",
            },
        ],
    }

    logger.info(
        f"[parse_jd_jr] returning placeholder jd_jr_context "
        f"with {len(jd_jr_context['job_descriptions'])} JD items "
        f"and {len(jd_jr_context['job_requirements'])} JR items"
    )

    # Return HANYA field yang berubah — LangGraph merge otomatis ke full state
    return {"jd_jr_context": jd_jr_context}


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER 3 — Gap Analyzer
# Nodes: analyze_gap, score_gap (sekuensial — score_gap butuh output analyze_gap)
# ══════════════════════════════════════════════════════════════════════════════

async def analyze_gap(state: CVAgentState) -> dict:
    """
    Node 2: Analyze each JD/JR item against user's Master Data.

    Reads jd_jr_context from state, compares against Master Data,
    categorizes each item as exact_match, implicit_match, or gap,
    saves results to DB, and returns gap_analysis_context (Context Package 3).

    Input  : state.jd_jr_context
    Output : state.gap_analysis_context
    Cluster: 3 — Gap Analyzer Agent
    """
    application_id = state["application_id"]
    logger.info(f"[analyze_gap] called for application_id={application_id}")

    supabase = get_supabase()

    # TODO Phase 6: Replace with real Gap Analyzer Agent call
    # from agents.cluster3.gap_analyzer import fetch_master_data, run_gap_analyzer
    # master_data = await fetch_master_data(state["user_id"])
    # results = await run_gap_analyzer(application_id, state["jd_jr_context"], master_data)

    # ── Placeholder gap_analysis_context ──────────────────────────────────────
    # Struktur harus persis Context Package 3
    # Minimal dua item: satu exact_match dan satu gap
    # Downstream nodes (score_gap, plan_strategy) membaca dari results list ini

    results = [
        {
            # exact_match: ada bukti eksplisit di Master Data
            "item_id": "r001",
            "text": "Menguasai Python",
            "dimension": "JR",
            "category": "exact_match",
            "priority": "must",
            "evidence": [
                {
                    "source": "skills",
                    "entry_id": "placeholder-skill-uuid",
                    "entry_title": "Python",
                    "detail": "Standalone skill, is_inferred: false",
                }
            ],
            "reasoning": None,  # exact_match tidak butuh reasoning
        },
        {
            # implicit_match: ada bukti transferable — MySQL → SQL
            "item_id": "r002",
            "text": "Pengalaman dengan SQL",
            "dimension": "JR",
            "category": "implicit_match",
            "priority": "must",
            "evidence": [
                {
                    "source": "experience",
                    "entry_id": "placeholder-exp-uuid",
                    "entry_title": "PT Contoh Indonesia",
                    "detail": "MySQL tercantum di skills_used",
                }
            ],
            # reasoning wajib ada untuk implicit_match — menjelaskan koneksi transferable
            "reasoning": "MySQL adalah implementasi SQL — kemampuan query relasional dapat ditransfer langsung",
        },
        {
            # gap: tidak ada bukti di Master Data sama sekali
            "item_id": "r003",
            "text": "Pengalaman dengan AWS atau GCP",
            "dimension": "JR",
            "category": "gap",
            "priority": "nice_to_have",
            "evidence": [],  # kosong untuk gap
            "reasoning": None,
        },
    ]

    gap_analysis_context = {
        "application_id": application_id,
        "results": results,
    }

    # ── Simpan setiap result item ke DB ────────────────────────────────────────
    # Satu row per item — dibutuhkan oleh GET /applications/{id}/gap endpoint
    # dan oleh Planner Agent di Phase 6 untuk membuat CV Strategy Brief
    for item in results:
        supabase.table("gap_analysis_results").insert({
            "application_id": application_id,
            "item_id": item["item_id"],
            "text": item["text"],
            "dimension": item["dimension"],
            "category": item["category"],
            "priority": item["priority"],
            # evidence disimpan sebagai JSONB — harus di-wrap dalam dict
            "evidence": item["evidence"],
            "reasoning": item["reasoning"],
            # suggestion hanya untuk gap items — Phase 6 yang akan mengisi
            "suggestion": None,
        }).execute()

    logger.info(
        f"[analyze_gap] saved {len(results)} gap analysis results to DB "
        f"for application_id={application_id}"
    )

    return {"gap_analysis_context": gap_analysis_context}


async def score_gap(state: CVAgentState) -> dict:
    """
    Node 3: Calculate fit score based on gap analysis results.

    Reads gap_analysis_context from state, computes quantitative score
    and qualitative assessment, saves to DB, and returns gap_score.

    Input  : state.gap_analysis_context
    Output : state.gap_score
    Cluster: 3 — Scoring Agent
    """
    application_id = state["application_id"]
    logger.info(f"[score_gap] called for application_id={application_id}")

    supabase = get_supabase()

    # TODO Phase 6: Replace with real Scoring Agent call
    # from agents.cluster3.scoring import run_scoring
    # results = state["gap_analysis_context"]["results"]
    # return {"gap_score": await run_scoring(application_id, results)}

    # ── Placeholder gap_score ─────────────────────────────────────────────────
    # Nilai 72.0 → verdict "cukup_cocok" (range 50-74)
    # proceed_recommendation "lanjut" → workflow melanjutkan ke plan_strategy
    # Kalau "tinjau" → user disarankan kembali update profil dulu
    gap_score = {
        "quantitative_score": 72.0,
        "verdict": "cukup_cocok",
        "strength": "Kompetensi teknis core (Python, SQL) kuat dan exact match dengan requirements utama",
        "concern": "Gap di beberapa requirement nice_to_have seperti cloud platform experience",
        "recommendation": "Lanjutkan generate CV, pastikan narasi menjembatani gap yang ada",
        "proceed_recommendation": "lanjut",
    }

    # ── Simpan ke DB ──────────────────────────────────────────────────────────
    # Satu row per application — dibutuhkan oleh GET /applications/{id}/gap endpoint
    # Relasi one-to-one dengan applications table (satu application, satu score)
    supabase.table("gap_analysis_scores").insert({
        "application_id": application_id,
        "quantitative_score": gap_score["quantitative_score"],
        "verdict": gap_score["verdict"],
        "strength": gap_score["strength"],
        "concern": gap_score["concern"],
        "recommendation": gap_score["recommendation"],
        "proceed_recommendation": gap_score["proceed_recommendation"],
    }).execute()

    logger.info(
        f"[score_gap] saved gap score to DB: "
        f"score={gap_score['quantitative_score']}, "
        f"verdict={gap_score['verdict']}, "
        f"proceed={gap_score['proceed_recommendation']}"
    )

    return {"gap_score": gap_score}


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER 4 — Orchestrator (Planning Phase)
# Nodes: plan_strategy, select_content (sekuensial)
# Berjalan setelah Interrupt 1 (user approve gap analysis)
# ══════════════════════════════════════════════════════════════════════════════

async def plan_strategy(state: CVAgentState) -> dict:
    """
    Node 4: Generate CV Strategy Brief based on gap analysis.

    Reads gap_analysis_context, gap_score, and jd_jr_context from state.
    Produces strategy_brief — the "contract" governing all CV generation.
    Saves brief to DB with user_approved=false (user reviews at Interrupt 2).

    Input  : state.gap_analysis_context, state.gap_score, state.jd_jr_context
    Output : state.strategy_brief, state.brief_id
    Cluster: 4 — Planner Agent
    """
    application_id = state["application_id"]
    logger.info(f"[plan_strategy] called for application_id={application_id}")

    supabase = get_supabase()

    # TODO Phase 6: Replace with real Planner Agent call
    # from agents.cluster4.planner import run_planner
    # return await run_planner(
    #     application_id,
    #     state["gap_analysis_context"],
    #     state["jd_jr_context"],
    # )

    # ── Placeholder strategy_brief ────────────────────────────────────────────
    # Brief terdiri dari tiga zona editabilitas berbeda untuk user:
    # - Zona Merah  : content_instructions — read-only, dikelola agent
    # - Zona Kuning : keyword_targets + narrative_instructions — bisa diedit terbatas
    # - Zona Hijau  : primary_angle, summary_hook_direction, tone — bebas diedit

    strategy_brief = {
        # Zona Merah — komponen mana yang masuk CV dan berapa entry per komponen
        "content_instructions": {
            "experience": {"include": [], "top_n": 3},
            "projects":   {"include": [], "top_n": 3},
            "education":  {"include": [], "top_n": 2},
            "skills":     {"include": [], "top_n": 15},
        },

        # Zona Kuning — narrative instructions untuk implicit match dan gap bridge
        # user bisa setuju, ubah angle, atau tolak setiap item
        "narrative_instructions": [
            {
                "id": "ni-001",
                "type": "implicit_match",
                "requirement": "Pengalaman dengan SQL",
                "matched_with": "MySQL experience",
                "suggested_angle": "Narrasikan sebagai SQL proficiency — MySQL adalah implementasi SQL",
                "user_decision": None,  # None = belum diputuskan user
            }
        ],

        # Zona Kuning — keyword yang harus muncul secara natural di CV
        "keyword_targets": ["Python", "data analysis", "SQL"],

        # Zona Hijau — bebas diedit user tanpa batasan
        "primary_angle": "Data professional dengan kemampuan teknis yang kuat",
        "summary_hook_direction": "Buka dengan posisi sebagai data professional yang menggabungkan kemampuan teknis dengan komunikasi bisnis",
        "tone": "technical_concise",

        # Selalu false saat pertama dibuat — menjadi true setelah user approve di Interrupt 2
        "user_approved": False,
    }

    # ── Simpan ke DB dan capture generated brief_id ───────────────────────────
    # brief_id dibutuhkan oleh select_content node untuk membuat relasi
    # di selected_content_packages table
    response = supabase.table("cv_strategy_briefs").insert({
        "application_id": application_id,
        "content_instructions": strategy_brief["content_instructions"],
        "narrative_instructions": strategy_brief["narrative_instructions"],
        "keyword_targets": strategy_brief["keyword_targets"],
        "primary_angle": strategy_brief["primary_angle"],
        "summary_hook_direction": strategy_brief["summary_hook_direction"],
        "tone": strategy_brief["tone"],
        "user_approved": False,
    }).execute()

    # Ambil UUID yang di-generate DB untuk brief ini
    brief_id = response.data[0]["id"]

    logger.info(
        f"[plan_strategy] saved strategy brief to DB: brief_id={brief_id}"
    )

    # Return dua field sekaligus — strategy_brief untuk content, brief_id untuk relasi
    return {
        "strategy_brief": strategy_brief,
        "brief_id": brief_id,
    }


async def select_content(state: CVAgentState) -> dict:
    """
    Node 5: Select which Master Data entries will appear in the CV.

    Reads strategy_brief from state (already user-approved at Interrupt 2).
    Queries Master Data DB for experience and projects entries.
    Adds bullet_quota to each entry, saves package to DB.

    Input  : state.strategy_brief, state.brief_id, state.user_id
    Output : state.selected_content_package
    Cluster: 4 — Selection Agent
    """
    application_id = state["application_id"]
    user_id = state["user_id"]
    brief_id = state["brief_id"]
    logger.info(f"[select_content] called for application_id={application_id}")

    supabase = get_supabase()

    # TODO Phase 6: Replace with real Selection Agent call
    # from agents.cluster4.selection import run_selection
    # return {"selected_content_package": await run_selection(
    #     application_id, user_id, state["strategy_brief"]
    # )}

    # ── Query Master Data — ambil entry nyata dari DB user ────────────────────
    # Ini bukan placeholder — kita benar-benar query data milik user
    # Hasilnya mungkin kosong kalau user belum mengisi profil, dan itu OK
    # Selection Agent di Phase 6 akan melakukan ranking dan filtering yang lebih cerdas

    # Ambil maksimal 3 experience entries milik user ini
    exp_response = (
        supabase.table("experience")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    )

    # Ambil maksimal 3 projects entries milik user ini
    proj_response = (
        supabase.table("projects")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    )

    # ── Tambahkan bullet_quota ke setiap entry ─────────────────────────────────
    # bullet_quota = 3 berarti Content Writer Agent akan menulis 3 bullet points
    # per entry. Ini adalah instruksi untuk Cluster 5.
    experience_entries = [
        {**entry, "bullet_quota": 3}
        for entry in exp_response.data
    ]

    projects_entries = [
        {**entry, "bullet_quota": 3}
        for entry in proj_response.data
    ]

    # ── Build selected_content_package — Context Package 4 ───────────────────
    # brief: copy field-field yang dibutuhkan Content Writer dari strategy_brief
    # selected_content: entry-entry yang dipilih per komponen
    brief = state["strategy_brief"]

    selected_content_package = {
        "application_id": application_id,
        "brief_id": brief_id,

        # Subset dari strategy_brief yang dibutuhkan Content Writer Agent
        "brief": {
            "primary_angle": brief["primary_angle"],
            "summary_hook_direction": brief["summary_hook_direction"],
            "keyword_targets": brief["keyword_targets"],
            "tone": brief["tone"],
            "narrative_instructions": brief["narrative_instructions"],
        },

        # Entry yang dipilih — bisa kosong kalau user belum isi profil
        "selected_content": {
            "experience": experience_entries,
            "projects": projects_entries,
            "education": [],    # Phase 6: Selection Agent akan mengisi ini
            "awards": [],
            "organizations": [],
            "skills": [],
            "certificates": [],
        },
    }

    # ── Simpan ke DB ──────────────────────────────────────────────────────────
    # Disimpan sebagai JSONB — seluruh package dalam satu row
    # Relasi ke brief via brief_id untuk audit trail
    supabase.table("selected_content_packages").insert({
        "application_id": application_id,
        "brief_id": brief_id,
        "content": selected_content_package,
    }).execute()

    logger.info(
        f"[select_content] selected {len(experience_entries)} experience "
        f"and {len(projects_entries)} projects entries for application_id={application_id}"
    )

    return {"selected_content_package": selected_content_package}