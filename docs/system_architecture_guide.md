# Personalized CV Generation Agent
## System Architecture Guide

Dokumen ini adalah panduan utama sistem. Baca dokumen ini terlebih dahulu untuk memahami gambaran besar arsitektur, kemudian buka file spesifikasi cluster yang relevan untuk detail implementasi.

---

## Daftar Dokumen Spesifikasi

| File | Deskripsi |
|---|---|
| `cluster1_specification.md` | Knowledge Management — Master Data, Profile Ingestion Agent |
| `cluster2_specification.md` | Job Analyzer — Parser Agent, JD/JR DB |
| `cluster3_specification.md` | Gap Analyzer — Gap Analyzer Agent, Scoring Agent |
| `cluster4_specification.md` | Orchestrator — Planner Agent, Selection Agent, Revision Handler |
| `cluster5_specification.md` | CV Generator — Content Writer, Skills Grouping, Summary Writer |
| `cluster6_specification.md` | Quality Control — ATS Scoring Agent, Semantic Reviewer Agent |

---

## 1. Gambaran Sistem

Sistem ini terdiri dari dua lapisan utama:

**Lapisan 1 — Sistem Agent (6 Cluster)**
Otak utama sistem. Seluruh proses yang melibatkan LLM call terjadi di sini. Setiap cluster punya tanggung jawab yang terpisah dan tidak boleh dilanggar.

**Lapisan 2 — Infrastruktur Luar Sistem Agent**
Komponen pendukung yang menghubungkan sistem agent dengan user dan dunia luar. Tidak ada LLM call di lapisan ini kecuali Document Renderer yang memang pure code.

### Enam Cluster dan Tanggung Jawabnya

```
CLUSTER 1 — Knowledge Management
Tanggung jawab : Menyimpan dan memproses kompetensi user (Master Data)
Berjalan       : Setup awal + setiap kali user update profil
Agent          : Profile Ingestion Agent
Output         : Master Data DB

CLUSTER 2 — Job Analyzer
Tanggung jawab : Memproses JD/JR perusahaan menjadi atomic items
Berjalan       : Setiap kali user input JD/JR untuk satu lamaran
Agent          : Parser Agent
Output         : job_descriptions DB + job_requirements DB

CLUSTER 3 — Gap Analyzer
Tanggung jawab : Menganalisis gap antara JD/JR dengan Master Data
Berjalan       : Setelah Cluster 2 selesai
Agent          : Gap Analyzer Agent → Scoring Agent (sekuensial)
Output         : gap_analysis_results DB + gap_analysis_scores DB

CLUSTER 4 — Orchestrator
Tanggung jawab : Satu-satunya cluster yang membuat keputusan strategis
Berjalan       : Setelah user approve dari Cluster 3, dan setiap siklus revisi
Agent          : Planner Agent → Selection Agent (sekuensial)
                 Revision Handler (saat menerima feedback dari Cluster 6)
Output         : cv_strategy_briefs DB + selected_content_packages DB

CLUSTER 5 — CV Generator
Tanggung jawab : Mengeksekusi instruksi dari Cluster 4 menjadi konten CV
Berjalan       : Setelah Cluster 4 selesai, dan setiap siklus revisi
Agent          : Content Writer Agent (paralel per komponen)
                 → Skills Grouping Agent
                 → Summary Writer Agent (sekuensial)
Output         : cv_outputs DB (Final Structured Output JSON)

CLUSTER 6 — Quality Control
Tanggung jawab : Mengevaluasi kualitas CV dari dua dimensi
Berjalan       : Setelah Cluster 5 selesai, setiap iterasi
Agent          : ATS Scoring Agent + Semantic Reviewer Agent (paralel)
Output         : qc_results DB → QC Report ke Cluster 4
```

### Aturan Antar Cluster

```
Cluster 1 : Tidak memanggil cluster lain. Hanya menyimpan data.
Cluster 2 : Tidak memanggil cluster lain. Hanya menyimpan data.
Cluster 3 : Membaca dari Cluster 1 dan Cluster 2. Tidak menulis ke cluster lain.
Cluster 4 : Satu-satunya yang boleh membuat keputusan strategis.
            Memanggil Cluster 5 (planning dan revision).
            Menerima feedback dari Cluster 6.
Cluster 5 : Pure executor. Menerima instruksi dari Cluster 4.
            Tidak pernah membuat keputusan.
Cluster 6 : Pure evaluator. Mengirim QC Report ke Cluster 4.
            Tidak pernah mengubah konten CV secara langsung.
```

---

## 2. Full System Flow

```
USER INPUT PROFIL (Cluster 1)
User isi form kompetensi
        ↓
Profile Ingestion Agent
        ↓
Master Data DB
        ↓
[User approve inferred skills]
        ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USER INPUT JD/JR (Cluster 2)
User input Job Description + Job Requirements
        ↓
Parser Agent — dekomposisi + deteksi priority
        ↓
job_descriptions DB + job_requirements DB
        ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GAP ANALYSIS (Cluster 3)
Gap Analyzer Agent
(baca Master Data + JD/JR DB, analisis per item, dua dimensi JD & JR)
        ↓
Scoring Agent
(kalkulasi deterministik + LLM as a Judge)
        ↓
[INTERRUPT] Laporan Gap + Skor ditampilkan ke user
User putuskan: Lanjut Generate CV / Kembali Update Profil
        ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ORCHESTRATION — Planning Phase (Cluster 4)
Planner Agent
(baca Gap Analysis + JD/JR → generate CV Strategy Brief)
        ↓
[INTERRUPT] Brief + Suggestion Cards ditampilkan ke user
User: adjust Zona Hijau/Kuning, approve/ubah/tolak narrative instructions
        ↓
Selection Agent
(pilih top-N entry per komponen berdasarkan Brief)
        ↓
Selected Content Package
        ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CV GENERATION (Cluster 5)
Content Writer Agent — paralel per komponen, sekuensial antar komponen
Experience → Education → Awards → Projects → Organizations
        ↓
Skills Grouping Agent
        ↓
Summary Writer Agent
        ↓
Final Structured Output (JSON) → cv_outputs DB
        ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUALITY CONTROL (Cluster 6)
ATS Scoring Agent + Semantic Reviewer Agent (paralel)
        ↓
QC Report (action_required per section)
        ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ORCHESTRATION — Revision Phase (Cluster 4)
Ada section gagal QC?
├── Ya  → Jalur A: instruksi revisi ke Cluster 5 (section bermasalah, paralel)
│         kembali ke Cluster 6 untuk QC ulang
│         ulangi sampai lolos ATAU MAX_QC_ITERATIONS habis
│         (iterasi habis → ambil versi combined score tertinggi)
└── Tidak → lanjut ke user review
        ↓
[INTERRUPT] CV ditampilkan ke user section per section
User review:
├── Approve → lanjut
└── Minta revisi → Jalur B: user ketik instruksi bebas
                   Cluster 5 regenerate section tersebut
        ↓
Semua section approved
        ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DOCUMENT RENDERING (luar sistem agent)
Final Structured Output (JSON)
        ↓
Document Renderer (pure code — python-docx + WeasyPrint)
        ↓
PDF / DOCX → disimpan ke Supabase Storage
        ↓
User download via signed URL
```

---

## 3. Entity Relationship Diagram (ERD)

Seluruh tabel sistem beserta relasinya. Tabel dikelompokkan per cluster yang memilikinya.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLUSTER 1 — Master Data
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

users
├── id UUID PK
├── name VARCHAR
├── email VARCHAR UNIQUE
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

education
├── id UUID PK
├── user_id UUID FK → users.id
├── institution VARCHAR
├── degree VARCHAR
├── field_of_study VARCHAR
├── start_date DATE
├── end_date DATE
├── is_current BOOLEAN
├── what_i_did TEXT[]
├── challenge TEXT[]
├── impact TEXT[]
├── skills_used TEXT[]
├── is_inferred BOOLEAN
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

experience
├── id UUID PK
├── user_id UUID FK → users.id
├── company VARCHAR
├── role VARCHAR
├── start_date DATE
├── end_date DATE
├── is_current BOOLEAN
├── what_i_did TEXT[]
├── challenge TEXT[]
├── impact TEXT[]
├── skills_used TEXT[]
├── is_inferred BOOLEAN
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

projects
├── id UUID PK
├── user_id UUID FK → users.id
├── title VARCHAR
├── url VARCHAR
├── start_date DATE
├── end_date DATE
├── what_i_did TEXT[]
├── challenge TEXT[]
├── impact TEXT[]
├── skills_used TEXT[]
├── is_inferred BOOLEAN
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

awards
├── id UUID PK
├── user_id UUID FK → users.id
├── title VARCHAR
├── issuer VARCHAR
├── date DATE
├── what_i_did TEXT[]
├── challenge TEXT[]
├── impact TEXT[]
├── skills_used TEXT[]
├── is_inferred BOOLEAN
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

organizations
├── id UUID PK
├── user_id UUID FK → users.id
├── name VARCHAR
├── role VARCHAR
├── start_date DATE
├── end_date DATE
├── is_current BOOLEAN
├── what_i_did TEXT[]
├── challenge TEXT[]
├── impact TEXT[]
├── skills_used TEXT[]
├── is_inferred BOOLEAN
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

certificates
├── id UUID PK
├── user_id UUID FK → users.id
├── name VARCHAR
├── issuer VARCHAR
├── issue_date DATE
├── expiry_date DATE
├── url VARCHAR
├── is_inferred BOOLEAN
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

skills
├── id UUID PK
├── user_id UUID FK → users.id
├── name VARCHAR
├── category VARCHAR  [technical | soft | tool]
├── is_inferred BOOLEAN
├── source TEXT
├── created_at TIMESTAMP
└── updated_at TIMESTAMP
     UNIQUE(user_id, name)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLUSTER 2 — Job Analyzer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

applications                              ← anchor seluruh sistem per lamaran
├── id UUID PK
├── user_id UUID FK → users.id
├── company_name VARCHAR
├── position VARCHAR
├── status VARCHAR  [draft|applied|interview|offer|rejected|accepted]
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

job_postings                              ← raw input JD/JR
├── id UUID PK
├── application_id UUID FK → applications.id
├── jd_raw TEXT
├── jr_raw TEXT
└── created_at TIMESTAMP

job_descriptions                          ← hasil parsing JD
├── id UUID PK
├── application_id UUID FK → applications.id
├── responsibility_id VARCHAR
├── text TEXT
└── created_at TIMESTAMP

job_requirements                          ← hasil parsing JR
├── id UUID PK
├── application_id UUID FK → applications.id
├── requirement_id VARCHAR
├── text TEXT
├── source VARCHAR  [JD | JR | JD+JR]
├── priority VARCHAR  [must | nice_to_have]
└── created_at TIMESTAMP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLUSTER 3 — Gap Analyzer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

gap_analysis_results
├── id UUID PK
├── application_id UUID FK → applications.id
├── item_id VARCHAR
├── text TEXT
├── dimension VARCHAR  [JD | JR]
├── category VARCHAR  [exact_match | implicit_match | gap]
├── priority VARCHAR  [must | nice_to_have]
├── evidence JSONB
├── reasoning TEXT
├── suggestion TEXT
└── created_at TIMESTAMP

gap_analysis_scores
├── id UUID PK
├── application_id UUID FK → applications.id
├── quantitative_score NUMERIC
├── verdict VARCHAR  [sangat_cocok | cukup_cocok | kurang_cocok]
├── strength TEXT
├── concern TEXT
├── recommendation TEXT
├── proceed_recommendation VARCHAR  [lanjut | tinjau]
└── created_at TIMESTAMP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLUSTER 4 — Orchestrator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cv_strategy_briefs
├── id UUID PK
├── application_id UUID FK → applications.id
├── content_instructions JSONB
├── narrative_instructions JSONB
├── keyword_targets TEXT[]
├── primary_angle TEXT
├── summary_hook_direction TEXT
├── tone VARCHAR  [technical_concise | professional_formal | professional_conversational]
├── user_approved BOOLEAN
├── created_at TIMESTAMP
└── updated_at TIMESTAMP

selected_content_packages
├── id UUID PK
├── application_id UUID FK → applications.id
├── brief_id UUID FK → cv_strategy_briefs.id
├── content JSONB
└── created_at TIMESTAMP

revision_history
├── id UUID PK
├── application_id UUID FK → applications.id
├── revision_type VARCHAR  [qc_driven | user_driven]
├── iteration INTEGER
├── sections JSONB
├── status VARCHAR  [pending | completed | max_reached]
└── created_at TIMESTAMP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLUSTER 5 — CV Generator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cv_outputs
├── id UUID PK
├── application_id UUID FK → applications.id
├── version INTEGER
├── content JSONB                         ← Final Structured Output
├── revision_type VARCHAR  [initial | qc_driven | user_driven]
├── section_revised VARCHAR
├── status VARCHAR  [draft | qc_passed | user_approved | final]
└── created_at TIMESTAMP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLUSTER 6 — Quality Control
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

qc_results
├── id UUID PK
├── application_id UUID FK → applications.id
├── cv_version INTEGER
├── iteration INTEGER
├── section VARCHAR
├── entry_id UUID
├── ats_score NUMERIC
├── ats_status VARCHAR  [passed | failed]
├── semantic_score NUMERIC
├── semantic_status VARCHAR  [passed | failed]
├── action_required BOOLEAN
├── preserve JSONB
├── revise JSONB
├── missed_keywords TEXT[]
├── combined_score NUMERIC
└── created_at TIMESTAMP

qc_overall_scores
├── id UUID PK
├── application_id UUID FK → applications.id
├── cv_version INTEGER
├── iteration INTEGER
├── overall_ats_score NUMERIC
├── sections_passed INTEGER
├── sections_failed INTEGER
└── created_at TIMESTAMP
```

### Relasi Kunci

```
users (1) ──────────────────────── (N) semua tabel Master Data
users (1) ──────────────────────── (N) applications
applications (1) ───────────────── (N) job_postings
applications (1) ───────────────── (N) job_descriptions
applications (1) ───────────────── (N) job_requirements
applications (1) ───────────────── (N) gap_analysis_results
applications (1) ───────────────── (1) gap_analysis_scores
applications (1) ───────────────── (N) cv_strategy_briefs
applications (1) ───────────────── (N) selected_content_packages
applications (1) ───────────────── (N) revision_history
applications (1) ───────────────── (N) cv_outputs
applications (1) ───────────────── (N) qc_results
applications (1) ───────────────── (N) qc_overall_scores
cv_strategy_briefs (1) ─────────── (N) selected_content_packages
```

---

## 4. Shared Resources Antar Cluster

Beberapa DB dikonsumsi oleh lebih dari satu cluster:

```
Master Data DB
├── Ditulis oleh  : Cluster 1
└── Dibaca oleh   : Cluster 3, Cluster 4 (Selection Agent), Cluster 5 (pass-through)

JD/JR DB
├── Ditulis oleh  : Cluster 2
└── Dibaca oleh   : Cluster 3, Cluster 4 (Planner), Cluster 5 (Content Writer), Cluster 6

Gap Analysis DB
├── Ditulis oleh  : Cluster 3
└── Dibaca oleh   : Cluster 4 (Planner Agent)

Strategy DB
├── Ditulis oleh  : Cluster 4
└── Dibaca oleh   : Cluster 5, Cluster 6

CV Output DB
├── Ditulis oleh  : Cluster 5
└── Dibaca oleh   : Cluster 6

QC DB
├── Ditulis oleh  : Cluster 6
└── Dibaca oleh   : Cluster 4 (Revision Handler)
```

---

## 5. Context Package Specification

Antar cluster berkomunikasi via **context package** — output terstruktur yang sudah siap dikonsumsi cluster lain. Cluster penerima tidak perlu tahu schema DB cluster pengirim.

### Package 1 — Master Data Context (Cluster 1 → Cluster 3, 4, 5)

```json
{
  "user_id": "uuid",
  "components": {
    "experience": [
      {
        "entry_id": "uuid",
        "company": "string",
        "role": "string",
        "start_date": "date",
        "end_date": "date",
        "is_current": false,
        "what_i_did": ["string"],
        "challenge": ["string"],
        "impact": ["string"],
        "skills_used": ["string"],
        "is_inferred": false
      }
    ],
    "projects": [ ... ],
    "education": [ ... ],
    "awards": [ ... ],
    "organizations": [ ... ],
    "certificates": [ ... ],
    "skills": [ ... ]
  }
}
```

### Package 2 — JD/JR Context (Cluster 2 → Cluster 3, 4, 5, 6)

```json
{
  "application_id": "uuid",
  "job_descriptions": [
    { "responsibility_id": "d001", "text": "string" }
  ],
  "job_requirements": [
    { "requirement_id": "r001", "text": "string", "source": "JR", "priority": "must" }
  ]
}
```

### Package 3 — Gap Analysis Context (Cluster 3 → Cluster 4)

```json
{
  "application_id": "uuid",
  "results": [
    {
      "item_id": "r001",
      "text": "string",
      "dimension": "JR",
      "category": "exact_match",
      "priority": "must",
      "evidence": [ ... ],
      "reasoning": "string"
    }
  ],
  "score": {
    "quantitative_score": 72,
    "verdict": "cukup_cocok",
    "strength": "string",
    "concern": "string",
    "recommendation": "string"
  }
}
```

### Package 4 — Selected Content Package (Cluster 4 → Cluster 5)

```json
{
  "application_id": "uuid",
  "brief_id": "uuid",
  "brief": {
    "primary_angle": "string",
    "summary_hook_direction": "string",
    "keyword_targets": ["string"],
    "tone": "technical_concise",
    "narrative_instructions": [ ... ]
  },
  "selected_content": {
    "experience": [ { "entry_id": "uuid", "bullet_quota": 3, ... } ],
    "projects": [ ... ],
    "education": [ ... ],
    "awards": [ ... ],
    "organizations": [ ... ],
    "skills": [ ... ],
    "certificates": [ ... ]
  }
}
```

### Package 5 — QC Report (Cluster 6 → Cluster 4)

```json
{
  "application_id": "uuid",
  "cv_version": 2,
  "iteration": 1,
  "overall_ats_score": 78,
  "sections": [
    {
      "section": "experience",
      "entry_id": "uuid",
      "ats_score": 85,
      "ats_status": "passed",
      "semantic_score": 82,
      "semantic_status": "passed",
      "action_required": false,
      "preserve": ["string"],
      "revise": [],
      "missed_keywords": []
    }
  ]
}
```

### Package 6 — Revision Instructions (Cluster 4 → Cluster 5)

```json
{
  "application_id": "uuid",
  "revision_type": "qc_driven",
  "iteration": 2,
  "brief_reference": "uuid",
  "sections_to_revise": [
    {
      "section": "projects",
      "entry_id": "uuid",
      "preserve": ["string"],
      "instructions": "string",
      "user_instruction": null
    }
  ]
}
```

---

## 6. LangGraph Workflow Specification

### State Schema

State adalah objek yang dibawa sepanjang seluruh workflow. Setiap node membaca dan menulis ke state ini.

```python
class CVAgentState(TypedDict):
    # Identity
    user_id: str
    application_id: str

    # Cluster 2 output
    jd_jr_context: dict

    # Cluster 3 output
    gap_analysis_context: dict
    gap_score: dict
    user_proceed: bool                    # hasil keputusan user di interrupt C3

    # Cluster 4 output
    strategy_brief: dict
    user_brief_approved: bool             # hasil keputusan user di interrupt C4
    selected_content_package: dict

    # Cluster 5 output
    cv_output: dict
    cv_version: int

    # Cluster 6 output
    qc_report: dict
    qc_iteration: int                     # counter iterasi QC

    # Revision
    revision_type: str                    # qc_driven | user_driven
    user_section_approvals: dict          # { section_id: approved | revision_requested }
    user_revision_instructions: dict      # { section_id: "instruksi bebas user" }

    # Final
    final_output_path: str                # path file PDF/DOCX di Supabase Storage
```

### Node Definitions

```python
# Node 1: parse_jd_jr
# Input  : application_id
# Output : state.jd_jr_context
# Cluster: 2 — Parser Agent

# Node 2: analyze_gap
# Input  : state.jd_jr_context + Master Data DB
# Output : state.gap_analysis_context
# Cluster: 3 — Gap Analyzer Agent

# Node 3: score_gap
# Input  : state.gap_analysis_context
# Output : state.gap_score
# Cluster: 3 — Scoring Agent

# INTERRUPT 1: user_gap_review
# Tampilkan: gap_analysis_context + gap_score ke user
# Tunggu   : state.user_proceed (true = lanjut, false = kembali ke C1)

# Node 4: plan_strategy
# Input  : state.gap_analysis_context + state.jd_jr_context
# Output : state.strategy_brief (draft, belum approved)
# Cluster: 4 — Planner Agent

# INTERRUPT 2: user_brief_review
# Tampilkan: state.strategy_brief ke user
# Tunggu   : state.user_brief_approved + adjusted brief

# Node 5: select_content
# Input  : state.strategy_brief + Master Data DB
# Output : state.selected_content_package
# Cluster: 4 — Selection Agent

# Node 6: generate_content
# Input  : state.selected_content_package
# Output : state.cv_output (version 1)
# Cluster: 5 — Content Writer + Skills Grouping + Summary Writer

# Node 7: qc_evaluate
# Input  : state.cv_output + state.jd_jr_context
# Output : state.qc_report
# Cluster: 6 — ATS Scoring + Semantic Reviewer (paralel)

# Node 8: check_qc_result (conditional)
# Logic  :
#   if any section action_required AND qc_iteration < MAX_QC_ITERATIONS:
#     → revise_content
#   elif qc_iteration >= MAX_QC_ITERATIONS:
#     → select_best_version → user_cv_review
#   else:
#     → user_cv_review

# Node 9: revise_content
# Input  : state.qc_report + state.cv_output
# Output : state.cv_output (version N+1)
# Cluster: 4 Revision Handler + 5 Content Writer

# INTERRUPT 3: user_cv_review
# Tampilkan: state.cv_output per section dengan status QC
# Tunggu   : state.user_section_approvals + state.user_revision_instructions

# Node 10: check_user_approvals (conditional)
# Logic  :
#   if all sections approved:
#     → render_document
#   else:
#     → apply_user_revisions

# Node 11: apply_user_revisions
# Input  : state.user_revision_instructions + state.cv_output
# Output : state.cv_output (version N+1)
# Cluster: 4 Revision Handler + 5 Content Writer
# → kembali ke INTERRUPT 3

# Node 12: render_document
# Input  : state.cv_output (final version)
# Output : state.final_output_path
# Luar sistem agent — pure code
```

### Edge Conditions

```python
# Setelah INTERRUPT 1 (user_gap_review):
def after_gap_review(state):
    if state["user_proceed"]:
        return "plan_strategy"
    else:
        return END   # user kembali ke Cluster 1, workflow selesai

# Setelah qc_evaluate (check_qc_result):
def check_qc_result(state):
    has_failed = any(s["action_required"] for s in state["qc_report"]["sections"])
    if has_failed and state["qc_iteration"] < MAX_QC_ITERATIONS:
        return "revise_content"
    else:
        return "user_cv_review"   # iterasi habis → ambil best version

# Setelah INTERRUPT 3 (user_cv_review):
def after_cv_review(state):
    all_approved = all(
        v == "approved"
        for v in state["user_section_approvals"].values()
    )
    if all_approved:
        return "render_document"
    else:
        return "apply_user_revisions"
```

### Interrupt Points

LangGraph interrupt adalah mekanisme pause-resume workflow. Ada tiga interrupt dalam sistem ini:

```
INTERRUPT 1 — Gap Review
Terjadi di  : setelah score_gap
Resume via  : POST /applications/{id}/resume
              body: { "action": "proceed" | "go_back" }

INTERRUPT 2 — Brief Review
Terjadi di  : setelah plan_strategy
Resume via  : POST /applications/{id}/resume
              body: { "action": "approve", "adjusted_brief": { ... } }

INTERRUPT 3 — CV Review
Terjadi di  : setelah qc_evaluate (semua iterasi selesai)
Resume via  : POST /applications/{id}/resume
              body: {
                "action": "submit_review",
                "approvals": { "section_id": "approved" | "revision_requested" },
                "instructions": { "section_id": "instruksi revisi bebas" }
              }
```

---

## 7. Stack Teknologi

| Layer | Teknologi | Versi | Alasan |
|---|---|---|---|
| Frontend | Next.js | 14+ | React-based, SSR, App Router |
| Styling | Tailwind CSS | 3+ | Utility-first, cepat untuk solo developer |
| Backend | FastAPI | 0.100+ | Async Python, konsisten dengan LangGraph |
| Orchestration | LangGraph | latest | Stateful multi-agent, human-in-the-loop built-in |
| Database | Supabase (PostgreSQL) | latest | PostgreSQL + Auth + Storage satu platform |
| Auth | Supabase Auth | — | JWT, Row Level Security built-in |
| LLM | Anthropic Claude API | claude-sonnet-4-5 | Model utama semua LLM call |
| LLM Tracing | LangSmith | latest | Native integration dengan LangGraph |
| Error Tracking | Sentry | latest | Frontend + backend error monitoring |
| PDF Renderer | WeasyPrint | latest | HTML → PDF dengan styling presisi |
| DOCX Renderer | python-docx | latest | Generate file Word dari template |
| Template Engine | Jinja2 | latest | Render JSON ke HTML/DOCX template |
| Deployment FE | Vercel | — | Auto-deploy dari GitHub, gratis untuk solo |
| Deployment BE | Railway | — | FastAPI + LangGraph deployment mudah |
| File Storage | Supabase Storage | — | Simpan PDF/DOCX hasil render |
| Real-time Update | Server-Sent Events (SSE) | — | Stream progress LLM ke frontend |

---

## 8. API Endpoints

### Auth
```
POST   /auth/register          ← registrasi user baru
POST   /auth/login             ← login, return JWT
POST   /auth/logout            ← invalidate session
GET    /auth/me                ← get current user profile
```

### Cluster 1 — Master Data
```
GET    /profile/{component}           ← list semua entry komponen
POST   /profile/{component}           ← create entry baru
PUT    /profile/{component}/{id}      ← update entry
DELETE /profile/{component}/{id}      ← delete entry
GET    /profile/inferred-skills       ← list suggestion skills belum diapprove
POST   /profile/inferred-skills/batch ← approve/reject batch suggestions
```

`{component}` = education | experience | projects | awards | organizations | certificates | skills

### Cluster 2 — Job Input
```
POST   /applications                  ← create application baru
GET    /applications                  ← list semua lamaran user
GET    /applications/{id}             ← detail satu lamaran
DELETE /applications/{id}             ← hapus lamaran
```

### Workflow — Orchestration
```
POST   /applications/{id}/start       ← trigger workflow dari awal (Cluster 2)
POST   /applications/{id}/resume      ← resume setelah interrupt
GET    /applications/{id}/status      ← cek status workflow + node aktif saat ini
GET    /applications/{id}/stream      ← SSE endpoint untuk progress updates
```

### Data per Step
```
GET    /applications/{id}/gap         ← hasil Gap Analysis + Skor (Cluster 3)
GET    /applications/{id}/brief       ← CV Strategy Brief (Cluster 4)
GET    /applications/{id}/cv          ← Final Structured Output (Cluster 5)
GET    /applications/{id}/qc          ← QC Report per iterasi (Cluster 6)
```

### Output
```
POST   /applications/{id}/render      ← trigger Document Renderer
GET    /applications/{id}/download    ← get signed URL untuk download PDF/DOCX
```

### Tracking
```
PATCH  /applications/{id}/status      ← update status lamaran
```

---

## 9. Struktur Folder Project

```
cv-agent/
├── frontend/                          ← Next.js app
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── dashboard/
│   │   ├── profile/
│   │   └── apply/
│   │       ├── new/
│   │       └── [id]/
│   │           ├── gap/
│   │           ├── brief/
│   │           ├── cv/
│   │           └── download/
│   ├── components/
│   │   ├── ui/                        ← shared UI components
│   │   ├── profile/                   ← Cluster 1 components
│   │   ├── gap/                       ← Cluster 3 components
│   │   ├── brief/                     ← Cluster 4 components
│   │   └── cv/                        ← Cluster 5+6 components
│   └── lib/
│       ├── api.ts                     ← API client
│       └── supabase.ts                ← Supabase client
│
├── backend/                           ← FastAPI app
│   ├── main.py                        ← FastAPI entry point
│   ├── routers/
│   │   ├── auth.py
│   │   ├── profile.py
│   │   ├── applications.py
│   │   ├── workflow.py
│   │   └── output.py
│   ├── agents/                        ← semua LLM agent
│   │   ├── cluster1/
│   │   │   └── profile_ingestion.py
│   │   ├── cluster2/
│   │   │   └── parser.py
│   │   ├── cluster3/
│   │   │   ├── gap_analyzer.py
│   │   │   └── scoring.py
│   │   ├── cluster4/
│   │   │   ├── planner.py
│   │   │   ├── selection.py
│   │   │   └── revision_handler.py
│   │   ├── cluster5/
│   │   │   ├── content_writer.py
│   │   │   ├── skills_grouping.py
│   │   │   └── summary_writer.py
│   │   └── cluster6/
│   │       ├── ats_scoring.py
│   │       └── semantic_reviewer.py
│   ├── workflow/
│   │   ├── graph.py                   ← LangGraph graph definition
│   │   ├── state.py                   ← CVAgentState TypedDict
│   │   └── edges.py                   ← edge condition functions
│   ├── renderer/
│   │   ├── document_renderer.py       ← orchestrate PDF + DOCX generation
│   │   ├── pdf_renderer.py            ← WeasyPrint
│   │   ├── docx_renderer.py           ← python-docx
│   │   └── templates/
│   │       ├── cv_template.html       ← Jinja2 HTML template
│   │       └── cv_template.docx       ← Word template
│   ├── db/
│   │   ├── supabase.py                ← Supabase client
│   │   └── migrations/                ← SQL migration files
│   ├── models/                        ← Pydantic models
│   │   ├── profile.py
│   │   ├── application.py
│   │   └── cv_output.py
│   └── config.py                      ← environment variables + constants
│
└── docs/                              ← semua file spesifikasi
    ├── system_architecture_guide.md   ← dokumen ini
    ├── cluster1_specification.md
    ├── cluster2_specification.md
    ├── cluster3_specification.md
    ├── cluster4_specification.md
    ├── cluster5_specification.md
    └── cluster6_specification.md
```

---

## 10. Environment Variables

Semua environment variables yang dibutuhkan sistem. Simpan di file `.env` untuk lokal dan di platform deployment untuk production.

```bash
# ─── Anthropic ───────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ─── Supabase ────────────────────────────────────────
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...         # hanya di backend, jangan expose ke frontend

# ─── LangSmith ───────────────────────────────────────
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=cv-agent

# ─── Sentry ──────────────────────────────────────────
SENTRY_DSN_BACKEND=https://xxx@sentry.io/xxx
SENTRY_DSN_FRONTEND=https://xxx@sentry.io/xxx

# ─── App Config ──────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8000   # URL FastAPI backend
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...

# ─── Configurable Constants ──────────────────────────
MAX_QC_ITERATIONS=3
ATS_THRESHOLD=70
SEMANTIC_THRESHOLD=65
QC_COMBINED_WEIGHT_ATS=0.5
QC_COMBINED_WEIGHT_SEMANTIC=0.5

TOP_N_EXPERIENCE=3
TOP_N_PROJECTS=3
TOP_N_AWARDS=3
TOP_N_EDUCATION=2
TOP_N_ORGANIZATIONS=2
TOP_N_CERTIFICATES=5
TOP_N_SKILLS=15

SIGNED_URL_EXPIRY_SECONDS=3600           # 1 jam untuk download link
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=3
```

---

## 11. Security

### Row Level Security (RLS)

Setiap tabel di Supabase wajib mengaktifkan RLS. Policy dasarnya: user hanya bisa mengakses data miliknya sendiri.

```sql
-- Contoh policy untuk tabel experience
ALTER TABLE experience ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access own experience"
ON experience
FOR ALL
USING (auth.uid() = user_id);

-- Policy yang sama diterapkan ke semua tabel dengan kolom user_id:
-- education, projects, awards, organizations, certificates, skills

-- Untuk tabel yang FK ke applications (bukan langsung ke users):
CREATE POLICY "Users can only access own gap_analysis_results"
ON gap_analysis_results
FOR ALL
USING (
  application_id IN (
    SELECT id FROM applications WHERE user_id = auth.uid()
  )
);
```

Policy ini diterapkan ke **semua tabel** di semua cluster.

### API Key Management

```
ANTHROPIC_API_KEY     : hanya ada di backend (FastAPI), tidak pernah expose ke frontend
SUPABASE_SERVICE_ROLE : hanya ada di backend, tidak pernah expose ke frontend
SUPABASE_ANON_KEY     : boleh di frontend, tapi RLS memproteksi akses data
JWT Token             : disimpan di httpOnly cookie, bukan localStorage
```

### Rate Limiting

```python
# Di FastAPI menggunakan slowapi
from slowapi import Limiter

# Endpoint workflow dibatasi lebih ketat karena mahal secara LLM cost
@router.post("/applications/{id}/start")
@limiter.limit("5/hour")               # maksimal 5 workflow baru per jam per user

@router.post("/applications/{id}/resume")
@limiter.limit("30/hour")              # resume lebih sering karena user interaction
```

---

## 12. Error Handling

### Di LangGraph Workflow

```python
# Setiap node dibungkus dengan retry logic
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def call_llm(prompt):
    ...

# Jika semua retry gagal → simpan error state ke workflow
# LangGraph checkpoint memungkinkan resume dari node terakhir
# tanpa harus restart seluruh workflow dari awal
```

### Error States di Workflow

```
node_error    : satu node gagal, workflow pause, user dinotifikasi
                user bisa retry node tersebut
timeout_error : LLM tidak respond dalam LLM_TIMEOUT_SECONDS
                otomatis retry sesuai LLM_MAX_RETRIES
db_error      : rollback transaction, log ke Sentry, notifikasi user
```

### Di Frontend

```
Loading states   : setiap LLM call menampilkan progress message via SSE
                   "Gap Analyzer sedang membaca profil Anda..."
                   "Planner Agent sedang menyusun strategi CV..."
Error boundaries : setiap halaman punya React error boundary
                   error ditampilkan dengan opsi retry yang jelas
Offline handling : jika koneksi putus saat workflow berjalan,
                   frontend polling /applications/{id}/status
                   untuk resume tampilan saat koneksi kembali
```

---

## 13. Deployment Architecture

```
PRODUCTION ENVIRONMENT

User Browser
     ↕ HTTPS
Vercel (Next.js Frontend)
     ↕ HTTPS/API calls
Railway (FastAPI Backend)
     ↕
     ├── Supabase (PostgreSQL + Auth + Storage)
     ├── Anthropic API (LLM calls)
     └── LangSmith (tracing)

STAGING ENVIRONMENT
Identik dengan production tapi menggunakan:
- Supabase project terpisah
- LangSmith project terpisah (cv-agent-staging)
- Environment variables terpisah
```

### CI/CD Pipeline

```
GitHub Repository
     ↓
Push ke branch main
     ↓
GitHub Actions:
├── Run tests (pytest untuk backend, jest untuk frontend)
├── Lint check
└── Deploy:
    ├── Vercel auto-deploy frontend
    └── Railway auto-deploy backend
```

### Database Migrations

```
Setiap perubahan schema disimpan sebagai file SQL di backend/db/migrations/
Format nama file: YYYYMMDD_HHMMSS_description.sql
Contoh: 20260318_143000_add_skills_grouping_table.sql

Jalankan migration:
supabase db push   ← untuk Supabase hosted
```

---

## 14. Configurable Constants

Semua nilai berikut dapat diubah tanpa menyentuh logic agent. Diambil dari environment variables di `config.py`.

```
TOP_N_CONFIG
├── experience    : top_n = 3, bullets = 3
├── projects      : top_n = 3, bullets = 3
├── awards        : top_n = 3, bullets = 3
├── education     : top_n = 2 (configurable)
├── organizations : top_n = 2 (configurable)
├── certificates  : top_n = 5 (configurable)
└── skills        : top_n = 15 (configurable)

MAX_QC_ITERATIONS          : 3 (default)
ATS_THRESHOLD              : 70 (default)
SEMANTIC_THRESHOLD         : 65 (default)
QC_COMBINED_WEIGHT_ATS     : 0.5 (default)
QC_COMBINED_WEIGHT_SEMANTIC: 0.5 (default)
LLM_TIMEOUT_SECONDS        : 60 (default)
LLM_MAX_RETRIES            : 3 (default)
SIGNED_URL_EXPIRY_SECONDS  : 3600 (default)
```

---

## 15. Prinsip Desain Sistem

- **Single responsibility per cluster** — setiap cluster punya satu tanggung jawab yang tidak dilanggar cluster lain.
- **Cluster 4 adalah satu-satunya decision maker** — tidak ada cluster lain yang membuat keputusan strategis.
- **Komunikasi via context package** — cluster tidak query DB cluster lain secara langsung. Semua komunikasi via structured package.
- **User selalu punya kontrol** — setiap keputusan kritis memiliki user checkpoint sebelum sistem melanjutkan.
- **Preserve before revise** — setiap instruksi revisi selalu menyertakan apa yang harus dijaga, bukan hanya apa yang harus diubah.
- **Versioning setiap iterasi** — tidak ada data yang ditimpa. Setiap iterasi revisi menghasilkan versi baru.
- **Best version selection** — saat iterasi habis, sistem memilih versi terbaik berdasarkan combined score, bukan versi terakhir.
- **LLM hanya untuk reasoning** — kalkulasi deterministik tidak menggunakan LLM. LLM dipakai untuk hal yang benar-benar butuh reasoning.
- **Document Renderer di luar sistem agent** — rendering adalah pure code, tidak ada LLM call, tidak bisa berhalusinasi.
- **Security by default** — RLS aktif di semua tabel, API key tidak pernah expose ke frontend, JWT di httpOnly cookie.
