# cv-agent/backend/models/profile.py

from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


# ─── Skill Category Enum ──────────────────────────────────────────────────────
# Dipakai oleh SkillCreate, SkillUpdate, SkillResponse, dan InferredSkillSuggestion
# Enum memastikan hanya tiga nilai yang valid: technical, soft, tool

class SkillCategory(str, Enum):
    technical = "technical"
    soft = "soft"
    tool = "tool"


# ─── EDUCATION ────────────────────────────────────────────────────────────────

class EducationCreate(BaseModel):
    # Required
    institution: str

    # Optional — user boleh tidak mengisi ini saat create
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = False

    # what_i_did, challenge, impact, skills_used TIDAK ada di sini
    # karena akan diisi oleh Profile Ingestion Agent setelah entry dibuat


class EducationUpdate(BaseModel):
    # Semua field optional — user hanya submit field yang ingin diubah
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None


class EducationResponse(BaseModel):
    # Semua kolom dari tabel education — termasuk yang di-generate sistem
    id: UUID
    user_id: UUID
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool
    what_i_did: Optional[List[str]] = None      # diisi agent
    challenge: Optional[List[str]] = None        # diisi agent
    impact: Optional[List[str]] = None           # diisi agent
    skills_used: Optional[List[str]] = None      # diisi agent
    is_inferred: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── EXPERIENCE ───────────────────────────────────────────────────────────────

class ExperienceCreate(BaseModel):
    # Required
    company: str
    role: str
    what_i_did: str  # user submit sebagai free-text, agent akan decompose jadi array

    # Optional
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = False


class ExperienceUpdate(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    what_i_did: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None


class ExperienceResponse(BaseModel):
    id: UUID
    user_id: UUID
    company: str
    role: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool
    what_i_did: Optional[List[str]] = None
    challenge: Optional[List[str]] = None
    impact: Optional[List[str]] = None
    skills_used: Optional[List[str]] = None
    is_inferred: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── PROJECTS ─────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    # Required
    title: str
    what_i_did: str  # free-text, agent akan decompose

    # Optional
    url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    what_i_did: Optional[str] = None
    url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    what_i_did: Optional[List[str]] = None
    challenge: Optional[List[str]] = None
    impact: Optional[List[str]] = None
    skills_used: Optional[List[str]] = None
    is_inferred: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── AWARDS ───────────────────────────────────────────────────────────────────

class AwardCreate(BaseModel):
    # Required
    title: str

    # Optional
    issuer: Optional[str] = None
    date: Optional[date] = None


class AwardUpdate(BaseModel):
    title: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[date] = None


class AwardResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    issuer: Optional[str] = None
    date: Optional[date] = None
    what_i_did: Optional[List[str]] = None
    challenge: Optional[List[str]] = None
    impact: Optional[List[str]] = None
    skills_used: Optional[List[str]] = None
    is_inferred: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── ORGANIZATIONS ────────────────────────────────────────────────────────────

class OrganizationCreate(BaseModel):
    # Required
    name: str

    # Optional
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = False


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None


class OrganizationResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool
    what_i_did: Optional[List[str]] = None
    challenge: Optional[List[str]] = None
    impact: Optional[List[str]] = None
    skills_used: Optional[List[str]] = None
    is_inferred: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── CERTIFICATES ─────────────────────────────────────────────────────────────
# Catatan: certificates TIDAK punya what_i_did, challenge, impact
# Ini hanya listing metadata — berbeda dari komponen lain

class CertificateCreate(BaseModel):
    # Required
    name: str

    # Optional
    issuer: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    url: Optional[str] = None


class CertificateUpdate(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    url: Optional[str] = None


class CertificateResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    issuer: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    url: Optional[str] = None
    is_inferred: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── SKILLS ───────────────────────────────────────────────────────────────────

class SkillCreate(BaseModel):
    # Required — category divalidasi via Enum, hanya menerima: technical, soft, tool
    name: str
    category: SkillCategory

    # Optional
    source: Optional[str] = None


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[SkillCategory] = None
    source: Optional[str] = None


class SkillResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    category: SkillCategory
    is_inferred: bool
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── INFERRED SKILLS (untuk suggestion UI) ───────────────────────────────────
# Model ini tidak terikat ke DB row — hanya dipakai untuk menampilkan
# suggestion dari Profile Ingestion Agent ke user

class InferredSkillSuggestion(BaseModel):
    name: str
    category: SkillCategory
    source: str  # penjelasan mengapa skill ini diinfer, contoh:
                 # "Random Forest usage implies scikit-learn in Python context"


class InferredSkillBatchRequest(BaseModel):
    # approved: skills yang user pilih untuk disimpan ke DB
    approved: List[InferredSkillSuggestion] = []
    # rejected: nama-nama skill yang user tolak (hanya nama, tidak perlu full object)
    rejected: List[str] = []