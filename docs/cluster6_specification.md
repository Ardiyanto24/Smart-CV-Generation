# Cluster 6 — Quality Control
## Specification Document

---

## 1. Deskripsi

Cluster 6 bertugas mengevaluasi kualitas CV yang dihasilkan Cluster 5 sebelum ditampilkan ke user. Evaluasi dilakukan dari dua dimensi secara paralel — ATS Scoring (teknis, keyword-based) dan Semantic Review (kesesuaian narasi dengan JD/JR). Output Cluster 6 adalah QC Report yang dikirim ke Cluster 4 (Orchestrator) sebagai dasar instruksi revisi.

Cluster 6 tidak mengubah konten CV secara langsung — tugasnya hanya mengevaluasi dan melaporkan. Semua keputusan revisi tetap ada di Cluster 4.

---

## 2. Komponen

| Komponen | Tipe | Deskripsi |
|---|---|---|
| ATS Scoring Agent | Kalkulasi + LLM | Menghitung skor ATS deterministik, LLM mengidentifikasi preserve items |
| Semantic Reviewer Agent | LLM Agent | Mengevaluasi kesesuaian narasi per section dengan JD/JR |
| QC DB | PostgreSQL | Menyimpan hasil QC per iterasi per section |

---

## 3. Flow

```
Trigger: Cluster 5 selesai menyimpan Final Structured Output ke CV Output DB
        ↓
ATS Scoring Agent          Semantic Reviewer Agent
(paralel)                  (paralel)
        ↓                          ↓
ATS Score + Preserve List  Semantic Score + Revise List per section
        ↓                          ↓
        └──────────┬───────────────┘
                   ↓
        Gabungkan hasil kedua agent
        Tentukan action_required per section
                   ↓
        Simpan ke QC DB
                   ↓
        Kirim QC Report ke Cluster 4
```

---

## 4. ATS Scoring Agent — Spesifikasi

### Pendekatan — Dua Tahap

**Tahap 1 — Kalkulasi Deterministik (bukan LLM)**

Menghitung skor ATS berdasarkan keyword matching antara konten CV dengan dua sumber keyword:
- `keyword_targets` dari CV Strategy Brief (Cluster 4)
- Atomic requirements dari `job_requirements` tabel (Cluster 2)

Formula:

```
ATS Score =
  (jumlah keyword ditemukan di CV) 
  ─────────────────────────────────── × 100
  (total keyword yang dicari)

Bobot per keyword:
- Keyword dari must requirements    : bobot 1.0
- Keyword dari nice_to_have         : bobot 0.5
- Keyword dari keyword_targets Brief: bobot 0.8
```

Pencarian keyword bersifat **case-insensitive** dan mendukung **partial match** untuk variasi kata (misalnya "machine learning" juga mencocokkan "ML").

**Tahap 2 — LLM sebagai Preserve Analyzer**

Setelah skor dihitung, LLM membaca CV dan hasil kalkulasi keyword matching untuk:
1. Mengidentifikasi elemen spesifik yang berkontribusi pada skor ATS (keyword, frasa, action verbs) → menjadi `preserve list`
2. Mengidentifikasi keyword yang seharusnya ada tapi tidak ditemukan → menjadi bagian dari `missed_keywords`

LLM di tahap ini **tidak mengubah skor** — hanya menginterpretasi hasil kalkulasi.

### Input

```json
{
  "cv_output": { ... },
  "keyword_targets": ["data pipeline", "predictive model", "Python", "SQL"],
  "job_requirements": [
    { "id": "r007", "text": "Menguasai Python", "priority": "must" },
    { "id": "r008", "text": "Menguasai SQL", "priority": "must" },
    { "id": "r012", "text": "Pengalaman AWS atau GCP", "priority": "nice_to_have" }
  ]
}
```

### Output

```json
{
  "ats_score": 78,
  "keyword_found": ["Python", "SQL", "data pipeline", "predictive model"],
  "missed_keywords": ["GCP", "AWS", "Agile"],
  "section_analysis": [
    {
      "section": "experience",
      "entry_id": "uuid-exp-1",
      "keywords_found_here": ["Python", "data pipeline"],
      "preserve": [
        "keyword 'data pipeline' di bullet 1",
        "keyword 'Python' di bullet 1",
        "action verb 'Developed' di awal bullet 1"
      ]
    },
    {
      "section": "projects",
      "entry_id": "uuid-proj-1",
      "keywords_found_here": ["predictive model", "SQL"],
      "preserve": [
        "keyword 'predictive model' di bullet 3",
        "frasa 'statistical analysis' di bullet 2"
      ]
    }
  ]
}
```

---

## 5. Semantic Reviewer Agent — Spesifikasi

### Pendekatan
Membandingkan setiap section langsung dengan bagian JD/JR yang relevan untuk section tersebut. Mapping antara section dan JD/JR yang relevan bersifat fixed untuk v1.

### Mapping Section → JD/JR yang Relevan

```
Summary       ←→ Seluruh JD + JR (harus merepresentasikan keseluruhan CV)
Experience    ←→ Semua JD + semua JR
Projects      ←→ Technical requirements dari JR + responsibilities dari JD
Education     ←→ Education requirements dari JR
Awards        ←→ Domain-specific requirements dari JR
Skills        ←→ Hard skill requirements dari JR
Organizations ←→ Soft skill requirements dari JR
Certificates  ←→ Certification requirements dari JR (jika ada)
```

### Kriteria Evaluasi per Section

Untuk setiap section, Semantic Reviewer Agent menilai tiga aspek:

1. **Relevansi** — apakah narasi relevan dengan JD/JR yang dipetakan ke section ini?
2. **Convincingness** — apakah narasi meyakinkan HR bahwa user mampu memenuhi requirement?
3. **Narrative Instructions** — apakah instruksi narasi dari Brief (implicit match, gap bridge) sudah dieksekusi dengan baik?

### Input

```json
{
  "section": "experience",
  "entry_id": "uuid-exp-1",
  "content": {
    "company": "PT Maju Bersama",
    "role": "Data Analyst Intern",
    "bullets": [
      "Developed churn classification predictive model...",
      "Addressed severe class imbalance using SMOTE...",
      "Achieved 15% accuracy improvement..."
    ]
  },
  "relevant_jd_jr": [
    { "id": "d001", "text": "Menganalisis data pelanggan", "dimension": "JD" },
    { "id": "r007", "text": "Menguasai Python", "dimension": "JR" }
  ],
  "narrative_instructions": [
    {
      "id": "ni-001",
      "type": "implicit_match",
      "requirement": "Pengalaman GCP",
      "approved_angle": "Narrasikan sebagai cloud platform proficiency"
    }
  ]
}
```

### Output

```json
{
  "section": "experience",
  "entry_id": "uuid-exp-1",
  "semantic_score": 82,
  "verdict": "passed",
  "strengths": [
    "Narasi menunjukkan problem-solving yang kuat di bullet 2",
    "Impact di bullet 3 spesifik dengan angka yang meyakinkan"
  ],
  "issues": [],
  "revise": []
}
```

Contoh output untuk section yang gagal:

```json
{
  "section": "projects",
  "entry_id": "uuid-proj-1",
  "semantic_score": 54,
  "verdict": "failed",
  "strengths": [
    "Bullet 1 mendeskripsikan arsitektur teknis dengan jelas"
  ],
  "issues": [
    "Bullet 2 terlalu teknis, tidak menunjukkan business impact atau problem-solving narrative",
    "Narrative instruction ni-001 (cloud platform proficiency) belum dieksekusi"
  ],
  "revise": [
    "Ubah bullet 2 agar lebih menunjukkan problem-solving approach, kurangi detail teknis yang berlebihan",
    "Tambahkan konteks cloud platform proficiency secara natural di bullet yang paling relevan"
  ]
}
```

---

## 6. Penggabungan Hasil dan QC Report

Setelah kedua agent selesai, hasilnya digabungkan per section untuk menentukan `action_required`.

### Logika Penggabungan — AND Logic dengan Toleransi Asimetris

```
Untuk setiap section:

ATS passed  DAN Semantic passed  → action_required: false  ✅
ATS passed  DAN Semantic failed  → action_required: true   (revisi semantic only)
ATS failed  DAN Semantic passed  → action_required: true   (revisi ATS only)
ATS failed  DAN Semantic failed  → action_required: true   (revisi keduanya)

Definisi "passed":
- ATS     : ats_score ≥ ATS_THRESHOLD (configurable constant)
- Semantic: semantic_score ≥ SEMANTIC_THRESHOLD (configurable constant)
            ATAU verdict tidak "failed"
```

### Format QC Report (dikirim ke Cluster 4)

```json
{
  "application_id": "uuid-application",
  "cv_version": 2,
  "iteration": 1,
  "overall_ats_score": 78,
  "sections": [
    {
      "section": "experience",
      "entry_id": "uuid-exp-1",
      "ats_score": 85,
      "ats_status": "passed",
      "semantic_score": 82,
      "semantic_status": "passed",
      "action_required": false,
      "preserve": [
        "keyword 'data pipeline' di bullet 1",
        "keyword 'Python' di bullet 1"
      ],
      "revise": []
    },
    {
      "section": "projects",
      "entry_id": "uuid-proj-1",
      "ats_score": 80,
      "ats_status": "passed",
      "semantic_score": 54,
      "semantic_status": "failed",
      "action_required": true,
      "preserve": [
        "keyword 'predictive model' di bullet 3",
        "frasa 'statistical analysis' di bullet 2"
      ],
      "revise": [
        "Ubah bullet 2 agar lebih menunjukkan problem-solving approach",
        "Tambahkan konteks cloud platform proficiency secara natural"
      ],
      "missed_keywords": []
    }
  ]
}
```

---

## 7. Penanganan Oscillation

Untuk mencegah iterasi yang tidak konvergen (ATS dan Semantic saling bertentangan), diterapkan strategi **best version selection** saat iterasi habis.

```
Setiap iterasi QC menyimpan:
├── Skor ATS per section
├── Skor Semantic per section
└── Combined score = (ATS × 0.5) + (Semantic × 0.5)

Jika MAX_QC_ITERATIONS tercapai dan section belum lolos:
└── Ambil versi dengan combined score tertinggi dari semua iterasi
    bukan versi terakhir
    → kirim versi terbaik ini ke user review dengan catatan
```

Bobot combined score (0.5 / 0.5) bersifat configurable — dapat disesuaikan jika ATS lebih diprioritaskan dari semantic atau sebaliknya.

---

## 8. Struktur Database

### Tabel `qc_results`
```sql
CREATE TABLE qc_results (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id   UUID REFERENCES applications(id) ON DELETE CASCADE,
  cv_version       INTEGER NOT NULL,
  iteration        INTEGER NOT NULL DEFAULT 1,
  section          VARCHAR(50) NOT NULL,
  entry_id         UUID,
  ats_score        NUMERIC(5,2),
  ats_status       VARCHAR(10) CHECK (ats_status IN ('passed', 'failed')),
  semantic_score   NUMERIC(5,2),
  semantic_status  VARCHAR(10) CHECK (semantic_status IN ('passed', 'failed')),
  action_required  BOOLEAN NOT NULL DEFAULT FALSE,
  preserve         JSONB,
  revise           JSONB,
  missed_keywords  TEXT[],
  combined_score   NUMERIC(5,2),
  created_at       TIMESTAMP DEFAULT NOW()
);
```

### Tabel `qc_overall_scores`
```sql
CREATE TABLE qc_overall_scores (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id   UUID REFERENCES applications(id) ON DELETE CASCADE,
  cv_version       INTEGER NOT NULL,
  iteration        INTEGER NOT NULL DEFAULT 1,
  overall_ats_score NUMERIC(5,2),
  sections_passed  INTEGER,
  sections_failed  INTEGER,
  created_at       TIMESTAMP DEFAULT NOW()
);
```

---

## 9. Konfigurasi

```
ATS_THRESHOLD         = configurable constant (nilai default: ditentukan saat implementasi)
SEMANTIC_THRESHOLD    = configurable constant (nilai default: ditentukan saat implementasi)
QC_COMBINED_WEIGHT_ATS      = 0.5  (configurable)
QC_COMBINED_WEIGHT_SEMANTIC = 0.5  (configurable)
```

---

## 10. Relasi dengan Cluster Lain

```
Input:
├── cv_outputs (Cluster 5)       → Final Structured Output yang dievaluasi
├── keyword_targets (Cluster 4)  → target keyword untuk ATS scoring
├── job_requirements (Cluster 2) → requirements untuk ATS keyword matching
└── job_descriptions (Cluster 2) → context untuk semantic review

Output:
└── QC Report → Cluster 4 (Revision Handler)
                field action_required sebagai filter eksplisit
                field preserve sebagai instruksi ke Content Writer Agent
                field revise sebagai target perbaikan
```

---

## 11. Prinsip Utama

- **Dua agent, paralel** — ATS Scoring dan Semantic Reviewer berjalan bersamaan untuk efisiensi.
- **Scoring deterministik, reasoning LLM** — skor ATS dihitung secara matematis, LLM hanya menginterpretasi untuk menghasilkan preserve list.
- **AND logic dengan toleransi asimetris** — ATS adalah hard requirement, Semantic adalah soft requirement.
- **Preserve list wajib ada** — setiap revisi brief harus menyertakan apa yang harus dijaga, bukan hanya apa yang harus diubah. Ini mencegah oscillation.
- **action_required sebagai single source of truth** — Cluster 4 wajib memfilter hanya section dengan `action_required: true`. Section yang lolos tidak boleh disentuh.
- **Best version selection** — saat iterasi habis, versi dengan combined score tertinggi yang dipakai, bukan versi terakhir.
- **Cluster 6 tidak mengubah konten** — tugasnya hanya mengevaluasi dan melaporkan. Semua keputusan revisi ada di Cluster 4.
