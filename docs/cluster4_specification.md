# Cluster 4 — Orchestrator
## Specification Document

---

## 1. Deskripsi

Cluster 4 adalah satu-satunya cluster yang boleh membuat keputusan strategis. Cluster lain hanya menyimpan data (Cluster 1, 2), menganalisis (Cluster 3), mengeksekusi (Cluster 5), atau mengevaluasi (Cluster 6). Semua keputusan tentang "apa yang harus dilakukan" ada di Cluster 4.

Cluster 4 bekerja di dua momen berbeda: **Planning** (awal, sebelum CV digenerate) dan **Revision** (setelah QC atau user meminta perubahan).

---

## 2. Komponen

| Komponen | Tipe | Deskripsi |
|---|---|---|
| Planner Agent | LLM Agent | Membuat CV Strategy Brief berdasarkan Gap Analysis |
| Selection Agent | LLM Agent | Memilih konten top-N dari Master Data berdasarkan Brief |
| Revision Handler | Logic/Orchestration | Menerima revisi dari Cluster 6 atau user, menginstruksi ulang Cluster 5 |
| Strategy DB | PostgreSQL | Menyimpan Brief, Selected Content Package, dan history revisi |

---

## 3. Flow — Planning Phase

```
Trigger: User klik "Lanjut Generate CV" di laporan Cluster 3
        ↓
Planner Agent
├── Baca gap_analysis_results (per application_id)
├── Baca gap_analysis_scores
├── Baca job_descriptions dan job_requirements dari JD/JR DB
└── Generate CV Strategy Brief
        ↓
Brief + Suggestion Cards ditampilkan ke user
User melakukan adjustment per zona:
├── Zona Hijau  → bebas diedit
├── Zona Kuning → adjust terbatas
└── Zona Merah  → read-only
        ↓
Brief final disimpan ke Strategy DB
        ↓
Selection Agent
├── Baca Brief final
├── Baca Master Data DB (per user_id)
└── Pilih top-N entry per komponen berdasarkan Brief
        ↓
Selected Content Package disimpan ke Strategy DB
        ↓
Trigger Cluster 5
```

---

## 4. Flow — Revision Phase

```
                    ┌─────────────────────────────┐
                    │     DUA JALUR REVISI         │
                    └─────────────────────────────┘

JALUR A — QC-Driven Revision
─────────────────────────────
Cluster 6 kirim Revisi Brief per section yang gagal QC
        ↓
Revision Handler
├── Cek iterasi saat ini < MAX_QC_ITERATIONS
├── Identifikasi section yang bermasalah
└── Generate instruksi revisi per section
        ↓
Instruksi dikirim ke Cluster 5
(hanya section yang bermasalah, secara paralel)
        ↓
Cluster 5 regenerate section tersebut
        ↓
Kembali ke Cluster 6 untuk QC ulang
        ↓
Jika iterasi habis → tetap lanjut ke user review
dengan catatan "section ini tidak lolos QC setelah N iterasi"

JALUR B — User-Driven Revision
────────────────────────────────
User tidak puas dengan narasi section tertentu
(terjadi setelah QC selesai, saat user review)
        ↓
User ketik instruksi revisi bebas:
"Tambahkan konteks bahwa project ini digunakan di production"
"Perkuat bagian impact dengan angka yang lebih spesifik"
        ↓
Revision Handler
└── Wrap instruksi user ke dalam format instruksi Cluster 5
        ↓
Instruksi dikirim ke Cluster 5
(hanya section yang diminta user)
        ↓
Cluster 5 regenerate section tersebut
        ↓
Ditampilkan kembali ke user
        ↓
User approve atau minta revisi lagi
(tidak ada batas iterasi untuk Jalur B)
```

---

## 5. Planner Agent — Spesifikasi

### Trigger
Dipanggil setelah user klik "Lanjut Generate CV" dari laporan Cluster 3.

### Input
- `gap_analysis_results` per `application_id`
- `gap_analysis_scores` per `application_id`
- `job_descriptions` per `application_id`
- `job_requirements` per `application_id`

### Output — CV Strategy Brief

Brief terdiri dari lima bagian dengan tingkat editabilitas berbeda untuk user.

#### Zona Merah — Read-only, tidak bisa diedit user
Dikendalikan penuh oleh agent. Mengubah ini akan merusak konsistensi dengan data di DB.

```json
"content_instructions": {
  "experience": {
    "include": ["uuid-exp-1", "uuid-exp-2"],
    "top_n": 3
  },
  "projects": {
    "include": ["uuid-proj-1", "uuid-proj-3"],
    "top_n": 3
  },
  "skills": {
    "include": ["Python", "SQL", "MySQL", "Scikit-learn"],
    "top_n": 10
  },
  "education": {
    "include": ["uuid-edu-1"],
    "top_n": 1
  }
}
```

#### Zona Kuning — Bisa diedit dengan batasan
User bisa menambah atau menghapus keyword, dan merespons setiap narrative instruction (setuju / ubah angle / tidak masukkan). Tidak boleh kosong.

```json
"keyword_targets": [
  "data pipeline", "dashboard", "stakeholder",
  "SQL", "Python", "Agile", "insight"
],

"narrative_instructions": [
  {
    "id": "ni-001",
    "type": "implicit_match",
    "requirement": "Pengalaman dengan GCP",
    "matched_with": "AWS experience di PT Maju Bersama",
    "suggested_angle": "Narrasikan sebagai cloud platform proficiency — user familiar dengan paradigma cloud (AWS), adaptasi ke GCP adalah learning curve yang manageable",
    "user_decision": null
  },
  {
    "id": "ni-002",
    "type": "gap_bridge",
    "requirement": "Familiar dengan metodologi Agile",
    "matched_with": null,
    "suggested_angle": "Narrasikan pengalaman kerja iteratif dan kolaboratif yang sejalan dengan prinsip Agile meskipun tidak eksplisit menggunakan label Agile",
    "user_decision": null
  }
]
```

User dapat merespons setiap `narrative_instruction` dengan tiga pilihan:
- `approved` — angle diterima, Content Writer mengeksekusi
- `adjusted` — user menulis angle versinya sendiri
- `rejected` — item ini tidak dimasukkan ke CV

#### Zona Hijau — Bebas diedit user
User bisa mengubah tanpa batasan. Tidak mempengaruhi logic Selection Agent.

```json
"primary_angle": "Data professional dengan background ML yang kuat, siap berkontribusi di analitik bisnis",

"summary_hook_direction": "Buka dengan posisi sebagai data professional yang menggabungkan kemampuan teknis ML dengan kemampuan komunikasi bisnis — ini yang membedakan dari kandidat teknis murni",

"tone": "technical_concise"
```

Pilihan tone yang tersedia: `technical_concise`, `professional_formal`, `professional_conversational`.

---

### UI — Suggestion Cards untuk Narrative Instructions

Setiap narrative instruction ditampilkan sebagai suggestion card:

```
┌─────────────────────────────────────────────────────┐
│ ⚡ Implicit Match — Cloud Platform                  │
│                                                      │
│ Perusahaan mensyaratkan : GCP experience             │
│ Yang Anda miliki        : AWS experience             │
│                                                      │
│ Suggested angle:                                     │
│ "Narrasikan sebagai cloud platform proficiency —     │
│  familiar dengan paradigma cloud (AWS), adaptasi ke  │
│  GCP adalah learning curve yang manageable"          │
│                                                      │
│ [✅ Setuju] [✏️ Ubah angle] [❌ Tidak masukkan]     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ❌ Gap Bridge — Agile Methodology                   │
│                                                      │
│ Perusahaan mensyaratkan : Familiar dengan Agile      │
│ Yang Anda miliki        : Tidak ditemukan            │
│                                                      │
│ Suggested angle:                                     │
│ "Narrasikan pengalaman kerja iteratif dan            │
│  kolaboratif yang sejalan dengan prinsip Agile"      │
│                                                      │
│ [✅ Setuju] [✏️ Ubah angle] [❌ Tidak masukkan]     │
└─────────────────────────────────────────────────────┘
```

---

## 6. Selection Agent — Spesifikasi

### Trigger
Dijalankan setelah user approve Brief final.

### Input
- Brief final (sudah divalidasi user) dari Strategy DB
- Master Data DB (per `user_id`)

### Proses
Untuk setiap komponen di `content_instructions`, Selection Agent:
1. Query Master Data untuk entry yang ada di list `include`
2. Rank berdasarkan relevansi terhadap `primary_angle` dan `keyword_targets`
3. Ambil top-N sesuai kuota di Brief

### Output — Selected Content Package

```json
{
  "application_id": "uuid-application",
  "selected_content": {
    "experience": [
      {
        "entry_id": "uuid-exp-1",
        "company": "PT Maju Bersama",
        "role": "Data Analyst Intern",
        "what_i_did": ["Membangun model klasifikasi churn", "..."],
        "challenge": ["Data sangat imbalanced", "..."],
        "impact": ["Akurasi naik 15%", "..."],
        "skills_used": ["Python", "MySQL", "..."],
        "bullet_quota": 3
      }
    ],
    "projects": [ ... ],
    "skills": [ ... ],
    "education": [ ... ]
  },
  "brief_reference": "uuid-brief"
}
```

---

## 7. Revision Handler — Spesifikasi

### Jalur A — QC-Driven Revision

**Trigger:** Cluster 6 mengirim Revisi Brief berisi section yang gagal QC.

**Stopping Criteria:**
```
MAX_QC_ITERATIONS = configurable constant (nilai default ditentukan nanti)
```

**Proses:**
```
Terima Revisi Brief dari Cluster 6
        ↓
Cek: current_iteration < MAX_QC_ITERATIONS?
├── Ya → generate instruksi revisi per section yang gagal
│         kirim ke Cluster 5 secara paralel
│         increment iteration counter
└── Tidak → tandai section sebagai "tidak lolos QC setelah N iterasi"
            lanjut ke user review dengan catatan
```

**Format instruksi ke Cluster 5:**
```json
{
  "revision_type": "qc_driven",
  "iteration": 2,
  "sections_to_revise": [
    {
      "section": "experience",
      "entry_id": "uuid-exp-1",
      "issues": [
        "Keyword 'data pipeline' belum muncul di bullet points",
        "Bullet point impact terlalu generik, perlu angka spesifik"
      ],
      "instructions": "Inject keyword 'data pipeline' secara natural di bullet 1. Perkuat bullet impact dengan metric yang ada di Master Data."
    }
  ]
}
```

---

### Jalur B — User-Driven Revision

**Trigger:** User tidak puas dengan narasi section tertentu setelah QC selesai.

**Stopping Criteria:** Tidak ada — user bebas revisi sampai puas.

**Proses:**
```
User ketik instruksi revisi bebas pada section tertentu
        ↓
Revision Handler wrap instruksi ke format standar
        ↓
Kirim ke Cluster 5 untuk section tersebut saja
        ↓
Hasil ditampilkan kembali ke user
```

**Format instruksi ke Cluster 5:**
```json
{
  "revision_type": "user_driven",
  "sections_to_revise": [
    {
      "section": "projects",
      "entry_id": "uuid-proj-1",
      "user_instruction": "Tambahkan konteks bahwa project ini digunakan di production dan diakses oleh lebih dari 500 pengguna aktif"
    }
  ]
}
```

---

## 8. Urutan Revision Phase

QC-driven revision harus selesai sebelum user bisa melakukan user-driven revision. Ini mencegah user merevisi narasi yang kemungkinan akan diubah lagi oleh QC.

```
Cluster 5 generate CV
        ↓
Cluster 6 QC (otomatis)
        ↓
Ada section gagal? → Jalur A (QC-driven, maks N iterasi)
        ↓
Semua section lolos QC atau iterasi habis
        ↓
CV ditampilkan ke user section per section dengan status:
├── ✅ QC Passed
├── 🔄 QC Passed after N iterations
└── ⚠️ QC tidak lolos setelah N iterasi — ditampilkan dengan catatan
        ↓
User review per section:
├── Approve → lanjut
└── Minta revisi → Jalur B (user-driven, bebas iterasi)
        ↓
Semua section approved user
        ↓
Final Structured Output → Document Renderer
```

---

## 9. Struktur Database

### Tabel `cv_strategy_briefs`
```sql
CREATE TABLE cv_strategy_briefs (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id         UUID REFERENCES applications(id) ON DELETE CASCADE,
  content_instructions   JSONB NOT NULL,
  narrative_instructions JSONB,
  keyword_targets        TEXT[],
  primary_angle          TEXT,
  summary_hook_direction TEXT,
  tone                   VARCHAR(30) DEFAULT 'technical_concise'
                         CHECK (tone IN ('technical_concise',
                                         'professional_formal',
                                         'professional_conversational')),
  user_approved          BOOLEAN DEFAULT FALSE,
  created_at             TIMESTAMP DEFAULT NOW(),
  updated_at             TIMESTAMP DEFAULT NOW()
);
```

### Tabel `selected_content_packages`
```sql
CREATE TABLE selected_content_packages (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
  brief_id       UUID REFERENCES cv_strategy_briefs(id),
  content        JSONB NOT NULL,
  created_at     TIMESTAMP DEFAULT NOW()
);
```

### Tabel `revision_history`
```sql
CREATE TABLE revision_history (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id  UUID REFERENCES applications(id) ON DELETE CASCADE,
  revision_type   VARCHAR(20) NOT NULL
                  CHECK (revision_type IN ('qc_driven', 'user_driven')),
  iteration       INTEGER DEFAULT 1,
  sections        JSONB NOT NULL,
  status          VARCHAR(20) DEFAULT 'pending'
                  CHECK (status IN ('pending', 'completed', 'max_reached')),
  created_at      TIMESTAMP DEFAULT NOW()
);
```

---

## 10. Konfigurasi

```
MAX_QC_ITERATIONS = configurable constant
  Nilai default: ditentukan saat implementasi
  Lokasi: environment variable atau config file
  Efek: membatasi jumlah iterasi otomatis QC-driven revision
```

---

## 11. Relasi dengan Cluster Lain

```
Input:
├── gap_analysis_results (Cluster 3) → dasar Planner Agent
├── gap_analysis_scores  (Cluster 3) → konteks skor untuk planning
├── job_descriptions     (Cluster 2) → keyword dan konteks JD
├── job_requirements     (Cluster 2) → keyword dan konteks JR
├── Master Data DB       (Cluster 1) → sumber konten untuk Selection Agent
└── Revisi Brief         (Cluster 6) → trigger Jalur A revision

Output:
├── Selected Content Package → Cluster 5 (planning phase)
└── Revision Instructions   → Cluster 5 (revision phase)
```

---

## 12. Prinsip Utama

- **Satu-satunya decision maker** — tidak ada cluster lain yang membuat keputusan strategis.
- **Brief adalah kontrak** — semua instruksi ke Cluster 5 mengacu pada Brief yang sudah divalidasi user.
- **Dua jalur revisi yang terpisah** — QC-driven (otomatis, ada batas) dan user-driven (manual, bebas iterasi).
- **QC selesai dulu, baru user review** — mencegah user merevisi narasi yang akan diubah QC.
- **Revisi hanya untuk section bermasalah** — tidak perlu regenerate seluruh CV untuk satu section yang perlu diperbaiki.
- **Transparency ke user** — status setiap section (QC passed, iterasi ke berapa, gagal QC) selalu ditampilkan.
