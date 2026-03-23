# cv-agent/backend/workflow/service.py

"""
Service layer antara FastAPI routers dan LangGraph graph.

Routers tidak boleh import graph secara langsung — semua interaksi
dengan LangGraph dilakukan melalui fungsi-fungsi di module ini.

Keuntungan:
- Routers tetap bersih dari LangGraph implementation details
- Mudah mengganti implementasi workflow tanpa menyentuh routers
- Logic validasi dan state building terpusat di satu tempat
"""

import json
import logging
from typing import AsyncGenerator

from workflow.graph import graph
from db.supabase import get_supabase

logger = logging.getLogger("workflow.service")


async def start_workflow(application_id: str, user_id: str) -> dict:
    """
    Mulai workflow CV generation dari awal untuk satu application.

    Memvalidasi bahwa application ada dan milik user, membangun initial state,
    lalu menjalankan graph sampai interrupt pertama (user_gap_review).

    Args:
        application_id: UUID application yang akan diproses
        user_id: UUID user yang memiliki application

    Returns:
        dict dengan status "interrupted" dan interrupt_type "user_gap_review"

    Raises:
        ValueError: jika application tidak ditemukan atau bukan milik user
    """
    supabase = get_supabase()

    # Validasi application exist dan milik user ini
    # Kalau tidak ada → ValueError (bukan HTTP error — caller yang handle)
    response = (
        supabase.table("applications")
        .select("id")
        .eq("id", application_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not response.data:
        raise ValueError("Application not found")

    logger.info(
        f"[start_workflow] starting workflow for "
        f"application_id={application_id}, user_id={user_id}"
    )

    # ── Build initial state ───────────────────────────────────────────────────
    # Hanya user_id, application_id, cv_version, dan qc_iteration yang non-None
    # Field lain akan diisi oleh masing-masing node saat dijalankan
    initial_state = {
        "user_id": user_id,
        "application_id": application_id,
        "cv_version": 1,        # dimulai dari versi 1
        "qc_iteration": 0,      # belum ada QC yang berjalan
        # Semua field lain None — akan diisi oleh nodes
        "jd_jr_context": None,
        "gap_analysis_context": None,
        "gap_score": None,
        "user_proceed": None,
        "strategy_brief": None,
        "brief_id": None,
        "user_brief_approved": None,
        "selected_content_package": None,
        "cv_output": None,
        "qc_report": None,
        "revision_type": None,
        "user_section_approvals": None,
        "user_revision_instructions": None,
        "final_output_path": None,
    }

    # ── Invoke graph ──────────────────────────────────────────────────────────
    # thread_id = application_id memastikan setiap application punya
    # checkpoint state yang terpisah di MemorySaver
    # Graph berjalan sampai interrupt pertama (user_gap_review setelah score_gap)
    # lalu pause dan return
    await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": application_id}},
    )

    logger.info(
        f"[start_workflow] workflow reached first interrupt (user_gap_review) "
        f"for application_id={application_id}"
    )

    return {
        "status": "interrupted",
        "interrupt_type": "user_gap_review",
        "application_id": application_id,
    }


async def resume_workflow(application_id: str, resume_payload: dict) -> dict:
    """
    Resume workflow yang sedang pause di interrupt point.

    Menentukan interrupt mana yang sedang di-resume dari action field,
    membangun state update yang sesuai, lalu melanjutkan graph execution.

    Args:
        application_id: UUID application yang workflownya di-resume
        resume_payload: dict berisi "action" dan data tambahan per action type

    Returns:
        dict dengan status "resumed" dan action yang dieksekusi

    Valid actions:
        "proceed"       → user setuju lanjut setelah melihat gap analysis
        "go_back"       → user ingin kembali update profil
        "approve"       → user approve strategy brief (mungkin dengan adjustment)
        "submit_review" → user submit section approvals setelah CV review
    """
    action = resume_payload.get("action")

    logger.info(
        f"[resume_workflow] resuming application_id={application_id} "
        f"with action={action}"
    )

    # ── Build state update berdasarkan action ─────────────────────────────────
    # Setiap action hanya mengupdate field yang relevan
    # LangGraph merge partial update ke full state secara otomatis

    if action == "proceed":
        # Interrupt 1 — user klik "Lanjut Generate CV"
        # after_gap_review edge akan routing ke plan_strategy
        state_update = {"user_proceed": True}

    elif action == "go_back":
        # Interrupt 1 — user klik "Kembali Update Profil"
        # after_gap_review edge akan routing ke END
        state_update = {"user_proceed": False}

    elif action == "approve":
        # Interrupt 2 — user approve strategy brief
        # Kalau ada adjusted_brief, merge ke strategy_brief yang sudah ada
        state_update = {"user_brief_approved": True}

        if "adjusted_brief" in resume_payload and resume_payload["adjusted_brief"]:
            # Ambil strategy_brief yang ada di checkpoint state
            current_state = graph.get_state(
                config={"configurable": {"thread_id": application_id}}
            )
            existing_brief = current_state.values.get("strategy_brief", {}) or {}

            # Merge adjusted_brief ke atas existing_brief
            # Key dari adjusted_brief akan override key yang sama di existing_brief
            merged_brief = {**existing_brief, **resume_payload["adjusted_brief"]}
            state_update["strategy_brief"] = merged_brief

    elif action == "submit_review":
        # Interrupt 3 — user submit section approvals dan revision instructions
        # after_cv_review edge akan routing berdasarkan isi approvals
        state_update = {
            "user_section_approvals": resume_payload.get("approvals", {}),
            "user_revision_instructions": resume_payload.get("instructions", {}),
        }

    else:
        # Action tidak dikenal — caller sudah validasi ini, tapi defensive check
        raise ValueError(f"Invalid action: {action}")

    # ── Inject state update ke checkpoint ────────────────────────────────────
    # aupdate_state menulis state_update ke checkpoint tanpa menjalankan graph
    # Ini "mengisi formulir" sebelum workflow dilanjutkan
    await graph.aupdate_state(
        config={"configurable": {"thread_id": application_id}},
        values=state_update,
    )

    # ── Resume graph dari checkpoint ──────────────────────────────────────────
    # ainvoke(None) = lanjutkan dari state yang ada di checkpoint
    # Graph berjalan sampai interrupt berikutnya atau END
    await graph.ainvoke(
        None,
        config={"configurable": {"thread_id": application_id}},
    )

    logger.info(
        f"[resume_workflow] workflow resumed successfully "
        f"for application_id={application_id}, action={action}"
    )

    return {
        "status": "resumed",
        "action": action,
        "application_id": application_id,
    }


async def get_workflow_status(application_id: str) -> dict:
    """
    Baca status workflow saat ini dari checkpoint.

    Dipakai frontend untuk polling progress selama workflow berjalan,
    dan untuk menentukan halaman apa yang harus ditampilkan.

    Args:
        application_id: UUID application yang status-nya ingin dibaca

    Returns:
        dict dengan status, current_interrupt, cv_version, dan qc_iteration
    """
    # Baca state dari checkpoint — tidak menjalankan graph
    snapshot = graph.get_state(
        config={"configurable": {"thread_id": application_id}}
    )

    # Kalau belum ada state → workflow belum dimulai
    if not snapshot or not snapshot.values:
        return {"status": "not_started"}

    state_values = snapshot.values

    # ── Tentukan status dari field `next` di snapshot ─────────────────────────
    # snapshot.next berisi list node yang akan dijalankan berikutnya
    # - Kosong ([]) → workflow sudah selesai (END)
    # - Berisi interrupt node name → workflow pause menunggu user
    # - Berisi regular node name → workflow sedang berjalan

    next_nodes = snapshot.next or []

    # Interrupt node names yang kita definisikan di graph.py
    interrupt_nodes = {"user_gap_review", "user_brief_review", "user_cv_review"}

    if not next_nodes:
        # Tidak ada next node → workflow sudah complete
        status = "completed"
        current_interrupt = None

    elif any(node in interrupt_nodes for node in next_nodes):
        # Next node adalah interrupt → workflow pause menunggu user
        status = "interrupted"
        # Ambil nama interrupt node yang pertama
        current_interrupt = next(
            node for node in next_nodes if node in interrupt_nodes
        )

    else:
        # Next node adalah regular node → workflow sedang berjalan
        status = "running"
        current_interrupt = None

    return {
        "status": status,
        "current_interrupt": current_interrupt,
        "cv_version": state_values.get("cv_version", 1),
        "qc_iteration": state_values.get("qc_iteration", 0),
    }


async def stream_workflow_events(application_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator yang stream LangGraph events sebagai Server-Sent Events.

    Dipakai oleh GET /applications/{id}/stream endpoint untuk real-time
    progress updates ke frontend. Frontend subscribe ke stream ini dan
    menampilkan node yang sedang berjalan ke user.

    Hanya yield events "on_chain_start" dan "on_chain_end" — filter event
    internal LangGraph yang terlalu granular dan tidak berguna untuk UI.

    Args:
        application_id: UUID application yang events-nya di-stream

    Yields:
        SSE-formatted string: "data: {json}\n\n"
        JSON berisi: { "event": event_type, "node": node_name }
    """
    logger.info(
        f"[stream_workflow_events] starting SSE stream "
        f"for application_id={application_id}"
    )

    # astream_events menghasilkan semua internal LangGraph events
    # version="v2" adalah format event terbaru dari LangGraph
    async for event in graph.astream_events(
        None,   # None = lanjutkan dari checkpoint yang ada
        config={"configurable": {"thread_id": application_id}},
        version="v2",
    ):
        event_type = event.get("event", "")
        node_name = event.get("name", "")

        # Filter — hanya yield events yang berguna untuk UI
        # on_chain_start → node mulai dijalankan
        # on_chain_end   → node selesai dijalankan
        # Event lain (on_chat_model_stream, on_tool_start, dll) terlalu granular
        if event_type not in ("on_chain_start", "on_chain_end"):
            continue

        # Skip event untuk graph-level chain (bukan individual node)
        # Biasanya ditandai dengan nama yang sama dengan graph name atau kosong
        if not node_name or node_name == "LangGraph":
            continue

        # Format sebagai SSE — "data: {json}\n\n" adalah format standar SSE
        # Frontend membaca ini via EventSource API
        sse_data = json.dumps({
            "event": event_type,
            "node": node_name,
        })
        yield f"data: {sse_data}\n\n"

    logger.info(
        f"[stream_workflow_events] SSE stream ended "
        f"for application_id={application_id}"
    )