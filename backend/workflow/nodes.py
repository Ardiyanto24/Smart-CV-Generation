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

import asyncio
import logging
from datetime import datetime, timezone

from config import get_settings
from db.supabase import get_supabase
from workflow.state import CVAgentState
from workflow.retry import with_retry

from agents.cluster2.parser import run_parser
from agents.cluster3.gap_analyzer import fetch_master_data, run_gap_analyzer
from agents.cluster3.scoring import run_scoring
from agents.cluster4.planner import run_planner
from agents.cluster4.selection import run_selection
from agents.cluster4.revision_handler import run_qc_revision, run_user_revision
from agents.cluster5.content_writer import write_component_bullets
from agents.cluster5.skills_grouping import group_skills
from agents.cluster5.summary_writer import write_summary
from agents.cluster6.ats_scoring import run_ats_scoring
from agents.cluster6.semantic_reviewer import run_semantic_review
from agents.cluster6.qc_combiner import combine_qc_results

from renderer.document_renderer import render_and_upload

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

    # Panggil Planner Agent — generate CV Strategy Brief
    # Agent membaca gap_analysis_context + jd_jr_context dari state
    # dan menyimpan brief ke cv_strategy_briefs table (user_approved=false)
    # brief["brief_id"] sudah di-inject oleh agent dari DB insert response
    brief = await run_planner(
        application_id=application_id,
        gap_analysis_context=state["gap_analysis_context"],
        jd_jr_context=state["jd_jr_context"],
    )

    logger.info(
        f"[plan_strategy] brief generated: brief_id={brief.get('brief_id')}"
    )

    # Return dua field terpisah di state:
    # - strategy_brief: full brief dict (dibaca oleh Content Writer, Summary Writer)
    # - brief_id: UUID untuk relasi di selected_content_packages (dibaca oleh select_content)
    return {
        "strategy_brief": brief,
        "brief_id": brief["brief_id"],
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
    logger.info(f"[select_content] called for application_id={application_id}")

    supabase = get_supabase()

    # Pakai strategy_brief dari state — ini adalah versi yang sudah diapprove user
    # (mungkin sudah diadjust user di Interrupt 2 untuk Zona Kuning/Hijau)
    # Bukan re-fetch dari DB — state sudah punya versi terbaru
    strategy_brief = state["strategy_brief"]

    # Panggil Selection Agent — query, ranking, dan package assembly
    # Agent menyimpan package ke selected_content_packages table
    package = await run_selection(
        application_id=application_id,
        user_id=user_id,
        strategy_brief=strategy_brief,
    )

    logger.info(
        f"[select_content] content selected for application_id={application_id}"
    )

    return {"selected_content_package": package}


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
    settings = get_settings()
    selected_package = state["selected_content_package"]
    brief = selected_package["brief"]
    selected_content = selected_package["selected_content"]
    generated_at = datetime.now(timezone.utc).isoformat()

    # ── Phase 1: Pass-through assembly ────────────────────────────────────────
    # Query user data untuk header — name dan contact info
    user_response = (
        supabase.table("users")
        .select("full_name, email, phone, linkedin_url, github_url, portfolio_url")
        .eq("id", state["user_id"])
        .limit(1)
        .execute()
    )

    user_data = user_response.data[0] if user_response.data else {}

    header = {
        "name": user_data.get("full_name", ""),
        "email": user_data.get("email", ""),
        "phone": user_data.get("phone", ""),
        "linkedin": user_data.get("linkedin_url", ""),
        "github": user_data.get("github_url", ""),
        "portfolio": user_data.get("portfolio_url", ""),
    }

    # Pass-through metadata per komponen — tidak digenerate LLM
    # Dipakai untuk menyusun section structure sebelum bullets ditambahkan
    pass_through = {
        "experience": [
            {
                "entry_id": e.get("id"),
                "company":  e.get("company"),
                "role":     e.get("role"),
                "year":     e.get("year") or e.get("start_year", ""),
                "location": e.get("location", ""),
            }
            for e in selected_content.get("experience", [])
        ],
        "education": [
            {
                "entry_id":    e.get("id"),
                "institution": e.get("institution"),
                "degree":      e.get("degree"),
                "field":       e.get("field_of_study", ""),
                "year":        e.get("year") or e.get("start_year", ""),
                "location":    e.get("location", ""),
                "gpa":         e.get("gpa", ""),
            }
            for e in selected_content.get("education", [])
        ],
        "awards": [
            {
                "entry_id": e.get("id"),
                "title":    e.get("title"),
                "issuer":   e.get("issuer", ""),
                "year":     e.get("year", ""),
            }
            for e in selected_content.get("awards", [])
        ],
        "projects": [
            {
                "entry_id":   e.get("id"),
                "title":      e.get("title"),
                "github_url": e.get("github_url", ""),
                "tools":      e.get("tools", e.get("skills_used", [])),
            }
            for e in selected_content.get("projects", [])
        ],
        "organizations": [
            {
                "entry_id": e.get("id"),
                "name":     e.get("name"),
                "role":     e.get("role", ""),
                "year":     e.get("year") or e.get("start_year", ""),
            }
            for e in selected_content.get("organizations", [])
        ],
        "certificates": [
            {
                "name":   e.get("name"),
                "issuer": e.get("issuer", ""),
                "year":   e.get("year", ""),
            }
            for e in selected_content.get("certificates", [])
        ],
    }

    # ── Phase 2: Content generation ───────────────────────────────────────────
    # Sequential across components, parallel within each component
    # Urutan fixed: experience → education → awards → projects → organizations
    # Skills grouping dipanggil setelah komponen narasi selesai

    generated_bullets = {}

    for component in ["experience", "education", "awards", "projects", "organizations"]:
        entries = selected_content.get(component, [])
        if entries:
            results = await write_component_bullets(component, entries, brief)
            # Hasil adalah list of {entry_id, component, bullets}
            # Di-index by entry_id untuk merge mudah ke pass_through nanti
            generated_bullets[component] = {
                r["entry_id"]: r["bullets"]
                for r in results
            }
            logger.info(
                f"[generate_content] {component}: {len(results)} entries written"
            )
        else:
            generated_bullets[component] = {}

    # Skills grouping — dari selected_content skills list (flat objects)
    skills_list = selected_content.get("skills", [])
    skills_result = await group_skills(skills_list) if skills_list else {"skills_grouped": []}

    logger.info(
        f"[generate_content] skills grouped: "
        f"{len(skills_result.get('skills_grouped', []))} groups"
    )

    # ── Phase 3: Assemble sections untuk Summary Writer ───────────────────────
    # Build section dicts dengan bullets sudah di-merge ke pass_through metadata
    # Summary Writer butuh ini untuk menulis summary yang spesifik

    def merge_bullets(component_name: str) -> list:
        """Helper: merge pass_through metadata dengan generated bullets."""
        merged = []
        bullets_map = generated_bullets.get(component_name, {})
        for item in pass_through[component_name]:
            entry_id = item["entry_id"]
            merged.append({
                **item,
                "bullets": bullets_map.get(entry_id, []),
            })
        return merged

    assembled_sections = {
        "experience":    merge_bullets("experience"),
        "education":     merge_bullets("education"),
        "awards":        merge_bullets("awards"),
        "projects":      merge_bullets("projects"),
        "organizations": merge_bullets("organizations"),
    }

    # Summary Writer dipanggil terakhir — membaca seluruh assembled sections
    summary = await write_summary(
        cv_sections=assembled_sections,
        skills_grouped=skills_result,
        brief=brief,
    )

    logger.info("[generate_content] summary written")

    # ── Phase 4: Final assembly — Final Structured Output JSON ────────────────
    # Urutan section fixed sesuai cluster5_specification Section 8:
    # header → summary → experience → education → awards →
    # skills → projects → certificates → organizations

    cv_output = {
        "application_id": application_id,
        "version":        cv_version,
        "generated_at":   generated_at,

        # ── Header: pass-through dari users table ──────────────────────────────
        "header": header,

        # ── Summary: digenerate oleh Summary Writer (selalu terakhir) ─────────
        "summary": summary,

        # ── Experience: pass-through metadata + generated bullets ──────────────
        "experience": assembled_sections["experience"],

        # ── Education: pass-through metadata + generated bullets ───────────────
        "education": assembled_sections["education"],

        # ── Awards: pass-through metadata + generated bullets ──────────────────
        "awards": assembled_sections["awards"],

        # ── Skills: output dari Skills Grouping Agent ──────────────────────────
        "skills": skills_result,

        # ── Projects: pass-through metadata + generated bullets ────────────────
        "projects": assembled_sections["projects"],

        # ── Certificates: pass-through saja — tidak ada bullets ────────────────
        "certificates": pass_through["certificates"],

        # ── Organizations: pass-through metadata + generated bullets ───────────
        "organizations": assembled_sections["organizations"],
    }

    # ── Simpan ke cv_outputs table ────────────────────────────────────────────
    supabase.table("cv_outputs").insert({
        "application_id": application_id,
        "version":        cv_version,
        "content":        cv_output,
        "revision_type":  "initial",
        "section_revised": None,    # None = seluruh CV digenerate, bukan satu section
        "status":         "draft",
    }).execute()

    logger.info(
        f"[generate_content] cv_output saved: "
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
    settings = get_settings()
    cv_output = state["cv_output"]
    jd_jr_context = state["jd_jr_context"]
    strategy_brief = state["strategy_brief"]

    keyword_targets = strategy_brief.get("keyword_targets", [])
    job_requirements = jd_jr_context.get("job_requirements", [])
    narrative_instructions = strategy_brief.get("narrative_instructions", [])

    # ── Jalankan ATS Scoring dan Semantic Review secara paralel ───────────────
    # Dua agent independen — tidak ada dependency antar keduanya
    # asyncio.gather menjalankan keduanya serentak, bukan berurutan
    ats_result, semantic_results = await asyncio.gather(
        run_ats_scoring(cv_output, keyword_targets, job_requirements),
        run_semantic_review(cv_output, jd_jr_context, narrative_instructions),
    )

    logger.info(
        f"[qc_evaluate] both agents complete — "
        f"ats_score={ats_result.get('weighted_score')}, "
        f"semantic_sections={len(semantic_results)}"
    )

    # ── Gabungkan hasil kedua agent menjadi QC Report ─────────────────────────
    # combine_qc_results adalah pure logic — AND logic per section
    qc_report = combine_qc_results(
        ats_result=ats_result,
        semantic_results=semantic_results,
        cv_version=cv_version,
        qc_iteration=current_iteration,
        settings=settings,
    )

    # Inject application_id — combine_qc_results tidak punya akses ke state
    qc_report["application_id"] = application_id

    sections = qc_report["sections"]
    sections_passed = qc_report["sections_passed"]
    sections_failed = qc_report["sections_failed"]

    # ── Simpan satu row per section ke qc_results ─────────────────────────────
    # Dibutuhkan oleh GET /applications/{id}/qc endpoint
    # dan oleh select_best_version node untuk best version selection
    for section in sections:
        supabase.table("qc_results").insert({
            "application_id":  application_id,
            "cv_version":      cv_version,
            "iteration":       current_iteration,
            "section":         section["section"],
            "entry_id":        section["entry_id"],
            "ats_score":       section["ats_score"],
            "ats_status":      section["ats_status"],
            "semantic_score":  section["semantic_score"],
            "semantic_status": section["semantic_status"],
            "action_required": section["action_required"],
            "preserve":        section["preserve"],
            "revise":          section["revise"],
            "missed_keywords": section["missed_keywords"],
            "combined_score":  section["combined_score"],
        }).execute()

    # ── Simpan aggregate score ke qc_overall_scores ───────────────────────────
    supabase.table("qc_overall_scores").insert({
        "application_id":   application_id,
        "cv_version":       cv_version,
        "iteration":        current_iteration,
        "overall_ats_score": qc_report["overall_ats_score"],
        "sections_passed":  sections_passed,
        "sections_failed":  sections_failed,
    }).execute()

    # ── Update cv_outputs status kalau semua sections passed ──────────────────
    # status "qc_passed" menandakan CV siap ditampilkan ke user untuk review
    # Kalau ada section yang gagal, status tetap "draft" — akan di-revisi dulu
    if sections_failed == 0:
        supabase.table("cv_outputs").update({
            "status": "qc_passed",
        }).eq("application_id", application_id).eq("version", cv_version).execute()

        logger.info(
            f"[qc_evaluate] all sections passed — "
            f"cv_outputs status updated to 'qc_passed' for version={cv_version}"
        )

    logger.info(
        f"[qc_evaluate] QC complete: iteration={current_iteration}, "
        f"overall_ats={qc_report['overall_ats_score']}, "
        f"passed={sections_passed}, failed={sections_failed}"
    )

    return {
        "qc_report": qc_report,
        "qc_iteration": current_iteration,
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

    # Panggil Revision Handler — Jalur A QC-driven
    # Agent memproses semua failed sections secara paralel dengan asyncio.gather
    # Return Context Package 6 berisi revised_bullets per section
    revision_result = await run_qc_revision(
        application_id=application_id,
        qc_report=state["qc_report"],
        cv_output=state["cv_output"],
        strategy_brief=state["strategy_brief"],
    )

    # ── Merge revised bullets ke cv_output ────────────────────────────────────
    # Copy cv_output lama lalu update hanya sections yang direvisi
    # Sections yang tidak direvisi tetap tidak berubah
    revised_cv_output = {**state["cv_output"], "version": new_version}

    for section_data in revision_result.get("sections_to_revise", []):
        section_name = section_data["section"]
        entry_id = section_data.get("entry_id")
        revised_bullets = section_data.get("revised_bullets", [])

        section_content = revised_cv_output.get(section_name)
        if isinstance(section_content, list) and entry_id:
            # Update bullets pada entry yang spesifik by entry_id
            for entry in section_content:
                if entry.get("entry_id") == entry_id:
                    entry["bullets"] = revised_bullets
                    break
        elif isinstance(section_content, list) and section_content:
            # Kalau tidak ada entry_id spesifik, update entry pertama
            section_content[0]["bullets"] = revised_bullets
        elif section_name == "summary" and revised_bullets:
            revised_cv_output["summary"] = revised_bullets[0]

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
    supabase.table("revision_history").insert({
        "application_id": application_id,
        "revision_type": "qc_driven",
        "iteration": current_iteration,
        "sections": revision_result,
        "status": "completed",
    }).execute()

    logger.info(
        f"[revise_content] QC revision complete: version={new_version}, "
        f"sections_revised={len(revision_result.get('sections_to_revise', []))}"
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

    # Panggil Revision Handler — Jalur B user-driven
    # Agent memproses sections yang diminta user secara paralel
    # Return Context Package 6 berisi revised_bullets per section
    revision_result = await run_user_revision(
        application_id=application_id,
        user_instructions=state.get("user_revision_instructions", {}),
        cv_output=state["cv_output"],
        strategy_brief=state["strategy_brief"],
    )

    # ── Merge revised bullets ke cv_output ────────────────────────────────────
    # Copy cv_output lama lalu update hanya sections yang direvisi user
    revised_cv_output = {**state["cv_output"], "version": new_version}

    for section_data in revision_result.get("sections_to_revise", []):
        section_name = section_data["section"]
        entry_id = section_data.get("entry_id")
        revised_bullets = section_data.get("revised_bullets", [])

        section_content = revised_cv_output.get(section_name)
        if isinstance(section_content, list) and entry_id:
            for entry in section_content:
                if entry.get("entry_id") == entry_id:
                    entry["bullets"] = revised_bullets
                    break
        elif isinstance(section_content, list) and section_content:
            section_content[0]["bullets"] = revised_bullets
        elif section_name == "summary" and revised_bullets:
            revised_cv_output["summary"] = revised_bullets[0]

    # ── Tentukan section_revised — ambil key pertama sebagai label di DB ───────
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
        "sections": revision_result,
        "status": "completed",
    }).execute()

    logger.info(
        f"[apply_user_revisions] user revision complete: version={new_version}, "
        f"sections_revised={len(revision_result.get('sections_to_revise', []))}"
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
# ══════════════════════════════════════════════════════════════════════════════

async def render_document(state: CVAgentState) -> dict:
    """
    Node 12 (Final): Render CV output to PDF and DOCX files.

    Takes the final approved cv_output JSON and converts it to downloadable files.
    Uploads both PDF and DOCX to Supabase Storage via Document Renderer.
    Updates cv_outputs status to 'final' to mark completion.
    Stores the PDF path in state for the frontend to use as download URL.

    Input  : state.cv_output, state.cv_version, state.application_id
    Output : state.final_output_path
    External: Document Renderer (pure code — no LLM calls)
    """
    from renderer.document_renderer import render_and_upload

    application_id = state["application_id"]
    cv_version = state["cv_version"]

    logger.info(
        f"[render_document] called for application_id={application_id}, "
        f"cv_version={cv_version} — this is the final node"
    )

    supabase = get_supabase()

    # ── Render PDF + DOCX dan upload ke Supabase Storage ─────────────────────
    # render_and_upload mengorkestrasi: render_pdf → render_docx →
    # upload PDF → upload DOCX secara sekuensial.
    result = await render_and_upload(
        cv_output=state["cv_output"],
        application_id=application_id,
        cv_version=cv_version,
    )

    pdf_path = result["pdf_path"]
    docx_path = result["docx_path"]

    # ── Update status cv_outputs ke "final" ───────────────────────────────────
    # Menandai bahwa versi ini sudah dirender dan siap didownload.
    # GET /applications/{id}/download akan query dengan filter status="final".
    # Update hanya row dengan cv_version yang sesuai — bukan semua versi.
    supabase.table("cv_outputs").update({
        "status": "final",
    }).eq("application_id", application_id).eq("version", cv_version).execute()

    logger.info(
        f"[render_document] workflow complete — "
        f"pdf_path={pdf_path}, docx_path={docx_path}, "
        f"cv_outputs status updated to 'final' for version={cv_version}"
    )

    return {"final_output_path": pdf_path}