# cv-agent/backend/agents/cluster4/revision_handler.py

"""
Revision Handler Agent — Cluster 4

Menangani dua jalur revisi CV:
  Jalur A (run_qc_revision)   : QC-driven, otomatis, berdasarkan QC report
  Jalur B (run_user_revision) : user-driven, manual, berdasarkan instruksi user

Kedua jalur menggunakan asyncio.gather untuk paralel processing per section.
Hanya sections yang memerlukan revisi yang diproses — sections lain tidak disentuh.

Prompts dikelola di: agents/prompts/revision_handler_prompt.py
"""

import asyncio
import json
import logging

from agents.llm_client import call_llm
from agents.prompts.revision_handler_prompt import QC_REVISION_SYSTEM, USER_REVISION_SYSTEM

logger = logging.getLogger("agents.cluster4.revision_handler")


async def _revise_section_qc(
    section: str,
    entry_id: str | None,
    current_bullets: list,
    preserve: list,
    revise: list,
    missed_keywords: list,
    narrative_instructions: list,
    tone: str,
) -> dict:
    """
    Helper: revisi satu section berdasarkan QC report.
    Dipanggil secara paralel untuk semua failed sections.

    Returns dict: {"section": str, "entry_id": str|None, "revised_bullets": list}
    """
    logger.info(f"[_revise_section_qc] revising section={section}, entry_id={entry_id}")

    # Filter narrative_instructions yang relevan untuk section ini
    relevant_instructions = [
        ni for ni in narrative_instructions
        if section.lower() in ni.get("requirement", "").lower()
        or section.lower() in ni.get("matched_with", "").lower()
    ] if narrative_instructions else []

    user_prompt = f"""Revise the bullets for this CV section based on QC feedback.

SECTION: {section}
ENTRY_ID: {entry_id or "N/A"}

CURRENT BULLETS:
{json.dumps(current_bullets, ensure_ascii=False, indent=2)}

PRESERVE (must keep exactly):
{json.dumps(preserve, ensure_ascii=False, indent=2)}

REVISE (must fix these issues):
{json.dumps(revise, ensure_ascii=False, indent=2)}

MISSED KEYWORDS (inject naturally):
{json.dumps(missed_keywords, ensure_ascii=False, indent=2)}

NARRATIVE INSTRUCTIONS (apply if relevant):
{json.dumps(relevant_instructions, ensure_ascii=False, indent=2)}

TONE: {tone}

Return the revised bullets as JSON."""

    raw_response = await call_llm(
        system_prompt=QC_REVISION_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=500,
    )

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[_revise_section_qc] unparseable JSON for section={section}. "
            f"Raw: {raw_response[:300]}"
        )
        raise ValueError(
            f"QC Revision returned invalid JSON for section={section}: {e}"
        )

    revised_bullets = result.get("revised_bullets", current_bullets)

    logger.info(
        f"[_revise_section_qc] section={section} revised: "
        f"{len(revised_bullets)} bullets"
    )

    return {
        "section": section,
        "entry_id": entry_id,
        "revised_bullets": revised_bullets,
    }


async def _revise_section_user(
    section: str,
    entry_id: str | None,
    current_bullets: list,
    user_instruction: str,
    keyword_targets: list,
    tone: str,
) -> dict:
    """
    Helper: revisi satu section berdasarkan instruksi user.
    Dipanggil secara paralel untuk semua sections yang diminta user.

    Returns dict: {"section": str, "entry_id": str|None, "revised_bullets": list}
    """
    logger.info(f"[_revise_section_user] revising section={section}, entry_id={entry_id}")

    user_prompt = f"""Revise the bullets for this CV section based on the user's instruction.

SECTION: {section}
ENTRY_ID: {entry_id or "N/A"}

CURRENT BULLETS:
{json.dumps(current_bullets, ensure_ascii=False, indent=2)}

USER INSTRUCTION:
{user_instruction}

KEYWORD TARGETS (preserve if already present):
{json.dumps(keyword_targets, ensure_ascii=False, indent=2)}

TONE: {tone}

Return the revised bullets as JSON."""

    raw_response = await call_llm(
        system_prompt=USER_REVISION_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=500,
    )

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[_revise_section_user] unparseable JSON for section={section}. "
            f"Raw: {raw_response[:300]}"
        )
        raise ValueError(
            f"User Revision returned invalid JSON for section={section}: {e}"
        )

    revised_bullets = result.get("revised_bullets", current_bullets)

    logger.info(
        f"[_revise_section_user] section={section} revised: "
        f"{len(revised_bullets)} bullets"
    )

    return {
        "section": section,
        "entry_id": entry_id,
        "revised_bullets": revised_bullets,
    }


async def run_qc_revision(
    application_id: str,
    qc_report: dict,
    cv_output: dict,
    strategy_brief: dict,
) -> dict:
    """
    Jalur A — QC-driven revision.

    Memproses semua sections dengan action_required=true dari QC report.
    Setiap section diproses oleh LLM call tersendiri secara paralel.
    Sections dengan action_required=false tidak disentuh.

    Args:
        application_id: UUID of the application
        qc_report: Context Package 5 dari qc_evaluate node
        cv_output: current cv_output dari state
        strategy_brief: approved brief — untuk narrative_instructions dan tone

    Returns:
        Context Package 6 dict dengan revision_type="qc_driven"
    """
    logger.info(
        f"[run_qc_revision] processing QC revision for "
        f"application_id={application_id}"
    )

    sections = qc_report.get("sections", [])
    tone = strategy_brief.get("tone", "technical_concise")
    narrative_instructions = strategy_brief.get("narrative_instructions", [])
    keyword_targets = strategy_brief.get("keyword_targets", [])

    # Filter hanya sections yang gagal QC
    failed_sections = [s for s in sections if s.get("action_required", False)]

    logger.info(
        f"[run_qc_revision] {len(failed_sections)}/{len(sections)} sections need revision"
    )

    if not failed_sections:
        logger.warning("[run_qc_revision] no failed sections found — nothing to revise")
        return {
            "revision_type": "qc_driven",
            "application_id": application_id,
            "sections_to_revise": [],
        }

    # ── Siapkan coroutines untuk paralel processing ────────────────────────────
    # Untuk setiap failed section, ambil current bullets dari cv_output
    # lalu buat coroutine revision-nya
    revision_coroutines = []
    section_metadata = []  # track metadata untuk build result nanti

    for qc_section in failed_sections:
        section_name = qc_section.get("section")
        entry_id = qc_section.get("entry_id")

        # Cari current bullets dari cv_output
        current_bullets = _extract_bullets_from_cv(cv_output, section_name, entry_id)

        if not current_bullets:
            logger.warning(
                f"[run_qc_revision] no bullets found for section={section_name}, "
                f"entry_id={entry_id} — skipping"
            )
            continue

        revision_coroutines.append(
            _revise_section_qc(
                section=section_name,
                entry_id=entry_id,
                current_bullets=current_bullets,
                preserve=qc_section.get("preserve", []),
                revise=qc_section.get("revise", []),
                missed_keywords=qc_section.get("missed_keywords", []),
                narrative_instructions=narrative_instructions,
                tone=tone,
            )
        )
        section_metadata.append({
            "section": section_name,
            "entry_id": entry_id,
            "preserve": qc_section.get("preserve", []),
            "revise_instructions": qc_section.get("revise", []),
        })

    # ── Paralel execution ──────────────────────────────────────────────────────
    # asyncio.gather menjalankan semua coroutines serentak
    # Hasilnya adalah list dengan urutan sama seperti coroutines input
    revision_results = await asyncio.gather(*revision_coroutines)

    # ── Build Context Package 6 ───────────────────────────────────────────────
    sections_to_revise = []
    for i, result in enumerate(revision_results):
        meta = section_metadata[i]
        sections_to_revise.append({
            "section": result["section"],
            "entry_id": result["entry_id"],
            "revised_bullets": result["revised_bullets"],
            "preserve": meta["preserve"],
            "instructions": meta["revise_instructions"],
            "user_instruction": None,  # null untuk QC-driven
        })

    logger.info(
        f"[run_qc_revision] QC revision complete: "
        f"{len(sections_to_revise)} sections revised for "
        f"application_id={application_id}"
    )

    return {
        "revision_type": "qc_driven",
        "application_id": application_id,
        "iteration": qc_report.get("iteration", 1),
        "brief_reference": strategy_brief.get("brief_id"),
        "sections_to_revise": sections_to_revise,
    }


async def run_user_revision(
    application_id: str,
    user_instructions: dict,
    cv_output: dict,
    strategy_brief: dict,
) -> dict:
    """
    Jalur B — User-driven revision.

    Memproses hanya sections yang user berikan instruksi revisi.
    Setiap section diproses paralel.
    Tidak ada batas iterasi — user bebas revisi sampai puas.

    Args:
        application_id: UUID of the application
        user_instructions: dict {section_key: "free-text instruction"}
                          contoh: {"experience": "tambahkan konteks production"}
        cv_output: current cv_output dari state
        strategy_brief: approved brief — untuk keyword_targets dan tone

    Returns:
        Context Package 6 dict dengan revision_type="user_driven"
    """
    logger.info(
        f"[run_user_revision] processing user revision for "
        f"application_id={application_id}, "
        f"sections={list(user_instructions.keys())}"
    )

    tone = strategy_brief.get("tone", "technical_concise")
    keyword_targets = strategy_brief.get("keyword_targets", [])

    if not user_instructions:
        logger.warning("[run_user_revision] no user instructions provided")
        return {
            "revision_type": "user_driven",
            "application_id": application_id,
            "sections_to_revise": [],
        }

    # ── Siapkan coroutines untuk paralel processing ────────────────────────────
    revision_coroutines = []
    section_keys = []

    for section_key, instruction in user_instructions.items():
        # section_key bisa berupa "section_name" atau "section_name:entry_id"
        # untuk membedakan beberapa entries dalam satu section
        if ":" in section_key:
            section_name, entry_id = section_key.split(":", 1)
        else:
            section_name = section_key
            entry_id = None

        # Cari current bullets dari cv_output
        current_bullets = _extract_bullets_from_cv(cv_output, section_name, entry_id)

        if not current_bullets:
            logger.warning(
                f"[run_user_revision] no bullets found for section={section_name}, "
                f"entry_id={entry_id} — skipping"
            )
            continue

        revision_coroutines.append(
            _revise_section_user(
                section=section_name,
                entry_id=entry_id,
                current_bullets=current_bullets,
                user_instruction=instruction,
                keyword_targets=keyword_targets,
                tone=tone,
            )
        )
        section_keys.append({
            "section_key": section_key,
            "section_name": section_name,
            "entry_id": entry_id,
            "user_instruction": instruction,
        })

    # ── Paralel execution ──────────────────────────────────────────────────────
    revision_results = await asyncio.gather(*revision_coroutines)

    # ── Build Context Package 6 ───────────────────────────────────────────────
    sections_to_revise = []
    for i, result in enumerate(revision_results):
        meta = section_keys[i]
        sections_to_revise.append({
            "section": result["section"],
            "entry_id": result["entry_id"],
            "revised_bullets": result["revised_bullets"],
            "preserve": [],  # user revision tidak punya preserve constraint
            "instructions": None,
            "user_instruction": meta["user_instruction"],
        })

    logger.info(
        f"[run_user_revision] user revision complete: "
        f"{len(sections_to_revise)} sections revised for "
        f"application_id={application_id}"
    )

    return {
        "revision_type": "user_driven",
        "application_id": application_id,
        "brief_reference": strategy_brief.get("brief_id"),
        "sections_to_revise": sections_to_revise,
    }


def _extract_bullets_from_cv(
    cv_output: dict,
    section_name: str,
    entry_id: str | None,
) -> list:
    """
    Helper: ekstrak bullets dari cv_output untuk section dan entry tertentu.

    cv_output structure per section:
    - list of entries (experience, projects, education, awards, organizations)
    - dict dengan skills_grouped (skills)
    - summary string (summary)

    Returns list of bullet strings, empty list jika tidak ditemukan.
    """
    section_data = cv_output.get(section_name)

    if not section_data:
        return []

    # Summary adalah string tunggal — wrap sebagai list untuk konsistensi
    if section_name == "summary":
        if isinstance(section_data, str):
            return [section_data]
        return []

    # Skills tidak punya bullets — skip
    if section_name == "skills":
        return []

    # List sections (experience, projects, education, awards, organizations)
    if isinstance(section_data, list):
        if entry_id:
            # Cari entry spesifik by entry_id
            for entry in section_data:
                if entry.get("entry_id") == entry_id:
                    return entry.get("bullets", [])
            return []
        else:
            # Ambil entry pertama kalau tidak ada entry_id spesifik
            if section_data:
                return section_data[0].get("bullets", [])
            return []

    return []