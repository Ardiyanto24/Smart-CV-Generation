# Cluster 1 — Knowledge Management
## Specification Document

---

## 1. Deskripsi

Cluster 1 adalah fondasi dari seluruh sistem. Tugasnya adalah mengumpulkan, memproses, dan menyimpan seluruh data kompetensi user ke dalam **Master Data DB**. Cluster ini berjalan di dua momen: saat setup awal (user pertama kali mengisi data) dan saat update (user menambah atau mengedit entry yang sudah ada).

Seluruh cluster lain bergantung pada kualitas data yang dihasilkan Cluster 1. Prinsip utamanya adalah: **tidak ada data yang masuk ke DB tanpa diproses terlebih dahulu oleh Profile Ingestion Agent**.

---

## 2. Komponen

| Komponen | Tipe | Deskripsi |
|---|---|---|
| Form UI | Frontend | Form input per komponen untuk user |
| Profile Ingestion Agent | LLM Agent | Memproses raw input menjadi structured data |
| Master Data DB | PostgreSQL | Penyimpanan seluruh data kompetensi user |

---

## 3. Flow

```
User mengisi form komponen (Education / Experience / Projects / dll)
        ↓
Raw input masuk ke sistem
        ↓
Profile Ingestion Agent — Tahap 1
├── Dekomposisi aktivitas → what_i_did[], challenge[], impact[]
└── Inferensi skills_used → langsung disimpan ke DB
        ↓
Profile Ingestion Agent — Tahap 2
└── Inferensi standalone skills → ditampilkan ke user sebagai suggestion
        ↓
User approve / reject suggestion
        ↓
Skill yang di-approve → disimpan ke tabel skills (is_inferred: true)
        ↓
Master Data DB siap dikonsumsi cluster lain
```

### Flow Update (Edit Entry Lama)

```
User mengedit entry yang sudah ada
        ↓
Profile Ingestion Agent re-run (hanya untuk entry yang diedit)
        ↓
Cek skill lama yang sudah approved:
├── Masih terdeteksi → tidak ada perubahan
└── Tidak terdeteksi lagi → tampilkan notifikasi ke user
    "Skill X sebelumnya diinfer dari entry ini tapi tidak lagi
     terdeteksi. Apakah ingin dihapus dari skills?"
        ↓
User putuskan → DB diupdate sesuai keputusan user
```

---

## 4. Profile Ingestion Agent — Spesifikasi

### Trigger
Setiap kali user melakukan **create** atau **update** pada entry manapun.

### Scope
Hanya memproses entry yang baru dibuat atau diedit — bukan seluruh Master Data.

### Tugas Tahap 1 — Dekomposisi & Inferensi Kontekstual

Memecah input multi-kegiatan menjadi array of atomic items dan menginfer skills yang digunakan dalam konteks entry tersebut.

**Input:**
```json
{
  "component": "experience",
  "entry": {
    "company": "PT Maju Bersama",
    "role": "Data Analyst Intern",
    "what_i_did": "Membangun model klasifikasi churn, membuat dashboard monitoring performa model, melakukan data cleaning pipeline, presentasi hasil ke stakeholder",
    "challenge": "Data sangat imbalanced, pipeline sering timeout",
    "impact": "Akurasi naik 15%, churn rate turun dalam 3 bulan pertama"
  }
}
```

**Output (langsung ke DB):**
```json
{
  "component": "experience",
  "entry_id": "uuid-generated",
  "what_i_did": [
    "Membangun model klasifikasi churn menggunakan Random Forest",
    "Membuat dashboard monitoring performa model",
    "Membangun data cleaning pipeline",
    "Mempresentasikan hasil analisis ke stakeholder"
  ],
  "challenge": [
    "Data sangat imbalanced dengan rasio 1:20",
    "Pipeline sering timeout saat memproses data besar"
  ],
  "impact": [
    "Akurasi model naik 15% setelah optimasi threshold",
    "Churn rate turun dalam 3 bulan pertama setelah deployment"
  ],
  "skills_used": [
    "Python",
    "Random Forest",
    "Dashboard development",
    "Data cleaning",
    "Stakeholder communication"
  ],
  "is_inferred": false
}
```

### Tugas Tahap 2 — Inferensi Standalone Skills

Mengekstrak skills yang tidak ditulis eksplisit user tapi bisa disimpulkan dari konteks. Hasilnya **tidak langsung ke DB** — ditampilkan ke user sebagai suggestion.

**Output (ditampilkan ke user):**
```json
{
  "inferred_skills": [
    {
      "name": "Scikit-learn",
      "category": "technical",
      "source": "Random Forest usage dalam konteks Python ML"
    },
    {
      "name": "Pandas",
      "category": "technical",
      "source": "Data cleaning pipeline dalam konteks Python"
    },
    {
      "name": "Data visualization",
      "category": "technical",
      "source": "Dashboard monitoring development"
    }
  ]
}
```

User dapat approve semua, reject semua, atau memilih satu per satu. Skill yang di-approve masuk ke tabel `skills` dengan `is_inferred: true`.

### Edge Case — Duplicate Skill
Sebelum menampilkan suggestion, agent mengecek tabel `skills` di DB. Skill yang sudah ada (berdasarkan nama, case-insensitive) **tidak dimunculkan** sebagai suggestion untuk menghindari duplikasi.

---

## 5. Struktur Database

### Tabel `users`
```sql
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        VARCHAR(255) NOT NULL,
  email       VARCHAR(255) UNIQUE NOT NULL,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);
```

---

### Tabel `education`
```sql
CREATE TABLE education (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID REFERENCES users(id) ON DELETE CASCADE,
  institution    VARCHAR(255) NOT NULL,
  degree         VARCHAR(255),
  field_of_study VARCHAR(255),
  start_date     DATE,
  end_date       DATE,
  is_current     BOOLEAN DEFAULT FALSE,
  what_i_did     TEXT[],
  challenge      TEXT[],
  impact         TEXT[],
  skills_used    TEXT[],
  is_inferred    BOOLEAN DEFAULT FALSE,
  created_at     TIMESTAMP DEFAULT NOW(),
  updated_at     TIMESTAMP DEFAULT NOW()
);
```

**Catatan:** `what_i_did`, `challenge`, `impact` pada education bersifat opsional — tidak semua user memiliki narasi aktivitas dari pengalaman pendidikan.

---

### Tabel `experience`
```sql
CREATE TABLE experience (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  company     VARCHAR(255) NOT NULL,
  role        VARCHAR(255) NOT NULL,
  start_date  DATE,
  end_date    DATE,
  is_current  BOOLEAN DEFAULT FALSE,
  what_i_did  TEXT[] NOT NULL,
  challenge   TEXT[],
  impact      TEXT[],
  skills_used TEXT[],
  is_inferred BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);
```

---

### Tabel `projects`
```sql
CREATE TABLE projects (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  title       VARCHAR(255) NOT NULL,
  url         VARCHAR(500),
  start_date  DATE,
  end_date    DATE,
  what_i_did  TEXT[] NOT NULL,
  challenge   TEXT[],
  impact      TEXT[],
  skills_used TEXT[],
  is_inferred BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);
```

---

### Tabel `awards`
```sql
CREATE TABLE awards (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  title       VARCHAR(255) NOT NULL,
  issuer      VARCHAR(255),
  date        DATE,
  what_i_did  TEXT[],
  challenge   TEXT[],
  impact      TEXT[],
  skills_used TEXT[],
  is_inferred BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);
```

---

### Tabel `organizations`
```sql
CREATE TABLE organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  name        VARCHAR(255) NOT NULL,
  role        VARCHAR(255),
  start_date  DATE,
  end_date    DATE,
  is_current  BOOLEAN DEFAULT FALSE,
  what_i_did  TEXT[],
  challenge   TEXT[],
  impact      TEXT[],
  skills_used TEXT[],
  is_inferred BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);
```

---

### Tabel `certificates`
```sql
CREATE TABLE certificates (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  name        VARCHAR(255) NOT NULL,
  issuer      VARCHAR(255),
  issue_date  DATE,
  expiry_date DATE,
  url         VARCHAR(500),
  is_inferred BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);
```

**Catatan:** Certificates tidak memiliki struktur tiga bullet point — cukup listing dengan metadata.

---

### Tabel `skills`
```sql
CREATE TABLE skills (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  name        VARCHAR(255) NOT NULL,
  category    VARCHAR(50) CHECK (category IN ('technical', 'soft', 'tool')),
  is_inferred BOOLEAN DEFAULT FALSE,
  source      TEXT,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, name)
);
```

**Catatan:** Tabel ini adalah **aggregated view** dari semua skills user — baik yang diinput manual maupun yang diinfer dari konteks entry lain. Kolom `source` menyimpan keterangan asal inferensi untuk keperluan transparansi ke user. Constraint `UNIQUE(user_id, name)` mencegah duplikasi skill per user.

---

## 6. Aturan Seleksi (dikonsumsi Cluster 4 — Selection Agent)

```json
TOP_N_CONFIG = {
  "experience":    { "top_n": 3, "bullets": 3 },
  "projects":      { "top_n": 3, "bullets": 3 },
  "awards":        { "top_n": 3, "bullets": 3 },
  "education":     { "top_n": "configurable" },
  "organizations": { "top_n": "configurable" },
  "certificates":  { "top_n": "configurable" },
  "skills":        { "top_n": "configurable" }
}
```

Nilai `configurable` dapat diubah tanpa menyentuh logic agent.

---

## 7. Operasi yang Didukung

| Operasi | Trigger Agent | Behaviour |
|---|---|---|
| Create entry baru | Ya | Full flow Tahap 1 + Tahap 2 |
| Edit entry lama | Ya | Re-run agent hanya untuk entry yang diedit + cek skill lama |
| Delete entry | Tidak | Operasi langsung ke DB, tidak melibatkan agent |

---

## 8. Prinsip Utama

- **Agent tidak pernah menyimpan hasil inferensi standalone skills tanpa konfirmasi user.** Dekomposisi dan `skills_used` kontekstual boleh langsung ke DB, tapi standalone skills selalu melalui approval.
- **Re-run agent bersifat scoped** — hanya entry yang berubah yang diproses ulang, bukan seluruh Master Data.
- **Duplicate skill tidak dimunculkan sebagai suggestion** — agent cek existing skills sebelum generate suggestion.
- **Skill yang sudah approved tidak dihapus otomatis** — perubahan pada entry hanya menghasilkan notifikasi, bukan penghapusan otomatis.
