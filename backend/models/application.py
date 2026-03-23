# cv-agent/backend/models/application.py

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, model_validator


# ─── Application Status Enum ──────────────────────────────────────────────────
# Merepresentasikan lifecycle satu lamaran kerja
# draft → applied → interview → offer → accepted/rejected

class ApplicationStatus(str, Enum):
    draft = "draft"
    applied = "applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    accepted = "accepted"


# ─── APPLICATION ──────────────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    # Required — minimal info untuk membuat lamaran baru
    company_name: str
    position: str

    # Tidak ada field 'status' di sini — selalu default ke 'draft' di backend
    # User tidak boleh menentukan status saat create


class ApplicationResponse(BaseModel):
    # Semua kolom dari tabel applications
    id: UUID
    user_id: UUID
    company_name: str
    position: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationStatusUpdate(BaseModel):
    # Hanya untuk PATCH /applications/{id}/status
    # User hanya bisa mengubah status, tidak ada field lain
    status: ApplicationStatus


# ─── JOB POSTING ──────────────────────────────────────────────────────────────

class JobPostingCreate(BaseModel):
    # Keduanya optional secara individual...
    jd_raw: Optional[str] = None
    jr_raw: Optional[str] = None

    # ...tapi minimal satu harus ada
    # @model_validator dijalankan setelah semua field divalidasi
    @model_validator(mode="after")
    def at_least_one_must_be_present(self) -> "JobPostingCreate":
        if not self.jd_raw and not self.jr_raw:
            raise ValueError(
                "At least one of 'jd_raw' or 'jr_raw' must be provided"
            )
        return self


class JobPostingResponse(BaseModel):
    # Semua kolom dari tabel job_postings
    # Tidak ada updated_at — raw input bersifat immutable
    id: UUID
    application_id: UUID
    jd_raw: Optional[str] = None
    jr_raw: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── PARSED JD/JR (Read-only — dibuat oleh Parser Agent) ─────────────────────
# Tidak ada Create model untuk ini karena dibuat oleh agent, bukan user langsung

class JobRequirementResponse(BaseModel):
    # Hasil parsing JR — satu row = satu atomic requirement
    id: UUID
    application_id: UUID
    requirement_id: str      # short ID seperti "r001", "r002"
    text: str                # atomic requirement statement
    source: str              # "JD", "JR", atau "JD+JR"
    priority: str            # "must" atau "nice_to_have"

    class Config:
        from_attributes = True


class JobDescriptionResponse(BaseModel):
    # Hasil parsing JD — satu row = satu atomic responsibility
    id: UUID
    application_id: UUID
    responsibility_id: str   # short ID seperti "d001", "d002"
    text: str                # atomic responsibility statement

    class Config:
        from_attributes = True