# cv-agent/backend/agents/cluster5/content_writer.py

"""
Content Writer Agent — Cluster 5

Menggenerate bullet points untuk setiap CV entry berdasarkan
Selected Content Package dan CV Strategy Brief.

Dua fungsi:
- write_entry_bullets     : generate 3 bullets untuk satu entry (1 LLM call)
- write_component_bullets : process semua entries satu komponen secara paralel

Three-bullet structure adalah fixed:
  Bullet 1: what was done (capability)
  Bullet 2: challenge and solution (problem-solving)
  Bullet 3: measurable impact (value delivered)

Prompts dikelola di: agents/prompts/content_writer_prompt.py
"""

import asyncio
import json
import logging

from agents.llm_client import call_llm
from agents.prompts.content_writer_prompt import CONTENT_WRITER_SYSTEM

logger = logging.getLogger("agents.cluster5.content_writer")


async def write_entry_bullets(entry: dict, brief_context: dict) -> dict:
    """
    Generate exactly 3 bullet points for a single CV entry.

    Three-bullet structure:
    - Bullet 1: capability — what was done (from what_i_did)
    - Bullet 2: problem-solving — challenge and how it was solved (from challenge)
    - Bullet 3: impact — measurable result (from impact)

    Narrative instructions diapply hanya kalau user_decision = "approved"
    atau "adjusted" — null dan "rejected" diabaikan.

    Args:
        entry: full entry dict dari selected_content_package, termasuk
               entry_id, component, what_i_did, challenge, impact, skills_used.
               Juga contains bullet_quota (selalu 3) sebagai konfirmasi.
        brief_context: dict berisi keyword_targets, tone, narrative_instructions

    Returns:
        dict berisi entry_id, component, dan bullets (list of 3 strings)
    """
    entry_id = entry.get("id") or entry.get("entry_id")
    component = entry.get("component", "unknown")

    logger.info(
        f"[write_entry_bullets] generating bullets for "
        f"component={component}, entry_id={entry_id}"
    )

    # ── Filter narrative instructions yang relevan dan sudah diapprove ─────────
    # Hanya apply kalau user_decision = "approved" atau "adjusted"
    # null = belum diputuskan, "rejected" = user tidak mau angle ini
    all_instructions = brief_context.get("narrative_instructions", [])
    approved_instructions = [
        ni for ni in all_instructions
        if ni.get("user_decision") in ("approved", "adjusted")
    ]

    # ── Build entry summary untuk LLM — hanya fields yang relevan ─────────────
    # Tidak kirim seluruh entry karena ada fields DB yang tidak dibutuhkan LLM
    entry_summary = {
        "component": component,
        "what_i_did": entry.get("what_i_did", []),
        "challenge": entry.get("challenge", []),
        "impact": entry.get("impact", []),
        "skills_used": entry.get("skills_used", []),
    }

    # Tambahkan context identifier sesuai component type
    # Dipakai LLM untuk framing yang tepat per komponen
    if component == "experience":
        entry_summary["company"] = entry.get("company")
        entry_summary["role"] = entry.get("role")
    elif component == "projects":
        entry_summary["title"] = entry.get("title")
        entry_summary["tools"] = entry.get("tools", [])
    elif component == "education":
        entry_summary["institution"] = entry.get("institution")
        entry_summary["degree"] = entry.get("degree")
    elif component == "awards":
        entry_summary["title"] = entry.get("title")
        entry_summary["issuer"] = entry.get("issuer")
    elif component == "organizations":
        entry_summary["name"] = entry.get("name")
        entry_summary["role"] = entry.get("role")

    # ── User prompt ───────────────────────────────────────────────────────────
    # System prompt dikelola di agents/prompts/content_writer_prompt.py
    user_prompt = f"""Generate 3 bullet points for this CV entry.

ENTRY DATA:
{json.dumps(entry_summary, ensure_ascii=False, indent=2)}

BRIEF CONTEXT:
{json.dumps({
    "keyword_targets": brief_context.get("keyword_targets", []),
    "tone": brief_context.get("tone", "technical_concise"),
    "narrative_instructions": approved_instructions,
}, ensure_ascii=False, indent=2)}

Return exactly 3 bullets as JSON."""

    # ── LLM call ──────────────────────────────────────────────────────────────
    raw_response = await call_llm(
        system_prompt=CONTENT_WRITER_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=400,  # 3 bullets × ~20 words × ~5 tokens = ~300, dengan buffer
    )

    # ── Parse JSON response ───────────────────────────────────────────────────
    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[write_entry_bullets] unparseable JSON for "
            f"component={component}, entry_id={entry_id}. "
            f"Raw: {raw_response[:300]}"
        )
        raise ValueError(
            f"Content Writer returned invalid JSON for "
            f"component={component}, entry_id={entry_id}: {e}"
        )

    bullets = result.get("bullets", [])

    # ── Validasi jumlah bullets ───────────────────────────────────────────────
    # LLM kadang menghasilkan 2 atau 4 — kita enforce 3
    if len(bullets) != 3:
        logger.warning(
            f"[write_entry_bullets] expected 3 bullets, got {len(bullets)} "
            f"for component={component}, entry_id={entry_id}. Adjusting."
        )
        # Truncate kalau lebih, pad dengan empty string kalau kurang
        while len(bullets) < 3:
            bullets.append("")
        bullets = bullets[:3]

    logger.info(
        f"[write_entry_bullets] generated {len(bullets)} bullets for "
        f"component={component}, entry_id={entry_id}"
    )

    return {
        "entry_id": entry_id,
        "component": component,
        "bullets": bullets,
    }


async def write_component_bullets(
    component: str,
    entries: list,
    brief_context: dict,
) -> list:
    """
    Process all entries for a single component in parallel.

    Wrapper tipis di atas write_entry_bullets — hanya asyncio.gather.
    Setiap entry mendapat LLM call tersendiri secara simultan.

    Urutan hasil dijamin sama dengan urutan input entries —
    asyncio.gather mempertahankan urutan sesuai urutan coroutines.

    Args:
        component: nama komponen ("experience", "projects", dll)
                   Di-inject ke setiap entry sebelum dikirim ke write_entry_bullets
        entries: list of entry dicts dari selected_content_package
        brief_context: dict berisi keyword_targets, tone, narrative_instructions

    Returns:
        List of result dicts dalam urutan yang sama dengan input entries.
        Setiap item: {"entry_id": str, "component": str, "bullets": list}
    """
    if not entries:
        logger.info(f"[write_component_bullets] no entries for component={component}")
        return []

    logger.info(
        f"[write_component_bullets] processing {len(entries)} entries "
        f"for component={component} in parallel"
    )

    # Inject component name ke setiap entry sebelum dikirim ke write_entry_bullets
    # Entry dari DB tidak punya field "component" — harus di-inject di sini
    annotated_entries = [
        {**entry, "component": component}
        for entry in entries
    ]

    # asyncio.gather — semua entries diproses serentak
    # Hasilnya list dengan urutan sama persis seperti input (tidak random)
    results = await asyncio.gather(*[
        write_entry_bullets(entry, brief_context)
        for entry in annotated_entries
    ])

    logger.info(
        f"[write_component_bullets] completed {len(results)} entries "
        f"for component={component}"
    )

    return list(results)