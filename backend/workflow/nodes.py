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
from workflow.retry import with_retry

from agents.cluster2.parser import run_parser
from agents.cluster3.gap_analyzer import fetch_master_data, run_gap_analyzer
from agents.cluster3.scoring import run_scoring

# ── Logger ────────────────────────────────────────────────────────────────────
# Module-level logger — dipakai oleh semua node di file ini
# Format: "workflow.nodes" sebagai logger name untuk mudah difilter di log output
# Contoh log: "workflow.nodes - INFO - [parse_jd_jr] called for application uuid-123"

logger = logging.getLogger("workflow.nodes")


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER 2 — Job Analyzer
# Node: parse_jd_jr
# ══════════════════════════════════════════════════════════════════════════════

@with_retry
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

    @with_retry
    async def parse_jd_jr(state: CVAgentState) -> dict:
        """
        Node 1: Parse raw JD/JR text into structured atomic requirement items.

        Reads raw JD/JR from job_postings table, calls Parser Agent to decompose
        into atomic items, saves to job_descriptions and job_requirements tables,
        and returns structured jd_jr_context (Context Package 2).

        Input  : state.application_id
        Output : state.jd_jr_context
        Cluster: 2 — Parser Agent
        """
        application_id = state["application_id"]
        logger.info(f"[parse_jd_jr] called for application_id={application_id}")

        supabase = get_supabase()

        # Query raw JD/JR dari job_postings table
        # Disimpan sebelumnya oleh POST /applications/{id}/start endpoint
        response = (
            supabase.table("job_postings")
            .select("jd_raw, jr_raw")
            .eq("application_id", application_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise ValueError(
                f"No job_posting found for application_id={application_id}. "
                f"Ensure POST /applications/{application_id}/start was called first."
            )

        job_posting = response.data[0]
        jd_raw = job_posting.get("jd_raw")
        jr_raw = job_posting.get("jr_raw")

        logger.info(
            f"[parse_jd_jr] found job_posting — "
            f"jd_raw={'present' if jd_raw else 'empty'}, "
            f"jr_raw={'present' if jr_raw else 'empty'}"
        )

        # Panggil Parser Agent — dekomposisi, priority detection, deduplikasi
        # Hasil langsung disimpan ke job_descriptions dan job_requirements tables
        jd_jr_context = await run_parser(
            application_id=application_id,
            jd_raw=jd_raw,
            jr_raw=jr_raw,
        )

        logger.info(
            f"[parse_jd_jr] parsing complete: "
            f"{len(jd_jr_context['job_descriptions'])} JD items, "
            f"{len(jd_jr_context['job_requirements'])} JR items"
        )

        return {"jd_jr_context": jd_jr_context}


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER 3 — Gap Analyzer
# Nodes: analyze_gap, score_gap (sekuensial — score_gap butuh output analyze_gap)
# ══════════════════════════════════════════════════════════════════════════════

@with_retry
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
    user_id = state["user_id"]
    logger.info(f"[analyze_gap] called for application_id={application_id}")

    # Fetch semua Master Data user — dibutuhkan oleh Gap Analyzer Agent
    # fetch_master_data query 7 tabel sekaligus dan return Context Package 1
    master_data = await fetch_master_data(user_id)

    logger.info(
        f"[analyze_gap] master data fetched, "
        f"calling Gap Analyzer Agent for application_id={application_id}"
    )

    # Panggil Gap Analyzer Agent — analisis semua JD/JR items dalam satu LLM call
    # results adalah list of gap analysis objects (exact_match/implicit_match/gap)
    # Agent juga bulk-insert semua results ke gap_analysis_results table
    results = await run_gap_analyzer(
        application_id=application_id,
        jd_jr_context=state["jd_jr_context"],
        master_data=master_data,
    )

    # Build gap_analysis_context — Context Package 3
    # Dibaca oleh score_gap node dan plan_strategy node downstream
    gap_analysis_context = {
        "application_id": application_id,
        "results": results,
    }

    logger.info(
        f"[analyze_gap] complete: {len(results)} items analyzed "
        f"for application_id={application_id}"
    )

    return {"gap_analysis_context": gap_analysis_context}


@with_retry
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

    # Extract results list dari gap_analysis_context
    # run_scoring hanya butuh list of gap result objects, bukan full context dict
    gap_results = state["gap_analysis_context"]["results"]

    logger.info(
        f"[score_gap] calling Scoring Agent with {len(gap_results)} gap results "
        f"for application_id={application_id}"
    )

    # Panggil Scoring Agent — Part 1 deterministik + Part 2 LLM as Judge
    # Agent juga menyimpan hasil ke gap_analysis_scores table
    gap_score = await run_scoring(
        application_id=application_id,
        gap_results=gap_results,
    )

    logger.info(
        f"[score_gap] scoring complete: "
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

@with_retry
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


@with_retry
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


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER 5 — CV Generator
# Node: generate_content
# Di Phase 6 akan menjalankan 4 fase:
#   Fase 1: Pass-through assembly (data non-generated dari Master Data)
#   Fase 2: Content generation paralel per komponen (Content Writer Agent)
#   Fase 3: Skills grouping (Skills Grouping Agent)
#   Fase 4: Summary generation (Summary Writer Agent — selalu terakhir)
# ══════════════════════════════════════════════════════════════════════════════

@with_retry
async def generate_content(state: CVAgentState) -> dict:
    """
    Node 6: Generate full CV content from Selected Content Package.

    Reads selected_content_package and strategy_brief from state.
    Produces Final Structured Output JSON — the complete CV content.
    Saves to cv_outputs table with version tracking.

    In Phase 6, this node runs 4 sequential phases:
    1. Pass-through assembly (non-LLM)
    2. Content Writer Agent per component (parallel within, sequential across)
    3. Skills Grouping Agent
    4. Summary Writer Agent (always last)

    Input  : state.selected_content_package, state.strategy_brief, state.cv_version
    Output : state.cv_output
    Cluster: 5 — Content Writer + Skills Grouping + Summary Writer
    """
    application_id = state["application_id"]
    cv_version = state["cv_version"]
    logger.info(
        f"[generate_content] called for application_id={application_id}, "
        f"cv_version={cv_version}"
    )

    supabase = get_supabase()

    # TODO Phase 6: Replace with real Content Writer + Skills Grouping + Summary Writer Agent calls
    # Fase 1: pass-through assembly dari Master Data
    # Fase 2: asyncio.gather per komponen — Content Writer Agent
    # Fase 3: Skills Grouping Agent
    # Fase 4: Summary Writer Agent (setelah semua section selesai)

    # ── Placeholder cv_output ─────────────────────────────────────────────────
    # Struktur harus persis Final Structured Output JSON (cluster5_specification Section 8)
    # Urutan section fixed: header → summary → experience → education →
    #                       awards → skills → projects → certificates → organizations

    generated_at = datetime.now(timezone.utc).isoformat()

    cv_output = {
        "application_id": application_id,
        "version": cv_version,
        "generated_at": generated_at,

        # ── Header: pass-through dari Master Data (non-generated) ─────────────
        # Di Phase 6 diambil dari tabel users dan kontak user
        "header": {
            "name": "Placeholder Name",
            "email": "placeholder@email.com",
            "phone": "+62812345678",
            "linkedin": "placeholder-linkedin",
            "github": "placeholder-github",
        },

        # ── Summary: digenerate oleh Summary Writer Agent ─────────────────────
        # Selalu ditulis TERAKHIR setelah semua section lain selesai
        # agar summary benar-benar mencerminkan isi CV, bukan generik
        "summary": (
            "Placeholder summary — Data professional dengan pengalaman membangun "
            "solusi analitik berbasis Python dan SQL. Terbiasa berkolaborasi dengan "
            "stakeholder bisnis untuk menghasilkan insight yang actionable."
        ),

        # ── Experience: digenerate oleh Content Writer Agent ──────────────────
        # Tiga bullet points per entry: what_i_did → challenge → impact
        # Setiap bullet max 20 kata, diawali action verb
        "experience": [
            {
                "entry_id": "placeholder-exp-uuid",
                "company": "PT Contoh Indonesia",
                "role": "Data Analyst",
                "year": "2023 – 2024",
                "bullets": [
                    "Developed Python-based data pipeline processing 1M+ daily transactions for business intelligence reporting.",
                    "Addressed data quality issues by implementing automated validation checks, reducing error rate by 40%.",
                    "Delivered weekly SQL dashboards enabling stakeholders to monitor KPIs with 2-day faster turnaround.",
                ],
            }
        ],

        # ── Education: digenerate oleh Content Writer Agent ───────────────────
        "education": [
            {
                "entry_id": "placeholder-edu-uuid",
                "institution": "Universitas Contoh",
                "degree": "S1 Statistika",
                "year": "2019 – 2023",
                "location": "Jakarta",
                "bullets": [
                    "Completed statistical modeling curriculum with focus on applied machine learning and data analysis.",
                    "Addressed complex research challenges through thesis on predictive modeling for customer churn.",
                    "Achieved GPA 3.75/4.00 while actively contributing to university data science community.",
                ],
            }
        ],

        # ── Awards: digenerate oleh Content Writer Agent ──────────────────────
        "awards": [
            {
                "entry_id": "placeholder-award-uuid",
                "title": "Best Data Project — Placeholder Competition",
                "issuer": "Placeholder Organization",
                "year": "2023",
                "bullets": [
                    "Developed winning predictive model achieving 92% accuracy on real-world dataset.",
                    "Addressed imbalanced data challenge using SMOTE and ensemble methods.",
                    "Delivered solution ranked 1st among 50+ competing teams nationally.",
                ],
            }
        ],

        # ── Skills: digenerate oleh Skills Grouping Agent ─────────────────────
        # Dikelompokkan berdasarkan domain, bukan hanya kategori DB (technical/soft/tool)
        "skills": {
            "skills_grouped": [
                {
                    "group_label": "Programming Languages",
                    "items": ["Python", "SQL", "R"],
                },
                {
                    "group_label": "Libraries & Frameworks",
                    "items": ["Pandas", "Scikit-learn", "TensorFlow"],
                },
                {
                    "group_label": "Tools & Platforms",
                    "items": ["MySQL", "Tableau", "Git"],
                },
                {
                    "group_label": "Personal Strengths",
                    "items": ["Stakeholder Communication", "Problem Solving"],
                },
            ]
        },

        # ── Projects: digenerate oleh Content Writer Agent ────────────────────
        "projects": [
            {
                "entry_id": "placeholder-proj-uuid",
                "title": "Customer Churn Prediction System",
                "github_url": "https://github.com/placeholder/churn-prediction",
                "tools": ["Python", "Scikit-learn", "MySQL"],
                "bullets": [
                    "Built end-to-end churn prediction pipeline using Random Forest with 87% accuracy.",
                    "Addressed class imbalance (1:20 ratio) through SMOTE and threshold optimization techniques.",
                    "Delivered automated retraining pipeline reducing manual intervention by 80% monthly.",
                ],
            }
        ],

        # ── Certificates: pass-through dari Master Data (non-generated) ───────
        # Tidak ada bullet points — hanya listing metadata
        "certificates": [
            {
                "name": "Machine Learning Specialization",
                "issuer": "Coursera — Stanford University",
            }
        ],

        # ── Organizations: digenerate oleh Content Writer Agent ───────────────
        "organizations": [
            {
                "entry_id": "placeholder-org-uuid",
                "name": "Data Science Community",
                "role": "Vice President",
                "year": "2022",
                "bullets": [
                    "Led university data science community with 200+ active members across 3 faculties.",
                    "Addressed member engagement challenges by launching weekly workshop series.",
                    "Increased active participation by 60% within one semester through structured programs.",
                ],
            }
        ],
    }

    # ── Simpan ke cv_outputs table ────────────────────────────────────────────
    # version dari state — dimulai dari 1, naik setiap revisi
    # revision_type "initial" — ini adalah versi pertama, bukan hasil revisi
    # status "draft" — akan berubah menjadi "qc_passed" setelah QC evaluate
    supabase.table("cv_outputs").insert({
        "application_id": application_id,
        "version": cv_version,
        "content": cv_output,
        "revision_type": "initial",
        "section_revised": None,    # None = seluruh CV digenerate, bukan satu section
        "status": "draft",
    }).execute()

    logger.info(
        f"[generate_content] saved cv_output to DB: "
        f"version={cv_version}, revision_type=initial, status=draft"
    )

    return {"cv_output": cv_output}


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER 6 — Quality Control
# Node: qc_evaluate
# Di Phase 6 akan menjalankan dua agent SECARA PARALEL:
#   - ATS Scoring Agent: keyword matching deterministik + LLM preserve analyzer
#   - Semantic Reviewer Agent: evaluasi kesesuaian narasi dengan JD/JR
# ══════════════════════════════════════════════════════════════════════════════

@with_retry
async def qc_evaluate(state: CVAgentState) -> dict:
    """
    Node 7: Evaluate CV quality from two dimensions in parallel.

    Reads cv_output and jd_jr_context from state.
    Runs ATS Scoring and Semantic Review (parallel in Phase 6).
    Saves results to qc_results (per section) and qc_overall_scores (aggregate).
    Increments qc_iteration counter.

    CRITICAL: In Phase 5 stub, all sections have action_required=false.
    This ensures workflow proceeds to user review without entering revision loop.
    In Phase 6, real scores determine which sections need revision.

    Input  : state.cv_output, state.jd_jr_context, state.cv_version, state.qc_iteration
    Output : state.qc_report, state.qc_iteration (incremented)
    Cluster: 6 — ATS Scoring Agent + Semantic Reviewer Agent (parallel)
    """
    application_id = state["application_id"]
    cv_version = state["cv_version"]

    # qc_iteration di state adalah nilai SEBELUM run ini
    # iteration yang disimpan ke DB dan di-report adalah nilai SETELAH increment
    current_iteration = state["qc_iteration"] + 1

    logger.info(
        f"[qc_evaluate] called for application_id={application_id}, "
        f"cv_version={cv_version}, iteration={current_iteration}"
    )

    supabase = get_supabase()

    # TODO Phase 6: Replace with real ATS Scoring + Semantic Reviewer Agent calls (parallel)
    # from agents.cluster6.ats_scoring import run_ats_scoring
    # from agents.cluster6.semantic_reviewer import run_semantic_review
    # from agents.cluster6.qc_combiner import combine_qc_results
    # settings = get_settings()
    # ats_result, semantic_results = await asyncio.gather(
    #     run_ats_scoring(cv_output, keyword_targets, job_requirements),
    #     run_semantic_review(cv_output, jd_jr_context, narrative_instructions),
    # )
    # qc_report = combine_qc_results(ats_result, semantic_results, cv_version, current_iteration, settings)

    # ── Placeholder sections ──────────────────────────────────────────────────
    # Satu entry per section CV — mengikuti urutan fixed dari cluster5_specification
    # action_required: false di SEMUA section — kritis untuk mencegah revision loop
    # di Phase 5. Di Phase 6, nilai ini ditentukan oleh real QC scores.

    sections = [
        {
            "section": "summary",
            "entry_id": None,           # None untuk section yang tidak map ke satu entry
            "ats_score": 78.0,
            "ats_status": "passed",
            "semantic_score": 80.0,
            "semantic_status": "passed",
            "action_required": False,   # ← KRITIS: harus False di Phase 5
            "preserve": ["opening sentence mencerminkan primary_angle dengan baik"],
            "revise": [],
            "missed_keywords": [],
        },
        {
            "section": "experience",
            "entry_id": "placeholder-exp-uuid",
            "ats_score": 82.0,
            "ats_status": "passed",
            "semantic_score": 79.0,
            "semantic_status": "passed",
            "action_required": False,
            "preserve": ["keyword 'Python' di bullet 1", "action verb 'Developed' di bullet 1"],
            "revise": [],
            "missed_keywords": [],
        },
        {
            "section": "education",
            "entry_id": "placeholder-edu-uuid",
            "ats_score": 70.0,
            "ats_status": "passed",
            "semantic_score": 72.0,
            "semantic_status": "passed",
            "action_required": False,
            "preserve": ["GPA mention di bullet 3"],
            "revise": [],
            "missed_keywords": [],
        },
        {
            "section": "skills",
            "entry_id": None,
            "ats_score": 85.0,
            "ats_status": "passed",
            "semantic_score": 83.0,
            "semantic_status": "passed",
            "action_required": False,
            "preserve": ["Python dan SQL di Programming Languages group"],
            "revise": [],
            "missed_keywords": [],
        },
        {
            "section": "projects",
            "entry_id": "placeholder-proj-uuid",
            "ats_score": 76.0,
            "ats_status": "passed",
            "semantic_score": 74.0,
            "semantic_status": "passed",
            "action_required": False,
            "preserve": ["keyword 'data pipeline' di bullet 1"],
            "revise": [],
            "missed_keywords": [],
        },
    ]

    # ── Build qc_report — Context Package 5 ───────────────────────────────────
    qc_report = {
        "application_id": application_id,
        "cv_version": cv_version,
        "iteration": current_iteration,
        "overall_ats_score": 78.0,
        "sections": sections,
    }

    # ── Simpan satu row per section ke qc_results ─────────────────────────────
    # Dibutuhkan oleh GET /applications/{id}/qc endpoint
    # dan oleh select_best_version node (untuk best version selection
    # saat MAX_QC_ITERATIONS habis — memilih versi dengan combined_score tertinggi)
    for section in sections:
        supabase.table("qc_results").insert({
            "application_id": application_id,
            "cv_version": cv_version,
            "iteration": current_iteration,
            "section": section["section"],
            "entry_id": section["entry_id"],
            "ats_score": section["ats_score"],
            "ats_status": section["ats_status"],
            "semantic_score": section["semantic_score"],
            "semantic_status": section["semantic_status"],
            "action_required": section["action_required"],
            "preserve": section["preserve"],
            "revise": section["revise"],
            "missed_keywords": section["missed_keywords"],
            # combined_score untuk best version selection di select_best_version node
            # formula: (ats × 0.5) + (semantic × 0.5) — weights dari settings
            "combined_score": (section["ats_score"] * 0.5) + (section["semantic_score"] * 0.5),
        }).execute()

    # ── Simpan aggregate score ke qc_overall_scores ───────────────────────────
    # Satu row per QC run — berisi ringkasan keseluruhan
    # sections_passed dan sections_failed untuk dashboard user
    sections_passed = sum(1 for s in sections if not s["action_required"])
    sections_failed = sum(1 for s in sections if s["action_required"])

    supabase.table("qc_overall_scores").insert({
        "application_id": application_id,
        "cv_version": cv_version,
        "iteration": current_iteration,
        "overall_ats_score": qc_report["overall_ats_score"],
        "sections_passed": sections_passed,
        "sections_failed": sections_failed,
    }).execute()

    logger.info(
        f"[qc_evaluate] QC complete: iteration={current_iteration}, "
        f"overall_ats={qc_report['overall_ats_score']}, "
        f"passed={sections_passed}, failed={sections_failed}"
    )

    # Return dua field — qc_report (hasil evaluasi) dan qc_iteration (counter diupdate)
    return {
        "qc_report": qc_report,
        "qc_iteration": current_iteration,  # update counter di state
    }


# ══════════════════════════════════════════════════════════════════════════════
# REVISION NODES
# Dua jalur revisi yang terpisah:
#   Jalur A: revise_content — QC-driven, otomatis, ada batas iterasi
#   Jalur B: apply_user_revisions — user-driven, manual, bebas iterasi
# QC-driven harus selesai dulu sebelum user bisa melakukan user-driven revision
# ══════════════════════════════════════════════════════════════════════════════

@with_retry
async def revise_content(state: CVAgentState) -> dict:
    """
    Node 9: Handle QC-driven revision (Jalur A).

    Triggered automatically when qc_evaluate finds sections with action_required=true
    AND qc_iteration < MAX_QC_ITERATIONS.

    Reads qc_report to identify failed sections, generates revision instructions,
    produces new cv_output version, and saves to DB.

    In Phase 6: calls Revision Handler + Content Writer Agent for failed sections only,
    running them in parallel using asyncio.gather.

    Input  : state.qc_report, state.cv_output, state.cv_version, state.qc_iteration
    Output : state.cv_output (new version), state.cv_version (incremented)
    """
    application_id = state["application_id"]
    current_iteration = state["qc_iteration"]
    new_version = state["cv_version"] + 1

    logger.info(
        f"[revise_content] called for application_id={application_id}, "
        f"iteration={current_iteration}, new_cv_version={new_version}"
    )

    supabase = get_supabase()

    # TODO Phase 6: Replace with real Revision Handler + Content Writer Agent calls
    # from agents.cluster4.revision_handler import run_qc_revision
    # revised_sections = await run_qc_revision(
    #     application_id,
    #     state["qc_report"],
    #     state["cv_output"],
    #     state["strategy_brief"],
    # )
    # Merge revised sections back into cv_output

    # ── Copy cv_output lama dan tambahkan revision note ───────────────────────
    # {**dict} membuat shallow copy — tidak mutate state langsung
    # _revision_note adalah marker bahwa ini hasil revisi stub, bukan LLM
    # Di Phase 6, field ini tidak ada — isinya adalah perubahan konten nyata
    revised_cv_output = {
        **state["cv_output"],
        "_revision_note": f"QC-driven revision stub — iteration {current_iteration}",
        "version": new_version,  # update version di dalam content juga
    }

    # ── Simpan versi baru ke cv_outputs ───────────────────────────────────────
    # Tidak menimpa versi lama — insert row baru dengan version yang di-increment
    # section_revised = "all" karena QC bisa merevisi multiple sections sekaligus
    supabase.table("cv_outputs").insert({
        "application_id": application_id,
        "version": new_version,
        "content": revised_cv_output,
        "revision_type": "qc_driven",
        "section_revised": "all",   # QC revisi semua section yang gagal sekaligus
        "status": "draft",          # kembali ke draft — akan di-QC ulang
    }).execute()

    # ── Catat di revision_history ─────────────────────────────────────────────
    # Audit trail untuk setiap instruksi revisi yang dikirim ke Cluster 5
    # sections berisi detail instruksi — di Phase 5 hanya placeholder
    supabase.table("revision_history").insert({
        "application_id": application_id,
        "revision_type": "qc_driven",
        "iteration": current_iteration,
        "sections": {
            "note": f"QC-driven revision stub for iteration {current_iteration}",
            "sections_revised": "all",
        },
        "status": "completed",
    }).execute()

    logger.info(
        f"[revise_content] created new cv_output version={new_version} "
        f"for application_id={application_id}"
    )

    return {
        "cv_output": revised_cv_output,
        "cv_version": new_version,
    }


@with_retry
async def apply_user_revisions(state: CVAgentState) -> dict:
    """
    Node 11: Handle user-driven revision (Jalur B).

    Triggered when user requests revision for a specific section during CV review.
    No iteration limit — user can revise as many times as needed.

    Reads user_revision_instructions from state to know which sections to revise
    and what changes are requested. Produces new cv_output version.

    In Phase 6: calls Revision Handler + Content Writer Agent for requested sections,
    running them in parallel using asyncio.gather.

    Input  : state.user_revision_instructions, state.cv_output, state.cv_version
    Output : state.cv_output (new version), state.cv_version (incremented)
    """
    application_id = state["application_id"]
    new_version = state["cv_version"] + 1

    # Ambil section keys yang diminta user untuk direvisi
    # user_revision_instructions: { "experience": "tambahkan angka spesifik", ... }
    revision_keys = list(state.get("user_revision_instructions", {}).keys())

    logger.info(
        f"[apply_user_revisions] called for application_id={application_id}, "
        f"sections={revision_keys}, new_cv_version={new_version}"
    )

    supabase = get_supabase()

    # TODO Phase 6: Replace with real user-driven Revision Handler call
    # from agents.cluster4.revision_handler import run_user_revision
    # revised_sections = await run_user_revision(
    #     application_id,
    #     state["user_revision_instructions"],
    #     state["cv_output"],
    #     state["strategy_brief"],
    # )
    # Merge revised sections back into cv_output

    # ── Copy cv_output lama dan tambahkan revision note ───────────────────────
    revised_cv_output = {
        **state["cv_output"],
        "_revision_note": f"User-driven revision stub — sections: {revision_keys}",
        "version": new_version,
    }

    # ── Tentukan section_revised ───────────────────────────────────────────────
    # Real implementation merevisi satu section per request
    # Ambil key pertama dari revision instructions sebagai section yang direvisi
    # Kalau tidak ada instruksi (edge case), set ke "unknown"
    section_revised = revision_keys[0] if revision_keys else "unknown"

    # ── Simpan versi baru ke cv_outputs ───────────────────────────────────────
    supabase.table("cv_outputs").insert({
        "application_id": application_id,
        "version": new_version,
        "content": revised_cv_output,
        "revision_type": "user_driven",
        "section_revised": section_revised,  # section spesifik yang direvisi user
        "status": "draft",
    }).execute()

    # ── Catat di revision_history ─────────────────────────────────────────────
    supabase.table("revision_history").insert({
        "application_id": application_id,
        "revision_type": "user_driven",
        "iteration": 1,     # user-driven tidak punya iteration counter
        "sections": {
            "note": f"User-driven revision stub",
            "sections_requested": revision_keys,
            "instructions": state.get("user_revision_instructions", {}),
        },
        "status": "completed",
    }).execute()

    logger.info(
        f"[apply_user_revisions] created new cv_output version={new_version} "
        f"for application_id={application_id}, section_revised={section_revised}"
    )

    return {
        "cv_output": revised_cv_output,
        "cv_version": new_version,
    }


# ══════════════════════════════════════════════════════════════════════════════
# BEST VERSION SELECTION
# Node: select_best_version
# Dipanggil ketika MAX_QC_ITERATIONS habis dan masih ada section yang gagal
# Ini adalah SATU-SATUNYA node yang fully implemented di Phase 5 — tidak ada stub
# Logicnya murni deterministik (DB query + kalkulasi), tidak butuh LLM
# ══════════════════════════════════════════════════════════════════════════════

async def select_best_version(state: CVAgentState) -> dict:
    """
    Node: Select the best CV version when MAX_QC_ITERATIONS is exhausted.

    Instead of presenting the last version (which may not be the best due to
    oscillation between ATS and Semantic scores), this node finds the version
    with the highest average combined_score across all sections.

    combined_score per section = (ats_score × weight_ats) + (semantic_score × weight_semantic)
    Best version = cv_version with highest AVERAGE combined_score across all its sections.

    This node is FULLY IMPLEMENTED in Phase 5 — no stub, no LLM calls.
    Pure deterministic logic: DB queries + arithmetic.

    Input  : state.application_id (to query qc_results and cv_outputs)
    Output : state.cv_output (best version content), state.cv_version (best version number)
    """
    application_id = state["application_id"]
    logger.info(
        f"[select_best_version] called for application_id={application_id} "
        f"— MAX_QC_ITERATIONS reached, selecting best version"
    )

    supabase = get_supabase()

    # ── Query semua QC results untuk application ini ───────────────────────────
    # Butuh combined_score per section per version untuk menghitung rata-rata
    qc_response = (
        supabase.table("qc_results")
        .select("cv_version, combined_score")
        .eq("application_id", application_id)
        .execute()
    )

    if not qc_response.data:
        # Edge case: tidak ada QC data — fallback ke cv_version saat ini
        logger.warning(
            f"[select_best_version] no qc_results found for application_id={application_id}, "
            f"falling back to current cv_version={state['cv_version']}"
        )
        return {
            "cv_output": state["cv_output"],
            "cv_version": state["cv_version"],
        }

    # ── Hitung average combined_score per cv_version ───────────────────────────
    # Struktur: { cv_version: [score1, score2, ...] }
    version_scores: dict[int, list[float]] = {}

    for row in qc_response.data:
        version = row["cv_version"]
        score = row["combined_score"] or 0.0   # None → 0.0 kalau combined_score belum dihitung

        if version not in version_scores:
            version_scores[version] = []
        version_scores[version].append(score)

    # Hitung rata-rata per version
    # { cv_version: average_combined_score }
    version_averages = {
        version: sum(scores) / len(scores)
        for version, scores in version_scores.items()
    }

    # ── Pilih version dengan average combined_score tertinggi ─────────────────
    best_version = max(version_averages, key=lambda v: version_averages[v])
    best_score = version_averages[best_version]

    logger.info(
        f"[select_best_version] version scores: {version_averages} | "
        f"selected version={best_version} with avg_combined_score={best_score:.2f}"
    )

    # ── Query cv_outputs untuk mendapatkan content dari best version ───────────
    cv_response = (
        supabase.table("cv_outputs")
        .select("content")
        .eq("application_id", application_id)
        .eq("version", best_version)
        .limit(1)
        .execute()
    )

    if not cv_response.data:
        # Edge case: version ada di qc_results tapi tidak ada di cv_outputs
        # Ini seharusnya tidak terjadi — log error dan fallback ke current version
        logger.error(
            f"[select_best_version] cv_output for best_version={best_version} "
            f"not found in DB — falling back to current cv_version={state['cv_version']}"
        )
        return {
            "cv_output": state["cv_output"],
            "cv_version": state["cv_version"],
        }

    best_cv_output = cv_response.data[0]["content"]

    logger.info(
        f"[select_best_version] selected cv_version={best_version} "
        f"(avg_combined_score={best_score:.2f}) to present to user"
    )

    # Return best version — bukan versi terakhir
    return {
        "cv_output": best_cv_output,
        "cv_version": best_version,
    }


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT RENDERER
# Node: render_document
# Node TERAKHIR dalam workflow
# Di Phase 7 akan memanggil Document Renderer (WeasyPrint + python-docx)
# untuk mengkonversi cv_output JSON → PDF + DOCX → upload ke Supabase Storage
# ══════════════════════════════════════════════════════════════════════════════

async def render_document(state: CVAgentState) -> dict:
    """
    Node 12 (Final): Render CV output to PDF and DOCX files.

    Takes the final approved cv_output JSON and converts it to downloadable files.
    Updates cv_outputs status to "final" to mark completion.
    Stores the file path in state for the frontend to use as download URL.

    In Phase 7: calls Document Renderer which runs WeasyPrint (PDF) and
    python-docx (DOCX), uploads both to Supabase Storage, returns storage paths.

    Input  : state.cv_output, state.cv_version, state.application_id
    Output : state.final_output_path
    External: Document Renderer (pure code — no LLM calls)
    """
    application_id = state["application_id"]
    cv_version = state["cv_version"]

    logger.info(
        f"[render_document] called for application_id={application_id}, "
        f"cv_version={cv_version} — this is the final node"
    )

    supabase = get_supabase()

    # TODO Phase 7: Replace with real Document Renderer call
    # from renderer.document_renderer import render_and_upload
    # result = await render_and_upload(state["cv_output"], application_id, cv_version)
    # pdf_path = result["pdf_path"]
    # docx_path = result["docx_path"]

    # ── Placeholder path ───────────────────────────────────────────────────────
    # Format mengikuti konvensi yang akan dipakai di Phase 7:
    # {application_id}/cv_v{version}.pdf
    # Path ini disimpan di state dan akan dipakai oleh GET /applications/{id}/download
    placeholder_path = f"storage/placeholder/{application_id}/cv_v{cv_version}.pdf"

    # ── Update status cv_outputs ke "final" ───────────────────────────────────
    # Menandai bahwa versi ini sudah dirender dan siap didownload
    # GET /applications/{id}/download akan query dengan filter status="final"
    # Update hanya row dengan cv_version yang sesuai — bukan semua versi
    supabase.table("cv_outputs").update({
        "status": "final",
    }).eq("application_id", application_id).eq("version", cv_version).execute()

    logger.info(
        f"[render_document] workflow complete — "
        f"final_output_path={placeholder_path}, "
        f"cv_outputs status updated to 'final' for version={cv_version}"
    )

    # Return final_output_path — disimpan di state sebagai hasil akhir workflow
    return {"final_output_path": placeholder_path}