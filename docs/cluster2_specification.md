# Cluster 2 — Job Analyzer
## Specification Document

---

## 1. Deskripsi

Cluster 2 bertugas memproses input JD (Job Description) dan JR (Job Requirements) dari user menjadi struktur atomic yang konsisten dan siap dikonsumsi oleh cluster lain. Output cluster ini disimpan ke **JD/JR DB** yang berfungsi sebagai shared resource — dikonsumsi oleh Cluster 3 (Gap Analyzer), Cluster 4 (Orchestrator), dan Cluster 5 (CV Generator).

---

## 2. Komponen

| Komponen | Tipe | Deskripsi |
|---|---|---|
| Form UI — JD | Frontend | Text area untuk user input Job Description |
| Form UI — JR | Frontend | Text area untuk user input Job Requirements |
| Parser Agent | LLM Agent | Dekomposisi JD/JR menjadi atomic requirements |
| JD/JR DB | PostgreSQL | Penyimpanan hasil parsing, shared resource |

---

## 3. Flow

```
User input JD (form 1) + JR (form 2)
        ↓
Parser Agent
├── Dekomposisi JD → atomic requirement items
├── Dekomposisi JR → atomic requirement items
├── Deteksi priority per item (must / nice_to_have)
└── Deduplikasi — jika JD dan JR menyebut hal yang sama → merge
        ↓
Hasil parsing disimpan ke JD/JR DB
        ↓
Siap dikonsumsi Cluster 3, Cluster 4, dan Cluster 5
```

---

## 4. Parser Agent — Spesifikasi

### Trigger
User submit form JD dan JR untuk satu lamaran (terikat ke satu `application_id`).

### Tugas Utama — Dekomposisi

Memecah teks JD/JR yang tidak terstruktur menjadi **atomic requirement items** — satu item hanya boleh berisi satu requirement. Tidak ada item yang menggabungkan dua hal berbeda.

Parser Agent juga mendeteksi **priority** berdasarkan sinyal linguistik dalam teks:
- `must` — requirement wajib (default jika tidak ada sinyal khusus)
- `nice_to_have` — ditandai kata seperti "nilai plus", "diutamakan", "menjadi keunggulan", "preferred", "a plus"

### Contoh Input

**JD (raw):**
> "Kami mencari Data Analyst yang akan bertanggung jawab menganalisis data pelanggan, membangun dashboard reporting untuk tim bisnis, berkolaborasi dengan tim produk untuk pengambilan keputusan berbasis data, dan mempresentasikan insight ke stakeholder senior."

**JR (raw):**
> "Minimal S1 Informatika atau Statistik, pengalaman minimal 2 tahun di bidang data, wajib menguasai Python dan SQL, pernah menangani dataset besar, familiar dengan metodologi Agile, kemampuan komunikasi dengan stakeholder non-teknis, pengalaman dengan AWS atau GCP menjadi nilai plus."

### Contoh Output (langsung ke DB)

```json
{
  "application_id": "uuid-application",
  "requirements": [
    {
      "id": "r001",
      "text": "Menganalisis data pelanggan",
      "source": "JD",
      "priority": "must"
    },
    {
      "id": "r002",
      "text": "Membangun dashboard reporting untuk tim bisnis",
      "source": "JD",
      "priority": "must"
    },
    {
      "id": "r003",
      "text": "Berkolaborasi dengan tim produk untuk pengambilan keputusan berbasis data",
      "source": "JD",
      "priority": "must"
    },
    {
      "id": "r004",
      "text": "Mempresentasikan insight ke stakeholder senior",
      "source": "JD",
      "priority": "must"
    },
    {
      "id": "r005",
      "text": "Minimal S1 Informatika atau Statistik atau bidang terkait",
      "source": "JR",
      "priority": "must"
    },
    {
      "id": "r006",
      "text": "Pengalaman minimal 2 tahun di bidang data",
      "source": "JR",
      "priority": "must"
    },
    {
      "id": "r007",
      "text": "Menguasai Python",
      "source": "JR",
      "priority": "must"
    },
    {
      "id": "r008",
      "text": "Menguasai SQL",
      "source": "JR",
      "priority": "must"
    },
    {
      "id": "r009",
      "text": "Pengalaman menangani dataset besar",
      "source": "JR",
      "priority": "must"
    },
    {
      "id": "r010",
      "text": "Familiar dengan metodologi Agile",
      "source": "JR",
      "priority": "must"
    },
    {
      "id": "r011",
      "text": "Kemampuan komunikasi dengan stakeholder non-teknis",
      "source": "JR",
      "priority": "must"
    },
    {
      "id": "r012",
      "text": "Pengalaman dengan AWS atau GCP",
      "source": "JR",
      "priority": "nice_to_have"
    }
  ]
}
```

### Aturan Dekomposisi
- Satu requirement = satu item. "Python dan SQL" dipecah menjadi dua item terpisah.
- Deduplikasi — jika JD dan JR menyebut hal yang sama, simpan satu item dengan `source: "JD+JR"`.
- Pertahankan nuansa asli teks perusahaan — jangan parafrase berlebihan, cukup bersihkan dan atomisasi.
- Priority default adalah `must` jika tidak ada sinyal linguistik khusus.

---

## 5. Struktur Database

### Tabel `applications`
```sql
CREATE TABLE applications (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
  company_name VARCHAR(255) NOT NULL,
  position     VARCHAR(255) NOT NULL,
  status       VARCHAR(50) DEFAULT 'draft'
               CHECK (status IN ('draft', 'applied', 'interview',
                                 'offer', 'rejected', 'accepted')),
  created_at   TIMESTAMP DEFAULT NOW(),
  updated_at   TIMESTAMP DEFAULT NOW()
);
```

**Catatan:** Tabel `applications` adalah anchor untuk seluruh sistem. Semua data per lamaran — JD/JR, gap analysis, dan generated CV — terikat ke satu `application_id`. Tabel ini juga mendukung fitur tracking lamaran di masa mendatang lewat kolom `status`.

---

### Tabel `job_postings` (raw input)
```sql
CREATE TABLE job_postings (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
  jd_raw         TEXT,
  jr_raw         TEXT,
  created_at     TIMESTAMP DEFAULT NOW()
);
```

**Catatan:** Raw input disimpan terpisah dari hasil parsing untuk keperluan audit dan kemungkinan re-parsing di masa mendatang jika logic Parser Agent diupgrade.

---

### Tabel `job_requirements` (hasil parsing)
```sql
CREATE TABLE job_requirements (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
  requirement_id VARCHAR(10) NOT NULL,
  text           TEXT NOT NULL,
  source         VARCHAR(10) CHECK (source IN ('JD', 'JR', 'JD+JR')),
  priority       VARCHAR(20) CHECK (priority IN ('must', 'nice_to_have')),
  created_at     TIMESTAMP DEFAULT NOW()
);
```

---

## 6. Konsumen JD/JR DB

JD/JR DB bukan hanya jembatan antara Cluster 2 dan 3 — dia adalah **shared resource** yang dikonsumsi oleh tiga cluster berbeda:

```
JD/JR DB dikonsumsi oleh:
├── Cluster 3 — Gap Analyzer Agent (analisis kecocokan)
├── Cluster 4 — Planner Agent      (keyword untuk strategy brief)
└── Cluster 5 — Content Writer Agent (keyword injection ke narasi)
```

---

## 7. Prinsip Utama

- **Satu item = satu requirement** — tidak ada item yang menggabungkan dua hal berbeda.
- **Raw input selalu disimpan** — untuk keperluan audit dan kemungkinan re-parsing.
- **Priority dideteksi dari sinyal linguistik** — agent tidak menebak, hanya mengikuti sinyal yang ada di teks asli.
- **Output bersifat dinamis mengikuti perusahaan** — tidak ada template section yang dipaksakan. Struktur output mengikuti apa yang disebutkan perusahaan.
