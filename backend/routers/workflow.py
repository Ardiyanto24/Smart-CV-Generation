# cv-agent/backend/routers/workflow.py

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from db.auth import get_current_user
from db.limiter import limiter
from db.supabase import get_supabase
from models.application import JobPostingCreate
from models.cv_output import (
    CVOutputResponse,
    CVStrategyBriefResponse,
    GapAnalysisFullResponse,
    GapAnalysisResultResponse,
    GapAnalysisScoreResponse,
    QCReportResponse,
    QCResultResponse,
)
from workflow.service import start_workflow as _start_workflow
from workflow.service import resume_workflow as _resume_workflow
from workflow.service import get_workflow_status as _get_workflow_status
from workflow.service import stream_workflow_events as _stream_workflow_events

router = APIRouter(
    prefix="/applications",
    tags=["workflow"],
)


# ─── Helper: Verify Application Ownership ─────────────────────────────────────
# Versi workflow router dari ownership check
# Sengaja tidak di-share dengan applications.py — routers tidak saling import

async def verify_application_ownership(
    application_id: str,
    user_id: str,
) -> dict:
    """
    Verify that the given application exists and belongs to the user.
    Raises HTTP 404 if not found or not owned by the current user.
    Returns the application row if valid.
    """
    supabase = get_supabase()

    response = (
        supabase.table("applications")
        .select("*")
        .eq("id", application_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    return response.data[0]


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSTEP 4.2 — WORKFLOW CONTROL STUBS
# Endpoints ini akan diisi implementasinya di Phase 5
# ═══════════════════════════════════════════════════════════════════════════════

# ─── POST /applications/{id}/start ───────────────────────────────────────────
@router.post("/{id}/start", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
async def start_workflow(
    request: Request,
    id: str,
    data: JobPostingCreate,
    current_user=Depends(get_current_user),
):
    """
    Start the CV generation workflow for a given application.
    Saves raw JD/JR input, then triggers the LangGraph workflow.
    Workflow runs until Interrupt 1 (user_gap_review after score_gap).
    """
    # Ownership check
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()

    # Simpan raw JD/JR ke DB — dibutuhkan oleh parse_jd_jr node
    # Node tersebut akan membaca dari tabel ini saat workflow berjalan
    supabase.table("job_postings").insert({
        "application_id": id,
        "jd_raw": data.jd_raw,
        "jr_raw": data.jr_raw,
    }).execute()

    # Workflow started — graph will run until interrupt 1 (user_gap_review)
    # Graph menjalankan: parse_jd_jr → analyze_gap → score_gap → [INTERRUPT]
    result = await _start_workflow(
        application_id=id,
        user_id=str(current_user.id),
    )

    return result


# ─── POST /applications/{id}/resume ──────────────────────────────────────────
@router.post("/{id}/resume", status_code=status.HTTP_200_OK)
@limiter.limit("30/hour")
async def resume_workflow(
    request: Request,
    id: str,
    body: Dict[str, Any],
    current_user=Depends(get_current_user),
):
    """
    Resume a paused workflow after a user interrupt.

    Dipanggil setelah tiga interrupt berbeda:
    - Interrupt 1 (gap review)   : action = "proceed" | "go_back"
    - Interrupt 2 (brief review) : action = "approve" + optional "adjusted_brief"
    - Interrupt 3 (CV review)    : action = "submit_review" + "approvals" + "instructions"
    """
    # Ownership check — pastikan application milik user ini
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    # Validasi 1: "action" key harus ada di request body
    # Tanpa action, service tidak tahu interrupt mana yang di-resume
    if "action" not in body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request body must contain an 'action' field",
        )

    # Validasi 2: nilai action harus salah satu dari empat yang valid
    valid_actions = {"proceed", "go_back", "approve", "submit_review"}
    if body["action"] not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid action. Must be one of: proceed, go_back, approve, submit_review",
        )

    # Panggil service layer — semua business logic ada di sana
    result = await _resume_workflow(
        application_id=id,
        resume_payload=body,
    )

    return result


# ─── GET /applications/{id}/status ───────────────────────────────────────────
@router.get("/{id}/status", status_code=status.HTTP_200_OK)
async def get_workflow_status(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Get current workflow status for a given application.

    Dipakai frontend untuk polling progress selama workflow berjalan.
    Response menentukan halaman apa yang harus ditampilkan:
    - "running"     → tampilkan WorkflowProgress component
    - "interrupted" → fetch data relevan, tampilkan ke user
    - "completed"   → navigasi ke download page
    - "not_started" → workflow belum dimulai
    """
    # Ownership check
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    # Baca status dari LangGraph checkpoint — tidak menjalankan workflow
    result = await _get_workflow_status(application_id=id)

    return result


# ─── GET /applications/{id}/stream ───────────────────────────────────────────
@router.get("/{id}/stream")
async def stream_workflow_events(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    SSE stream untuk real-time workflow progress updates.

    Frontend subscribe ke endpoint ini menggunakan browser EventSource API.
    Server mengirim event setiap kali satu node selesai dijalankan.

    Event format: data: {"event": "on_chain_start"|"on_chain_end", "node": "node_name"}

    Headers khusus mencegah proxy buffering yang akan merusak real-time behavior.
    """
    # Ownership check
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    # StreamingResponse menerima async generator dan stream hasilnya ke client
    # media_type "text/event-stream" adalah MIME type standar untuk SSE
    return StreamingResponse(
        content=_stream_workflow_events(application_id=id),
        media_type="text/event-stream",
        headers={
            # Mencegah browser dan CDN cache SSE stream
            "Cache-Control": "no-cache",
            # Khusus untuk Nginx — matikan proxy buffering
            # Tanpa ini, Nginx akan buffer semua events sebelum dikirim ke client
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSTEP 4.3 — DATA READ ENDPOINTS
# Endpoints ini fully implemented di Phase 4 — membaca data hasil kerja agents
# ═══════════════════════════════════════════════════════════════════════════════

# ─── GET /applications/{id}/gap ───────────────────────────────────────────────
# Membaca hasil Gap Analysis — dikerjakan oleh Gap Analyzer Agent (Cluster 3)
# Menggabungkan dua query: gap_analysis_results (list) + gap_analysis_scores (skor)

@router.get("/{id}/gap", response_model=GapAnalysisFullResponse)
async def get_gap_analysis(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Return the full Gap Analysis report for an application.
    Combines gap result items (exact_match, implicit_match, gap) with the
    overall score from the Scoring Agent.
    """
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()

    # Query 1: semua gap result items, diurutkan by item_id
    results_response = (
        supabase.table("gap_analysis_results")
        .select("*")
        .eq("application_id", id)
        .order("item_id")
        .execute()
    )

    # Query 2: satu baris score per application
    score_response = (
        supabase.table("gap_analysis_scores")
        .select("*")
        .eq("application_id", id)
        .execute()
    )

    # Kedua query harus return data — kalau salah satu kosong, berarti
    # gap analysis belum dijalankan untuk application ini
    if not results_response.data or not score_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gap analysis not found for this application",
        )

    # Rakit GapAnalysisFullResponse dari dua query terpisah
    return GapAnalysisFullResponse(
        results=[GapAnalysisResultResponse(**item) for item in results_response.data],
        score=GapAnalysisScoreResponse(**score_response.data[0]),
    )


# ─── GET /applications/{id}/brief ─────────────────────────────────────────────
# Membaca CV Strategy Brief — dibuat oleh Planner Agent (Cluster 4)
# Mengambil versi terbaru (created_at descending)

@router.get("/{id}/brief", response_model=CVStrategyBriefResponse)
async def get_strategy_brief(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Return the CV Strategy Brief for an application.
    Returns the most recent brief if multiple versions exist.
    """
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()

    # Ambil brief terbaru — order by created_at desc, limit 1
    response = (
        supabase.table("cv_strategy_briefs")
        .select("*")
        .eq("application_id", id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy brief not found for this application",
        )

    return CVStrategyBriefResponse(**response.data[0])


# ─── GET /applications/{id}/cv ────────────────────────────────────────────────
# Membaca CV output terbaru — dibuat oleh Content Writer Agent (Cluster 5)
# Mengambil versi dengan version number tertinggi

@router.get("/{id}/cv", response_model=CVOutputResponse)
async def get_cv_output(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Return the latest CV output for an application.
    Returns the highest version number if multiple revisions exist.
    """
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()

    # Ambil CV output dengan version tertinggi
    # order by version desc, limit 1
    response = (
        supabase.table("cv_outputs")
        .select("*")
        .eq("application_id", id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV output not found for this application",
        )

    return CVOutputResponse(**response.data[0])


# ─── GET /applications/{id}/qc ────────────────────────────────────────────────
# Membaca QC Report terbaru — dibuat oleh ATS Scoring + Semantic Reviewer (Cluster 6)
# Butuh dua query: (1) cari run terbaru di qc_overall_scores,
#                  (2) fetch semua sections dari qc_results untuk run itu

@router.get("/{id}/qc", response_model=QCReportResponse)
async def get_qc_report(
    id: str,
    current_user=Depends(get_current_user),
):
    """
    Return the latest QC report for an application.
    Identifies the most recent QC run by highest cv_version + iteration,
    then fetches all section results for that run.
    """
    await verify_application_ownership(
        application_id=id,
        user_id=str(current_user.id),
    )

    supabase = get_supabase()

    # Query 1: cari QC run terbaru — tertinggi cv_version, lalu iteration
    overall_response = (
        supabase.table("qc_overall_scores")
        .select("*")
        .eq("application_id", id)
        .order("cv_version", desc=True)
        .order("iteration", desc=True)
        .limit(1)
        .execute()
    )

    if not overall_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QC report not found for this application",
        )

    latest = overall_response.data[0]
    cv_version = latest["cv_version"]
    iteration = latest["iteration"]

    # Query 2: fetch semua section results untuk run yang ditemukan di atas
    sections_response = (
        supabase.table("qc_results")
        .select("*")
        .eq("application_id", id)
        .eq("cv_version", cv_version)
        .eq("iteration", iteration)
        .execute()
    )

    # Rakit QCReportResponse
    return QCReportResponse(
        cv_version=cv_version,
        iteration=iteration,
        overall_ats_score=latest.get("overall_ats_score"),
        sections=[QCResultResponse(**s) for s in sections_response.data],
    )