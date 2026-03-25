# cv-agent/backend/agents/cluster5/skills_grouping.py

"""
Skills Grouping Agent — Cluster 5

Mengorganisasi flat list of skill objects menjadi grouped structure
yang siap ditampilkan di CV sebagai skills section.

Grouping berdasarkan semantic proximity dan domain —
bukan sekedar mapping 3 kategori DB ke 3 grup.

Prompts dikelola di: agents/prompts/skills_grouping_prompt.py
"""

import json
import logging

from agents.llm_client import call_llm
from agents.prompts.skills_grouping_prompt import SKILLS_GROUPING_SYSTEM

logger = logging.getLogger("agents.cluster5.skills_grouping")


async def group_skills(skills: list) -> dict:
    """
    Organize a flat list of skill objects into CV-ready groups.

    LLM mengelompokkan skills berdasarkan semantic proximity dan domain —
    bukan rule-based mapping dari kategori DB.

    Validasi coverage: semua input skills harus muncul di output.
    Kalau ada yang hilang, di-log sebagai warning tapi tidak gagal.

    Args:
        skills: list of skill objects, masing-masing punya "name" dan "category"
                contoh: [{"name": "Python", "category": "technical"}, ...]

    Returns:
        dict berisi "skills_grouped" — list of group objects:
        {
            "skills_grouped": [
                {"group_label": "Programming Languages", "items": ["Python", "SQL"]},
                ...
            ]
        }
    """
    if not skills:
        logger.warning("[group_skills] received empty skills list")
        return {"skills_grouped": []}

    logger.info(f"[group_skills] grouping {len(skills)} skills")

    # ── User prompt — kirim flat skill list ke LLM ────────────────────────────
    # System prompt dikelola di agents/prompts/skills_grouping_prompt.py
    user_prompt = f"""Group these {len(skills)} skills into 3 to 6 meaningful CV sections.

SKILLS LIST:
{json.dumps(skills, ensure_ascii=False, indent=2)}

Return the grouped result as JSON."""

    # ── LLM call ──────────────────────────────────────────────────────────────
    # max_tokens=600 — 6 groups × ~10 skills × ~5 chars + labels = cukup
    raw_response = await call_llm(
        system_prompt=SKILLS_GROUPING_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=600,
    )

    # ── Parse JSON response ───────────────────────────────────────────────────
    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[group_skills] LLM returned unparseable JSON. "
            f"Raw: {raw_response[:300]}"
        )
        raise ValueError(f"Skills Grouping Agent returned invalid JSON: {e}")

    skills_grouped = result.get("skills_grouped", [])

    # ── Validasi jumlah groups (3–6) ──────────────────────────────────────────
    if not (3 <= len(skills_grouped) <= 6):
        logger.warning(
            f"[group_skills] expected 3-6 groups, got {len(skills_grouped)}. "
            f"Proceeding with LLM output as-is."
        )

    # ── Validasi coverage — semua input skills harus ada di output ────────────
    # Case-insensitive comparison untuk menangani perbedaan kapitalisasi
    input_names = {s["name"].lower() for s in skills}

    output_names = set()
    for group in skills_grouped:
        for item in group.get("items", []):
            output_names.add(item.lower())

    missing = input_names - output_names
    if missing:
        logger.warning(
            f"[group_skills] {len(missing)} skills missing from output: "
            f"{[s['name'] for s in skills if s['name'].lower() in missing]}"
        )

    duplicates = []
    seen = set()
    for group in skills_grouped:
        for item in group.get("items", []):
            item_lower = item.lower()
            if item_lower in seen:
                duplicates.append(item)
            seen.add(item_lower)

    if duplicates:
        logger.warning(
            f"[group_skills] {len(duplicates)} duplicate skills in output: {duplicates}"
        )

    group_count = len(skills_grouped)
    total_items = sum(len(g.get("items", [])) for g in skills_grouped)

    logger.info(
        f"[group_skills] grouping complete: {group_count} groups, "
        f"{total_items} skills placed"
    )

    return {"skills_grouped": skills_grouped}