# cv-agent/backend/models/cv_output.py

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


# ─── CV OUTPUT ────────────────────────────────────────────────────────────────
# Menyimpan hasil generation CV per versi
# content adalah JSONB — tidak divalidasi lebih lanjut oleh Pydantic
# karena strukturnya kompleks dan sudah divalidasi oleh agent

class CVOutputResponse(BaseModel):
    id: UUID
    application_id: UUID
    version: int                        # dimulai dari 1, naik setiap revisi
    content: Dict[str, Any]             # raw JSONB — Final Structured Output
    revision_type: Optional[str] = None # "initial", "qc_driven", "user_driven"
    section_revised: Optional[str] = None  # section mana yang direvisi, None = full CV
    status: str                         # "draft", "qc_passed", "user_approved", "final"
    created_at: datetime

    class Config:
        from_attributes = True


# ─── GAP ANALYSIS ─────────────────────────────────────────────────────────────

class GapAnalysisResultResponse(BaseModel):
    # Satu row = satu JD/JR item yang sudah dianalisis
    id: UUID
    item_id: str                        # referensi ke requirement_id atau responsibility_id
    text: str                           # teks requirement/responsibility asli
    dimension: str                      # "JD" atau "JR"
    category: str                       # "exact_match", "implicit_match", "gap"
    priority: Optional[str] = None      # "must" atau "nice_to_have"
    evidence: Optional[Dict[str, Any]] = None   # bukti match dari Master Data
    reasoning: Optional[str] = None     # penjelasan implicit match
    suggestion: Optional[str] = None    # saran untuk gap items

    class Config:
        from_attributes = True


class GapAnalysisScoreResponse(BaseModel):
    # Satu row per application — overall score dari Scoring Agent
    quantitative_score: float           # 0-100
    verdict: str                        # "sangat_cocok", "cukup_cocok", "kurang_cocok"
    strength: Optional[str] = None      # kekuatan kandidat
    concern: Optional[str] = None       # kekhawatiran/gap utama
    recommendation: Optional[str] = None
    proceed_recommendation: str         # "lanjut" atau "tinjau"

    class Config:
        from_attributes = True


class GapAnalysisFullResponse(BaseModel):
    # Composite model — ini yang dikembalikan oleh GET /applications/{id}/gap
    # Menggabungkan semua result items + satu score object
    results: List[GapAnalysisResultResponse]
    score: GapAnalysisScoreResponse


# ─── CV STRATEGY BRIEF ────────────────────────────────────────────────────────
# Output dari Planner Agent — "kontrak" yang mengatur seluruh CV generation

class CVStrategyBriefResponse(BaseModel):
    id: UUID
    content_instructions: Dict[str, Any]        # Zona Merah — read-only untuk user
    narrative_instructions: Optional[Dict[str, Any]] = None  # Zona Kuning
    keyword_targets: Optional[List[str]] = None  # Zona Kuning
    primary_angle: Optional[str] = None          # Zona Hijau
    summary_hook_direction: Optional[str] = None # Zona Hijau
    tone: str                                    # "technical_concise", dll
    user_approved: bool                          # sudah diapprove user atau belum

    class Config:
        from_attributes = True


# ─── QC RESULTS ───────────────────────────────────────────────────────────────
# Output dari Cluster 6 — evaluasi kualitas CV per section

class QCResultResponse(BaseModel):
    # Satu row = satu section CV pada satu iterasi QC
    section: str                                 # "experience", "projects", dll
    entry_id: Optional[UUID] = None              # None untuk section seperti "summary"
    ats_score: Optional[float] = None
    ats_status: Optional[str] = None             # "passed" atau "failed"
    semantic_score: Optional[float] = None
    semantic_status: Optional[str] = None        # "passed" atau "failed"
    action_required: bool                        # single source of truth untuk revisi
    preserve: Optional[List[str]] = None         # apa yang harus dijaga saat revisi
    revise: Optional[List[str]] = None           # apa yang harus diperbaiki
    missed_keywords: Optional[List[str]] = None  # keyword yang tidak ditemukan

    class Config:
        from_attributes = True


class QCReportResponse(BaseModel):
    # Composite model — ini yang dikembalikan oleh GET /applications/{id}/qc
    cv_version: int
    iteration: int
    overall_ats_score: Optional[float] = None
    sections: List[QCResultResponse]