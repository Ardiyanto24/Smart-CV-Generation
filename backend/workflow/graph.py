# cv-agent/backend/workflow/graph.py

"""
LangGraph graph assembly untuk CV Agent workflow.

File ini menghubungkan semua komponen:
- Nodes dari workflow/nodes.py
- Edge conditions dari workflow/edges.py
- State schema dari workflow/state.py
- Checkpoint mechanism (MemorySaver untuk development)

Hasil: satu compiled graph yang siap dijalankan via workflow/service.py
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from workflow.edges import after_cv_review, after_gap_review, check_qc_result
from workflow.nodes import (
    analyze_gap,
    apply_user_revisions,
    generate_content,
    parse_jd_jr,
    plan_strategy,
    qc_evaluate,
    render_document,
    revise_content,
    score_gap,
    select_best_version,
    select_content,
)
from workflow.state import CVAgentState


# ── Interrupt Node Wrappers ───────────────────────────────────────────────────
# LangGraph interrupt() harus dipanggil di dalam node function, bukan sebagai edge.
# Kita buat thin wrapper node yang hanya bertugas pause workflow dan
# menunggu resume dari user. Setelah resume, edge condition menentukan
# node berikutnya berdasarkan keputusan user.

async def user_gap_review(state: CVAgentState) -> dict:
    """
    Interrupt 1 — Pause setelah score_gap.
    Menampilkan gap analysis report ke user.
    Menunggu user memutuskan: lanjut generate CV atau kembali update profil.

    Resume via: POST /applications/{id}/resume
    Body: { "action": "proceed" | "go_back" }
    Setelah resume: after_gap_review edge menentukan routing
    """
    # interrupt() menyimpan state ke checkpoint dan pause workflow
    # Value yang di-pass ke interrupt() tersedia di frontend via /status endpoint
    interrupt({
        "type": "user_gap_review",
        "gap_analysis": state.get("gap_analysis_context"),
        "score": state.get("gap_score"),
    })
    # Tidak ada return — workflow pause di sini sampai di-resume
    return {}


async def user_brief_review(state: CVAgentState) -> dict:
    """
    Interrupt 2 — Pause setelah plan_strategy.
    Menampilkan CV Strategy Brief ke user untuk di-review dan di-adjust.
    Menunggu user approve brief (mungkin dengan adjustment di Zona Kuning/Hijau).

    Resume via: POST /applications/{id}/resume
    Body: { "action": "approve", "adjusted_brief": { ... } }
    Setelah resume: direct edge ke select_content (selalu lanjut)
    """
    interrupt({
        "type": "user_brief_review",
        "strategy_brief": state.get("strategy_brief"),
        "brief_id": state.get("brief_id"),
    })
    return {}


async def user_cv_review(state: CVAgentState) -> dict:
    """
    Interrupt 3 — Pause setelah QC selesai (semua iterasi).
    Menampilkan CV section per section dengan status QC ke user.
    Menunggu user approve setiap section atau minta revisi.

    Resume via: POST /applications/{id}/resume
    Body: {
        "action": "submit_review",
        "approvals": { "section_id": "approved" | "revision_requested" },
        "instructions": { "section_id": "instruksi revisi bebas" }
    }
    Setelah resume: after_cv_review edge menentukan routing
    """
    interrupt({
        "type": "user_cv_review",
        "cv_output": state.get("cv_output"),
        "qc_report": state.get("qc_report"),
        "cv_version": state.get("cv_version"),
    })
    return {}


# ── Graph Builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Build dan compile LangGraph graph untuk CV Agent workflow.

    Returns compiled graph yang siap dijalankan.
    Dipanggil sekali saat module di-import — hasilnya disimpan sebagai
    module-level variable `graph`.
    """
    # Inisialisasi StateGraph dengan CVAgentState sebagai schema
    builder = StateGraph(CVAgentState)

    # ── Daftarkan semua nodes ─────────────────────────────────────────────────
    # Node utama dari nodes.py
    builder.add_node("parse_jd_jr", parse_jd_jr)
    builder.add_node("analyze_gap", analyze_gap)
    builder.add_node("score_gap", score_gap)
    builder.add_node("plan_strategy", plan_strategy)
    builder.add_node("select_content", select_content)
    builder.add_node("generate_content", generate_content)
    builder.add_node("qc_evaluate", qc_evaluate)
    builder.add_node("revise_content", revise_content)
    builder.add_node("select_best_version", select_best_version)
    builder.add_node("apply_user_revisions", apply_user_revisions)
    builder.add_node("render_document", render_document)

    # Interrupt nodes — thin wrappers yang pause workflow menunggu user input
    builder.add_node("user_gap_review", user_gap_review)
    builder.add_node("user_brief_review", user_brief_review)
    builder.add_node("user_cv_review", user_cv_review)

    # ── Direct edges — selalu ke node yang sama ────────────────────────────────
    # START → parse_jd_jr: titik masuk workflow
    builder.add_edge(START, "parse_jd_jr")

    # Cluster 2 → Cluster 3
    builder.add_edge("parse_jd_jr", "analyze_gap")
    builder.add_edge("analyze_gap", "score_gap")

    # score_gap → Interrupt 1
    builder.add_edge("score_gap", "user_gap_review")

    # plan_strategy → Interrupt 2
    builder.add_edge("plan_strategy", "user_brief_review")

    # Interrupt 2 selalu lanjut ke select_content (tidak ada pilihan)
    builder.add_edge("user_brief_review", "select_content")

    # Cluster 4 → Cluster 5 → Cluster 6
    builder.add_edge("select_content", "generate_content")
    builder.add_edge("generate_content", "qc_evaluate")

    # Revisi QC loop kembali ke qc_evaluate untuk re-evaluasi
    builder.add_edge("revise_content", "qc_evaluate")

    # select_best_version → Interrupt 3 (setelah iterasi habis)
    builder.add_edge("select_best_version", "user_cv_review")

    # apply_user_revisions loop kembali ke user_cv_review
    # (user bisa revisi berkali-kali tanpa batas)
    builder.add_edge("apply_user_revisions", "user_cv_review")

    # render_document → END: workflow selesai
    builder.add_edge("render_document", END)

    # ── Conditional edges — routing dinamis berdasarkan state ─────────────────

    # Setelah Interrupt 1: routing berdasarkan user_proceed
    # True  → plan_strategy (lanjut ke planning phase)
    # False → END (user kembali update profil, workflow berakhir)
    builder.add_conditional_edges(
        "user_gap_review",
        after_gap_review,
        {
            "plan_strategy": "plan_strategy",
            END: END,
        },
    )

    # Setelah qc_evaluate: routing berdasarkan QC results dan iteration count
    # "revise_content"      → ada yang gagal, iterasi masih tersisa
    # "select_best_version" → ada yang gagal, iterasi habis
    # "user_cv_review"      → semua passed
    builder.add_conditional_edges(
        "qc_evaluate",
        check_qc_result,
        {
            "revise_content": "revise_content",
            "select_best_version": "select_best_version",
            "user_cv_review": "user_cv_review",
        },
    )

    # Setelah Interrupt 3: routing berdasarkan user section approvals
    # "render_document"      → semua section approved
    # "apply_user_revisions" → ada section yang minta revisi
    builder.add_conditional_edges(
        "user_cv_review",
        after_cv_review,
        {
            "render_document": "render_document",
            "apply_user_revisions": "apply_user_revisions",
        },
    )

    # ── Checkpoint ────────────────────────────────────────────────────────────
    # MemorySaver: menyimpan state di RAM — cepat untuk development
    # State hilang kalau server restart — acceptable di Phase 5
    #
    # TODO Production: Replace MemorySaver with a persistent checkpointer
    # (e.g., Supabase-backed or Redis-backed) before deployment.
    # Persistent checkpointer memastikan state survive server restart
    # dan memungkinkan resume workflow setelah downtime.
    checkpointer = MemorySaver()

    # Compile graph dengan checkpointer
    # thread_id (= application_id) dipakai sebagai checkpoint key —
    # memastikan setiap application punya state yang terpisah
    return builder.compile(checkpointer=checkpointer)


# ── Module-level graph instance ───────────────────────────────────────────────
# Dipanggil sekali saat module di-import
# Semua caller (workflow/service.py) menggunakan instance ini
graph = build_graph()