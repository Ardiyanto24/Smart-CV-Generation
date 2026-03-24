# cv-agent/backend/agents/cluster1/profile_ingestion.py

"""
Profile Ingestion Agent — Cluster 1

Dijalankan setiap kali user create atau update profile entry.
Dua tahap yang berjalan sekuensial:
  Stage 1: Dekomposisi + inferensi contextual skills → langsung ke DB
  Stage 2: Inferensi standalone skills → suggestion ke user (tidak ke DB)

Plus satu helper untuk update operations:
  check_stale_skills: deteksi skills lama yang tidak lagi relevan
"""

import json
import logging

from agents.llm_client import call_llm
from db.supabase import get_supabase

logger = logging.getLogger("agents.cluster1.profile_ingestion")


async def run_stage1(component: str, entry: dict, entry_id: str) -> dict:
    """
    Stage 1 — Dekomposisi raw input menjadi structured arrays.

    Menerima raw entry dari user (what_i_did sebagai free-text string),
    memecahnya menjadi atomic items, dan menginfer skills yang dipakai
    secara kontekstual dalam entry tersebut.

    Hasil langsung diupdate ke DB — tidak perlu konfirmasi user.

    Args:
        component: nama tabel target ("experience", "projects", dll)
        entry: dict berisi raw fields dari user input
        entry_id: UUID row yang akan di-update di DB

    Returns:
        dict berisi what_i_did[], challenge[], impact[], skills_used[]
    """
    logger.info(
        f"[run_stage1] processing component={component}, entry_id={entry_id}"
    )

    # ── System prompt ─────────────────────────────────────────────────────────
    # Instruksi ketat: respond ONLY valid JSON, no markdown, no preamble
    system_prompt = """You are an expert CV data processor. Your job is to decompose raw profile entry text into structured, atomic items.

Rules:
1. Break compound sentences into separate atomic items — one item = one specific thing
2. Each item must be self-explanatory without context from other items
3. For skills_used: only include skills that are EXPLICITLY evidenced by the described activities — high confidence only, no speculation
4. Keep the original language (Indonesian or English) — do not translate
5. Respond ONLY with valid JSON — no markdown fences, no explanation, no preamble

Output structure:
{
  "what_i_did": ["atomic action item 1", "atomic action item 2", ...],
  "challenge": ["atomic challenge item 1", ...],
  "impact": ["atomic impact item 1", ...],
  "skills_used": ["Skill1", "Skill2", ...]
}

If a field is empty or not provided, return an empty array for that field."""

    # ── User prompt — kirim raw entry data ───────────────────────────────────
    user_prompt = f"""Decompose this {component} entry:

Component: {component}
Entry data:
{json.dumps(entry, ensure_ascii=False, indent=2)}

Return the decomposed result as JSON following the specified structure."""

    # ── LLM call ──────────────────────────────────────────────────────────────
    raw_response = await call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1000,
    )

    # ── Parse JSON response ───────────────────────────────────────────────────
    # JSONDecodeError harus di-raise sebagai ValueError agar with_retry bisa retry
    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[run_stage1] LLM returned unparseable JSON for entry_id={entry_id}. "
            f"Raw response: {raw_response[:500]}"
        )
        raise ValueError(
            f"Stage 1 LLM returned invalid JSON for entry_id={entry_id}: {e}"
        )

    # ── Validasi struktur response ────────────────────────────────────────────
    # Pastikan semua keys ada — LLM kadang lupa beberapa field
    for key in ["what_i_did", "challenge", "impact", "skills_used"]:
        if key not in result:
            result[key] = []

    logger.info(
        f"[run_stage1] decomposition complete: "
        f"what_i_did={len(result['what_i_did'])} items, "
        f"skills_used={result['skills_used']}"
    )

    # ── Update DB dengan hasil dekomposisi ────────────────────────────────────
    # Tulis hasil kembali ke row yang sama — component name = table name
    supabase = get_supabase()
    supabase.table(component).update({
        "what_i_did": result["what_i_did"],
        "challenge": result["challenge"],
        "impact": result["impact"],
        "skills_used": result["skills_used"],
    }).eq("id", entry_id).execute()

    logger.info(
        f"[run_stage1] DB updated for entry_id={entry_id} in table={component}"
    )

    return result


async def run_stage2(
    component: str,
    entry_id: str,
    entry: dict,
    user_id: str,
) -> list:
    """
    Stage 2 — Inferensi standalone skills dari konteks entry.

    Mengidentifikasi skills yang tidak eksplisit ditulis user tapi
    bisa disimpulkan dengan confidence tinggi dari konteks entry.

    PENTING: Hasil TIDAK langsung ke DB — dikembalikan sebagai suggestions
    yang harus diapprove user terlebih dahulu.

    Duplicate check: skills yang sudah ada di tabel skills user
    (case-insensitive) tidak akan dimunculkan sebagai suggestion.

    Args:
        component: nama komponen entry
        entry_id: UUID entry (untuk referensi di source field)
        entry: dict hasil Stage 1 (sudah terstruktur)
        user_id: UUID user untuk duplicate check

    Returns:
        List of suggestion objects: [{"name": str, "category": str, "source": str}]
        Empty list jika tidak ada suggestions baru
    """
    logger.info(
        f"[run_stage2] inferring standalone skills for "
        f"component={component}, entry_id={entry_id}"
    )

    # ── System prompt ─────────────────────────────────────────────────────────
    system_prompt = """You are an expert CV skills analyzer. Your job is to infer skills that are NOT explicitly listed but can be confidently deduced from the context of a profile entry.

Rules:
1. Only infer skills with HIGH confidence — if it can be clearly deduced from the described activities
2. Do NOT include skills that are already in the skills_used list of the entry
3. The "source" field must be a brief, plain-language explanation of WHY this skill was inferred
4. Category must be exactly one of: "technical", "soft", "tool"
5. Respond ONLY with valid JSON — no markdown fences, no preamble

Example: If someone used "Random Forest in Python", you can infer "Scikit-learn" because Random Forest is primarily used via scikit-learn in Python.

Output structure:
[
  {
    "name": "SkillName",
    "category": "technical|soft|tool",
    "source": "Brief explanation of why this skill was inferred from the entry context"
  }
]

Return empty array [] if no skills can be confidently inferred."""

    user_prompt = f"""Analyze this {component} entry and infer standalone skills:

Entry data (already decomposed):
{json.dumps(entry, ensure_ascii=False, indent=2)}

Return a JSON array of inferred skill objects. Only include skills NOT already in the skills_used list above."""

    # ── LLM call ──────────────────────────────────────────────────────────────
    raw_response = await call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=500,
    )

    # ── Parse JSON response ───────────────────────────────────────────────────
    try:
        inferred_skills = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[run_stage2] LLM returned unparseable JSON for entry_id={entry_id}. "
            f"Raw response: {raw_response[:500]}"
        )
        raise ValueError(
            f"Stage 2 LLM returned invalid JSON for entry_id={entry_id}: {e}"
        )

    # Pastikan response adalah list
    if not isinstance(inferred_skills, list):
        logger.warning(
            f"[run_stage2] LLM returned non-list response, treating as empty"
        )
        return []

    # ── Duplicate check — filter skills yang sudah ada ────────────────────────
    # Query semua skills user yang sudah ada (case-insensitive)
    supabase = get_supabase()
    existing_response = (
        supabase.table("skills")
        .select("name")
        .eq("user_id", user_id)
        .execute()
    )

    # Set lowercase untuk case-insensitive comparison
    existing_names = {
        row["name"].lower()
        for row in existing_response.data
    }

    # Filter out skills yang sudah ada
    filtered_skills = [
        skill for skill in inferred_skills
        if skill.get("name", "").lower() not in existing_names
    ]

    # Tambahkan entry_id ke source untuk referensi saat check_stale_skills
    # Format: "original source text [entry_id: uuid]"
    for skill in filtered_skills:
        skill["source"] = f"{skill.get('source', '')} [entry_id: {entry_id}]"

    logger.info(
        f"[run_stage2] inferred {len(inferred_skills)} skills, "
        f"{len(filtered_skills)} after duplicate filter for entry_id={entry_id}"
    )

    return filtered_skills


async def check_stale_skills(
    component: str,
    entry_id: str,
    user_id: str,
    new_skills_used: list,
) -> list:
    """
    Deteksi skills lama yang tidak lagi relevan setelah entry di-update.

    Dipanggil HANYA saat update operation — tidak saat create.

    Logic:
    1. Query skills user yang is_inferred=true dan source berisi entry_id ini
    2. Bandingkan dengan new_skills_used (hasil Stage 1 yang baru)
    3. Skill yang ada di DB tapi tidak ada di new_skills_used = stale

    PENTING: Fungsi ini hanya MELAPORKAN stale skills, tidak menghapus.
    Keputusan hapus ada di tangan user — sesuai prinsip spec.

    Args:
        component: nama komponen (untuk context logging)
        entry_id: UUID entry yang baru saja di-update
        user_id: UUID user pemilik skills
        new_skills_used: list skill names dari hasil Stage 1 yang baru

    Returns:
        List of stale skill names (strings)
    """
    logger.info(
        f"[check_stale_skills] checking stale skills for "
        f"component={component}, entry_id={entry_id}"
    )

    supabase = get_supabase()

    # Query skills yang:
    # 1. Milik user ini
    # 2. is_inferred = true (hanya skills yang diinfer, bukan yang diinput manual)
    # 3. source mengandung entry_id ini (menunjukkan skill ini diinfer dari entry ini)
    response = (
        supabase.table("skills")
        .select("name, source")
        .eq("user_id", user_id)
        .eq("is_inferred", True)
        .like("source", f"%{entry_id}%")  # source field mengandung entry_id
        .execute()
    )

    if not response.data:
        logger.info(
            f"[check_stale_skills] no inferred skills found for entry_id={entry_id}"
        )
        return []

    # Normalize new_skills_used ke lowercase untuk comparison
    new_skills_lower = {skill.lower() for skill in new_skills_used}

    # Skill dianggap stale kalau tidak ada di new_skills_used
    stale_skills = [
        row["name"]
        for row in response.data
        if row["name"].lower() not in new_skills_lower
    ]

    if stale_skills:
        logger.info(
            f"[check_stale_skills] found {len(stale_skills)} stale skills "
            f"for entry_id={entry_id}: {stale_skills}"
        )
    else:
        logger.info(
            f"[check_stale_skills] no stale skills for entry_id={entry_id}"
        )

    return stale_skills