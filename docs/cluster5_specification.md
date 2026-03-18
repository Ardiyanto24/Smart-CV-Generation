# Cluster 5 — CV Generator
## Specification Document

---

## 1. Deskripsi

Cluster 5 adalah cluster eksekusi — tugasnya menghasilkan konten CV berdasarkan instruksi dari Selected Content Package dan CV Strategy Brief yang sudah divalidasi user di Cluster 4. Cluster ini tidak membuat keputusan strategis apapun — semua keputusan tentang "apa yang masuk" dan "bagaimana narasinya" sudah ditetapkan Cluster 4. Cluster 5 hanya mengeksekusi.

Output akhir Cluster 5 adalah **Final Structured Output** dalam format JSON yang keluar dari sistem agent dan dikonsumsi oleh dua pihak: Cluster 6 (Quality Control) dan Document Renderer (pure code).

---

## 2. Komponen

| Komponen | Tipe | Deskripsi |
|---|---|---|
| Content Writer Agent | LLM Agent | Menulis bullet points per entry, paralel per komponen |
| Skills Grouping Agent | LLM Agent | Mengelompokkan ulang skills berdasarkan kategori |
| Summary Writer Agent | LLM Agent | Menulis hook summary setelah semua section selesai |
| CV Output DB | PostgreSQL | Menyimpan Final Structured Output dengan versioning |
| Document Renderer | Pure code (non-LLM) | Render JSON ke PDF/DOCX |

---

## 3. Flow

```
Input: Selected Content Package + CV Strategy Brief (dari Cluster 4)
        ↓
FASE 1 — Pass-through Assembly
└── Kumpulkan data non-generated langsung dari Master Data:
    nama, kontak, metadata section (company, role, tahun, dll)
        ↓
FASE 2 — Content Generation (per komponen, sekuensial antar komponen)

  Experience (paralel antar entry)
  ├── Entry 1 → Content Writer Agent → 3 bullet points
  ├── Entry 2 → Content Writer Agent → 3 bullet points
  └── Entry 3 → Content Writer Agent → 3 bullet points
        ↓ selesai
  Education (paralel antar entry)
  └── Entry 1 → Content Writer Agent → 3 bullet points
        ↓ selesai
  Awards (paralel antar entry)
  ├── Entry 1 → Content Writer Agent → 3 bullet points
  └── Entry 2 → Content Writer Agent → 3 bullet points
        ↓ selesai
  Projects (paralel antar entry)
  ├── Entry 1 → Content Writer Agent → 3 bullet points
  ├── Entry 2 → Content Writer Agent → 3 bullet points
  └── Entry 3 → Content Writer Agent → 3 bullet points
        ↓ selesai
  Organizations (paralel antar entry)
  └── Entry 1 → Content Writer Agent → 3 bullet points
        ↓ selesai
  Skills → Skills Grouping Agent → grouped listing
        ↓ selesai

FASE 3 — Summary Generation
└── Summary Writer Agent
    (membaca seluruh hasil Fase 1 + Fase 2)
        ↓
FASE 4 — Assembly
└── Gabungkan semua hasil menjadi Final Structured Output (JSON)
        ↓
Simpan ke CV Output DB (versioned)
        ↓
Trigger Cluster 6 (QC)
```

---

## 4. Urutan Section (Fixed)

Urutan section di CV mengikuti template fixed. Urutan ini tidak berubah antar lamaran — Planner Agent tidak menentukan urutan.

```
1. Header         (nama, kontak)
2. Summary        (Summary Writer Agent)
3. Experience     (Content Writer Agent)
4. Education      (Content Writer Agent)
5. Awards         (Content Writer Agent)
6. Skills         (Skills Grouping Agent)
7. Projects       (Content Writer Agent)
8. Certificates   (pass-through)
9. Organizations  (Content Writer Agent)
```

Template tambahan dapat dibuat di masa mendatang tanpa mengubah logic agent.

---

## 5. Content Writer Agent — Spesifikasi

### Trigger
Dipanggil per komponen secara sekuensial. Di dalam setiap komponen, semua entry diproses secara paralel.

### Input per Instance
Setiap instance Content Writer Agent menerima:
- Satu entry dari Selected Content Package (misal: satu experience entry)
- CV Strategy Brief (keyword_targets, tone, narrative_instructions yang relevan)

### Tugas
Menulis tepat **3 bullet points** per entry dengan struktur:
- **Bullet 1** — Apa yang dikerjakan (`what_i_did`)
- **Bullet 2** — Tantangan dan solusi (`challenge`)
- **Bullet 3** — Impact / hasil (`impact`)

### Aturan Penulisan
- Setiap bullet point maksimal **20 kata**
- Mulai dengan **action verb** (Developed, Built, Engineered, Delivered, dll)
- Injeksi keyword dari `keyword_targets` secara natural — tidak dipaksakan
- Tone mengikuti Brief: `technical_concise` / `professional_formal` / `professional_conversational`
- Eksekusi `narrative_instructions` yang relevan untuk entry ini

### Contoh Input

```json
{
  "entry": {
    "component": "experience",
    "entry_id": "uuid-exp-1",
    "company": "PT Maju Bersama",
    "role": "Data Analyst Intern",
    "what_i_did": [
      "Membangun model klasifikasi churn",
      "Membuat dashboard monitoring performa model",
      "Membangun data cleaning pipeline"
    ],
    "challenge": [
      "Data sangat imbalanced dengan rasio 1:20",
      "Pipeline sering timeout saat memproses data besar"
    ],
    "impact": [
      "Akurasi model naik 15%",
      "Churn rate turun dalam 3 bulan pertama"
    ],
    "skills_used": ["Python", "MySQL", "Scikit-learn"]
  },
  "brief_context": {
    "keyword_targets": ["data pipeline", "predictive model", "stakeholder", "Python"],
    "tone": "technical_concise",
    "narrative_instructions": []
  }
}
```

### Contoh Output

```json
{
  "entry_id": "uuid-exp-1",
  "component": "experience",
  "bullets": [
    "Developed churn classification predictive model and data pipeline for automated cleaning and dashboard monitoring of model performance.",
    "Addressed severe class imbalance (1:20 ratio) using SMOTE and threshold tuning, resolving pipeline timeout issues through batch processing optimization.",
    "Achieved 15% accuracy improvement and reduced churn rate within 3 months, delivering actionable insights to stakeholders through performance dashboard."
  ]
}
```

### Penanganan Narrative Instructions

Jika Brief berisi narrative instruction untuk entry ini, Content Writer Agent mengeksekusinya:

```json
{
  "narrative_instruction": {
    "type": "implicit_match",
    "requirement": "Pengalaman dengan GCP",
    "matched_with": "AWS experience",
    "approved_angle": "Narrasikan sebagai cloud platform proficiency — familiar dengan paradigma cloud (AWS), adaptasi ke GCP manageable"
  }
}
```

Agent mengintegrasikan angle ini secara natural ke dalam bullet point yang paling relevan — bukan menambah bullet point baru.

---

## 6. Skills Grouping Agent — Spesifikasi

### Trigger
Dijalankan setelah semua komponen lain selesai di Fase 2, sebelum Summary Writer Agent.

### Input
- Seluruh skills dari Selected Content Package
- Kolom `category` dari tabel `skills` (`technical`, `soft`, `tool`)

### Tugas
Mengelompokkan skills ke dalam kategori yang relevan untuk ditampilkan di CV. Pengelompokan tidak rigid — LLM bisa membuat subkategori yang lebih deskriptif berdasarkan konteks skills yang ada.

### Contoh Input

```json
{
  "skills": [
    { "name": "Python",          "category": "technical" },
    { "name": "SQL",             "category": "technical" },
    { "name": "TensorFlow",      "category": "tool" },
    { "name": "Scikit-learn",    "category": "tool" },
    { "name": "MySQL",           "category": "tool" },
    { "name": "Leadership",      "category": "soft" },
    { "name": "Problem Solving", "category": "soft" }
  ]
}
```

### Contoh Output

```json
{
  "skills_grouped": [
    {
      "group_label": "Programming Languages",
      "items": ["Python", "SQL", "R"]
    },
    {
      "group_label": "Libraries & Frameworks",
      "items": ["TensorFlow", "Scikit-learn", "PyTorch", "Transformers"]
    },
    {
      "group_label": "Tools & Platforms",
      "items": ["MySQL", "Hugging Face", "Optuna"]
    },
    {
      "group_label": "Personal Strengths",
      "items": ["Leadership", "Problem Solving", "Time Management"]
    }
  ]
}
```

---

## 7. Summary Writer Agent — Spesifikasi

### Trigger
Dijalankan setelah seluruh Fase 2 selesai — semua section sudah digenerate.

### Input
- Seluruh hasil Content Writer Agent (semua bullet points)
- Seluruh hasil Skills Grouping Agent
- Pass-through data (metadata semua section)
- CV Strategy Brief: `summary_hook_direction`, `primary_angle`, `keyword_targets`, `tone`

### Tugas
Menulis **professional summary** yang menjadi hook CV. Summary harus:
- Mencerminkan keseluruhan isi CV (bukan generik)
- Mengikuti `summary_hook_direction` dari Brief
- Menginjeksi keyword paling krusial dari `keyword_targets`
- Panjang: 3–5 kalimat

### Contoh Output

```json
{
  "summary": "Bachelor of Statistics with hands-on experience building predictive models and data pipelines across NLP, computer vision, and tabular machine learning domains. Proficient in Python and ML frameworks including TensorFlow and scikit-learn, with proven expertise in feature engineering and model optimization. Skilled in translating complex statistical analysis into actionable business insights through cross-functional stakeholder collaboration. Demonstrated ability to deliver end-to-end machine learning solutions independently while applying data-driven approaches to solve real-world business problems."
}
```

---

## 8. Final Structured Output — Format JSON

Ini adalah output akhir dari sistem agent. Format JSON terstruktur per section, dengan semua data — pass-through dan generated — tergabung dalam satu dokumen.

```json
{
  "application_id": "uuid-application",
  "version": 1,
  "generated_at": "2026-03-18T10:00:00Z",

  "header": {
    "name": "Ardiyanto",
    "email": "ardiyanto.ardhiy@gmail.com",
    "phone": "+6281541571692",
    "linkedin": "Ardiyanto",
    "github": "ardiyanto24"
  },

  "summary": "Bachelor of Statistics with hands-on experience...",

  "experience": [
    {
      "entry_id": "uuid-exp-1",
      "company": "PT Maju Bersama",
      "role": "Data Analyst Intern",
      "year": "2024",
      "bullets": [
        "Developed churn classification predictive model and data pipeline...",
        "Addressed severe class imbalance using SMOTE and threshold tuning...",
        "Achieved 15% accuracy improvement and reduced churn rate..."
      ]
    }
  ],

  "education": [
    {
      "entry_id": "uuid-edu-1",
      "institution": "Universitas Sebelas Maret",
      "degree": "S1-Statistika",
      "year": "2021 – 2025",
      "location": "Surakarta",
      "bullets": [
        "Completed comprehensive statistical modeling curriculum...",
        "...",
        "..."
      ]
    }
  ],

  "awards": [ ... ],

  "skills": {
    "skills_grouped": [
      { "group_label": "Programming Languages", "items": ["Python", "SQL", "R"] },
      { "group_label": "Libraries & Frameworks", "items": ["TensorFlow", "Scikit-learn"] },
      { "group_label": "Tools & Platforms", "items": ["MySQL", "Hugging Face"] },
      { "group_label": "Personal Strengths", "items": ["Leadership", "Problem Solving"] }
    ]
  },

  "projects": [
    {
      "entry_id": "uuid-proj-1",
      "title": "RFP Insight — RAG System",
      "github_url": "https://github.com/...",
      "tools": ["Python", "LangChain", "LLaMA", "FAISS"],
      "bullets": [
        "Built document intelligence system implementing RAG architecture...",
        "Addressed long-document reasoning challenges through custom chunking pipeline...",
        "Delivered scalable solution enabling automated RFP processing..."
      ]
    }
  ],

  "certificates": [
    { "name": "Machine Learning Specialization by Stanford University", "issuer": "Coursera" },
    { "name": "DeepLearning.AI TensorFlow Developer Professional Certificate", "issuer": "Coursera" }
  ],

  "organizations": [
    {
      "entry_id": "uuid-org-1",
      "name": "Unit Ilmu Al-Qur'an Ormawa Kerohanian Islam",
      "role": "President",
      "year": "2024",
      "bullets": [
        "Led university-level spiritual organization responsible for strategic planning...",
        "Addressed inter-division collaboration challenges through structured programs...",
        "Increased member participation and strengthened organizational vision alignment..."
      ]
    }
  ]
}
```

---

## 9. Struktur Database

### Tabel `cv_outputs`
```sql
CREATE TABLE cv_outputs (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
  version        INTEGER NOT NULL DEFAULT 1,
  content        JSONB NOT NULL,
  revision_type  VARCHAR(20)
                 CHECK (revision_type IN ('initial', 'qc_driven', 'user_driven')),
  section_revised VARCHAR(50),
  status         VARCHAR(20) DEFAULT 'draft'
                 CHECK (status IN ('draft', 'qc_passed', 'user_approved', 'final')),
  created_at     TIMESTAMP DEFAULT NOW()
);
```

**Catatan:** Setiap iterasi revisi menghasilkan record baru dengan `version` yang di-increment. Kolom `section_revised` mencatat section mana yang direvisi pada versi tersebut — `NULL` berarti initial generation (seluruh CV). Kolom `revision_type` mencatat apakah versi ini hasil revisi QC atau permintaan user.

**Contoh versioning:**

| version | revision_type | section_revised | status |
|---|---|---|---|
| 1 | initial | NULL | qc_passed |
| 2 | qc_driven | experience | qc_passed |
| 3 | user_driven | projects | user_approved |
| 4 | user_driven | summary | final |

---

## 10. Relasi dengan Cluster Lain

```
Input:
├── Selected Content Package (Cluster 4) → konten yang akan digenerate
├── CV Strategy Brief (Cluster 4)        → instruksi narasi dan keyword
└── Master Data DB (Cluster 1)           → data pass-through (header, metadata)

Output:
├── Final Structured Output (JSON) → Cluster 6 (QC evaluation)
└── Final Structured Output (JSON) → Document Renderer (setelah semua approved)
```

---

## 11. Prinsip Utama

- **Pure execution** — Cluster 5 tidak membuat keputusan strategis apapun. Semua keputusan sudah ada di Brief dari Cluster 4.
- **Dua jenis data** — pass-through (tidak butuh LLM) dan generated (butuh LLM). Keduanya digabung di Final Structured Output.
- **Paralelisasi per komponen** — entry dalam satu komponen diproses paralel, tapi antar komponen sekuensial. Ini menjaga konsistensi tone antar section.
- **Summary selalu terakhir** — Summary Writer Agent hanya bekerja setelah semua section lain selesai, sehingga summary benar-benar mencerminkan isi CV.
- **Versioning per revisi** — setiap iterasi revisi (QC atau user) menghasilkan versi baru, bukan menimpa versi lama. Ini memungkinkan rollback jika dibutuhkan.
- **Document Renderer di luar sistem agent** — rendering ke PDF/DOCX adalah pure code, tidak ada LLM call. Deterministik, cepat, tidak bisa berhalusinasi.
