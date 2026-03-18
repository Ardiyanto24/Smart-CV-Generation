# Cluster 3 — Gap Analyzer
## Specification Document

---

## 1. Deskripsi

Cluster 3 bertugas menganalisis gap antara JD/JR perusahaan dengan kompetensi yang dimiliki user. Analisis dilakukan dalam dua dimensi — JR vs Master Data (kecocokan syarat) dan JD vs Master Data (kecocokan tanggung jawab). Hasil analisis kemudian dievaluasi oleh Scoring Agent untuk menghasilkan skor kesesuaian kuantitatif dan kualitatif. Keseluruhan laporan ditampilkan ke user sebelum proses CV generation dimulai. User memutuskan apakah lanjut generate CV atau kembali ke Cluster 1 untuk update Master Data.

---

## 2. Komponen

| Komponen | Tipe | Deskripsi |
|---|---|---|
| Gap Analyzer Agent | LLM Agent | Analisis kecocokan per item, dua dimensi |
| Scoring Agent | Kalkulasi + LLM as a Judge | Menghitung skor kesesuaian kuantitatif dan kualitatif |
| Laporan UI | Frontend | Menampilkan hasil analisis dan skor ke user |
| Gap Analysis DB | PostgreSQL | Menyimpan hasil analisis dan skor per lamaran |

---

## 3. Flow

```
Trigger: Parser Agent (Cluster 2) selesai menyimpan ke JD/JR DB
        ↓
Gap Analyzer Agent
├── Baca job_descriptions dari JD/JR DB (per application_id)
├── Baca job_requirements dari JD/JR DB (per application_id)
├── Baca seluruh Master Data dari Cluster 1 (per user_id)
└── Untuk setiap item dari JD dan JR → analisis → kategorikan
        ↓
Hasil Gap Analysis disimpan ke Gap Analysis DB
        ↓
Scoring Agent
├── Baca hasil Gap Analysis dari DB
├── Hitung skor kuantitatif (deterministik)
└── LLM as a Judge → penilaian kualitatif
        ↓
Laporan lengkap ditampilkan ke user:
├── ✅ Exact Match
├── ⚡ Implicit Match
├── ❌ Gap
└── 📊 Skor Kesesuaian
        ↓
User memutuskan:
├── Lanjut generate CV → trigger Cluster 4
└── Kembali update profil → kembali ke Cluster 1
```

---

## 4. Gap Analyzer Agent — Spesifikasi

### Trigger
Dipanggil oleh Orchestrator setelah Cluster 2 selesai menyimpan ke JD/JR DB.

### Input
- Hasil parsing JD dari tabel `job_descriptions` (per `application_id`)
- Hasil parsing JR dari tabel `job_requirements` (per `application_id`)
- Seluruh Master Data dari Cluster 1 (per `user_id`)

### Proses — Dua Dimensi Analisis

**Dimensi 1 — JR vs Master Data**
Pertanyaan: *"Apakah user memenuhi syarat yang diminta perusahaan?"*
Patokan: setiap atomic item dari tabel `job_requirements`.

**Dimensi 2 — JD vs Master Data**
Pertanyaan: *"Apakah user punya pengalaman mengerjakan hal yang akan dikerjakan di posisi ini?"*
Patokan: setiap atomic item dari tabel `job_descriptions`.

Untuk setiap item dari kedua dimensi, agent melakukan reasoning dalam tiga langkah:

1. Cari bukti eksplisit di Master Data — skills, experience, projects, education, organizations, awards, certificates.
2. Jika tidak ada bukti eksplisit, cari bukti implisit — transferable skill, domain yang sama, teknologi yang equivalent.
3. Kategorikan berdasarkan temuan.

### Tiga Kategori Output

**Exact Match** — Ada bukti eksplisit di Master Data yang secara langsung menjawab item ini.

```json
{
  "item_id": "r007",
  "text": "Menguasai Python",
  "dimension": "JR",
  "category": "exact_match",
  "priority": "must",
  "evidence": [
    {
      "source": "projects",
      "entry_id": "uuid-project-1",
      "entry_title": "ML Churn Prediction",
      "detail": "Python tercantum di skills_used"
    },
    {
      "source": "skills",
      "entry_id": "uuid-skill-1",
      "entry_title": "Python",
      "detail": "Standalone skill, is_inferred: false"
    }
  ]
}
```

**Implicit Match** — Tidak ada bukti eksplisit, tapi ada bukti transferable secara makna atau domain.

```json
{
  "item_id": "r008",
  "text": "Menguasai SQL",
  "dimension": "JR",
  "category": "implicit_match",
  "priority": "must",
  "reasoning": "User memiliki pengalaman MySQL di experience entry PT Maju Bersama. MySQL adalah implementasi dari SQL — kemampuan query relasional, JOIN, aggregation dapat ditransfer langsung.",
  "evidence": [
    {
      "source": "experience",
      "entry_id": "uuid-exp-1",
      "entry_title": "PT Maju Bersama",
      "detail": "MySQL tercantum di skills_used"
    }
  ]
}
```

**Gap** — Tidak ditemukan bukti sama sekali di Master Data.

```json
{
  "item_id": "r012",
  "text": "Pengalaman dengan AWS atau GCP",
  "dimension": "JR",
  "category": "gap",
  "priority": "nice_to_have",
  "suggestion": "Tidak ditemukan pengalaman cloud platform di Master Data. Jika pernah menggunakan AWS atau GCP meski singkat, pertimbangkan untuk menambahkan ke profil Anda."
}
```

### Aturan Analisis
- Analisis bersifat **per item**, tidak per section — mengikuti apa yang disebutkan perusahaan.
- Setiap item memiliki field `dimension` untuk membedakan apakah berasal dari JD atau JR.
- Satu item bisa punya **multiple evidence** dari berbagai komponen Master Data.
- Implicit Match **wajib disertai reasoning** yang jelas.
- Gap yang berpriority `nice_to_have` tetap dilaporkan tapi diberi penanda visual berbeda di UI.
- Agent tidak membuat judgment tentang kelayakan user — tugasnya hanya melaporkan fakta dari data.

---

## 5. Scoring Agent — Spesifikasi

### Trigger
Dijalankan setelah Gap Analyzer Agent selesai menyimpan seluruh hasil ke Gap Analysis DB. Bersifat **sekuensial** — tidak paralel dengan Gap Analyzer.

### Pendekatan — Kombinasi Kalkulasi + LLM as a Judge

**Bagian 1 — Kalkulasi Kuantitatif (deterministik, bukan LLM)**

```
Skor Kuantitatif =
  (jumlah Exact Match × 1.0) + (jumlah Implicit Match × 0.7)
  ──────────────────────────────────────────────────────────
                    total items (JD + JR)

Hasil: angka 0–100
```

Bobot Implicit Match lebih rendah (0.7) karena membutuhkan transferable reasoning — tidak sekuat Exact Match.

**Bagian 2 — Penilaian Kualitatif (LLM as a Judge)**

LLM membaca keseluruhan Gap Analysis dan memberikan penilaian yang tidak bisa ditangkap angka saja — misalnya mendeteksi bahwa semua Gap ada di requirement `must` yang paling krusial, meskipun skor kuantitatif terlihat cukup baik.

### Output Scoring Agent

```json
{
  "application_id": "uuid-application",
  "quantitative_score": 72,
  "verdict": "cukup_cocok",
  "qualitative_assessment": {
    "strength": "Kompetensi teknis core (Python, SQL, ML) sangat kuat dan exact match dengan requirements utama",
    "concern": "Gap di requirement must 'Agile methodology' dan 'dashboard development' perlu diperhatikan — keduanya disebutkan di JD sebagai tanggung jawab harian",
    "recommendation": "Lanjutkan generate CV, tapi pastikan narasi menjembatani gap Agile dengan pengalaman iteratif yang sudah ada"
  },
  "proceed_recommendation": "lanjut"
}
```

### Tabel Interpretasi Skor

| Skor | Verdict | Rekomendasi |
|---|---|---|
| 75–100 | `sangat_cocok` | Lanjutkan generate CV |
| 50–74 | `cukup_cocok` | Lanjutkan, perhatikan gap yang ada |
| 0–49 | `kurang_cocok` | Pertimbangkan update profil dulu |

---

## 6. Format Laporan ke User

Laporan dikelompokkan per kategori dengan urutan: Skor → Exact Match → Implicit Match → Gap.

```
LAPORAN GAP ANALYSIS
Posisi  : Data Analyst — PT Contoh Indonesia
Tanggal : 2026-03-18

📊 SKOR KESESUAIAN: 72 / 100 — Cukup Cocok
─────────────────────────────────────────
Kekuatan : Kompetensi teknis core sangat kuat
Perhatian: Gap di Agile dan dashboard development
Saran    : Lanjutkan, narasi menjembatani gap yang ada

[Lanjut Generate CV]  [Kembali Update Profil]

─────────────────────────────────────────
✅ EXACT MATCH (7 items — 4 JR, 3 JD)
─────────────────────────────────────────
• [JR] Menguasai Python
  Bukti: ML Churn Prediction (projects), Python (skills)

• [JD] Mempresentasikan insight ke stakeholder senior
  Bukti: PT Maju Bersama — presentasi ke stakeholder (experience)

[... dst ...]

─────────────────────────────────────────
⚡ IMPLICIT MATCH (3 items — 2 JR, 1 JD)
─────────────────────────────────────────
• [JR] Menguasai SQL
  Bukti: MySQL di PT Maju Bersama (experience)
  Alasan: MySQL adalah implementasi SQL — kemampuan dapat ditransfer

[... dst ...]

─────────────────────────────────────────
❌ GAP (3 items — 2 JR, 1 JD)
─────────────────────────────────────────
• [JR — MUST] Familiar dengan metodologi Agile
  Tidak ditemukan bukti di Master Data.
  → Jika pernah menggunakan Agile, tambahkan ke profil Anda.

• [JR — NICE TO HAVE] Pengalaman dengan AWS atau GCP
  Tidak ditemukan bukti di Master Data.
  → Opsional — tidak wajib tapi menjadi keunggulan.

• [JD — MUST] Membangun dashboard reporting untuk tim bisnis
  Tidak ditemukan bukti pembuatan dashboard di Master Data.
  → Jika pernah membuat dashboard, tambahkan ke profil Anda.
```

---

## 7. Struktur Database

### Tabel `gap_analysis_results`
```sql
CREATE TABLE gap_analysis_results (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
  item_id        VARCHAR(10) NOT NULL,
  text           TEXT NOT NULL,
  dimension      VARCHAR(5) NOT NULL CHECK (dimension IN ('JD', 'JR')),
  category       VARCHAR(20) NOT NULL
                 CHECK (category IN ('exact_match', 'implicit_match', 'gap')),
  priority       VARCHAR(20) CHECK (priority IN ('must', 'nice_to_have')),
  evidence       JSONB,
  reasoning      TEXT,
  suggestion     TEXT,
  created_at     TIMESTAMP DEFAULT NOW()
);
```

### Tabel `gap_analysis_scores`
```sql
CREATE TABLE gap_analysis_scores (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id        UUID REFERENCES applications(id) ON DELETE CASCADE,
  quantitative_score    NUMERIC(5,2) NOT NULL,
  verdict               VARCHAR(20) NOT NULL
                        CHECK (verdict IN ('sangat_cocok', 'cukup_cocok', 'kurang_cocok')),
  strength              TEXT,
  concern               TEXT,
  recommendation        TEXT,
  proceed_recommendation VARCHAR(10) CHECK (proceed_recommendation IN ('lanjut', 'tinjau')),
  created_at            TIMESTAMP DEFAULT NOW()
);
```

---

## 8. Relasi dengan Cluster Lain

```
Input:
├── job_descriptions (Cluster 2) → responsibilities yang akan dianalisis
├── job_requirements (Cluster 2) → requirements yang akan dianalisis
└── Master Data DB (Cluster 1)   → kompetensi user sebagai bahan perbandingan

Output:
├── gap_analysis_results → dikonsumsi Cluster 4 Planner Agent
│                          sebagai dasar pembuatan CV Strategy Brief
└── gap_analysis_scores  → ditampilkan ke user sebagai decision point
```

---

## 9. Prinsip Utama

- **Dua agent, sekuensial** — Gap Analyzer selesai dulu, baru Scoring Agent jalan.
- **Analisis dua dimensi** — JR untuk kecocokan syarat, JD untuk kecocokan tanggung jawab.
- **Scoring kombinasi** — skor kuantitatif untuk orientasi cepat, penilaian kualitatif LLM untuk pemahaman mendalam.
- **User sebagai decision maker** — skor adalah informasi, bukan larangan. User tetap bisa lanjut meskipun skor rendah.
- **Gap bukan vonis** — setiap Gap disertai suggestion yang membantu user memutuskan tindakan selanjutnya.
- **Agent tidak membuat judgment kelayakan** — tugasnya melaporkan fakta dan memberikan rekomendasi, bukan menilai apakah user pantas melamar.
