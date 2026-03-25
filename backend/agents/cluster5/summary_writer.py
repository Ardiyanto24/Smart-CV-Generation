# cv-agent/backend/agents/cluster5/summary_writer.py

"""
Summary Writer Agent — Cluster 5

Menulis professional summary berdasarkan seluruh isi CV yang sudah digenerate.
Selalu dipanggil TERAKHIR — setelah Content Writer dan Skills Grouping selesai.

Summary yang ditulis setelah semua sections selesai akan spesifik dan
mencerminkan konten nyata CV, bukan pernyataan generik.

Prompts dikelola di: agents/prompts/summary_writer_prompt.py
"""

import json
import logging

from agents.llm_client import call_llm
from agents.prompts.summary_writer_prompt import SUMMARY_WRITER_SYSTEM

logger = logging.getLogger("agents.cluster5.summary_writer")


async def write_summary(
    cv_sections: dict,
    skills_grouped: dict,
    brief: dict,
) -> str:
    """
    Write the professional summary from completed CV sections.

    Harus dipanggil setelah semua sections lain selesai — experience, projects,
    education, awards, organizations, dan skills sudah ter-generate semua.

    LLM membaca seluruh konten CV yang sudah digenerate untuk menulis summary
    yang mencerminkan isi nyata, bukan pernyataan generik.

    Args:
        cv_sections: dict berisi generated sections — experience, projects,
                     education, awards, organizations. Setiap item sudah
                     punya bullets dari Content Writer Agent.
        skills_grouped: output dari Skills Grouping Agent —
                        {"skills_grouped": [{"group_label": ..., "items": [...]}]}
        brief: brief subset dari strategy_brief —
               summary_hook_direction, primary_angle, keyword_targets, tone

    Returns:
        str — professional summary (3–5 sentences)
    """
    logger.info("[write_summary] generating professional summary")

    # ── Build CV content snapshot untuk LLM ───────────────────────────────────
    # Kirim semua generated sections agar LLM bisa menulis summary yang spesifik
    # Format ringkas: hanya fields yang relevan untuk summary writing
    cv_content_snapshot = {}

    # Experience — company, role, dan bullets (yang paling informatif untuk summary)
    if cv_sections.get("experience"):
        cv_content_snapshot["experience"] = [
            {
                "company": entry.get("company"),
                "role": entry.get("role"),
                "bullets": entry.get("bullets", []),
            }
            for entry in cv_sections["experience"]
        ]

    # Projects — title dan bullets
    if cv_sections.get("projects"):
        cv_content_snapshot["projects"] = [
            {
                "title": entry.get("title"),
                "bullets": entry.get("bullets", []),
            }
            for entry in cv_sections["projects"]
        ]

    # Education — institution, degree, bullets
    if cv_sections.get("education"):
        cv_content_snapshot["education"] = [
            {
                "institution": entry.get("institution"),
                "degree": entry.get("degree"),
                "bullets": entry.get("bullets", []),
            }
            for entry in cv_sections["education"]
        ]

    # Awards — title dan bullets (kalau ada)
    if cv_sections.get("awards"):
        cv_content_snapshot["awards"] = [
            {
                "title": entry.get("title"),
                "bullets": entry.get("bullets", []),
            }
            for entry in cv_sections["awards"]
        ]

    # Skills grouped — untuk memperkuat keyword coverage di summary
    cv_content_snapshot["skills_grouped"] = skills_grouped.get("skills_grouped", [])

    # ── User prompt ───────────────────────────────────────────────────────────
    # System prompt dikelola di agents/prompts/summary_writer_prompt.py
    user_prompt = f"""Write the professional summary for this CV.

GENERATED CV SECTIONS (read carefully — summary must reflect actual content):
{json.dumps(cv_content_snapshot, ensure_ascii=False, indent=2)}

BRIEF CONTEXT:
{json.dumps({
    "primary_angle": brief.get("primary_angle", ""),
    "summary_hook_direction": brief.get("summary_hook_direction", ""),
    "keyword_targets": brief.get("keyword_targets", []),
    "tone": brief.get("tone", "technical_concise"),
}, ensure_ascii=False, indent=2)}

Return the summary as JSON."""

    # ── LLM call ──────────────────────────────────────────────────────────────
    # max_tokens=300 — 5 kalimat × ~30 kata × ~5 token = ~750, cukup dengan buffer
    raw_response = await call_llm(
        system_prompt=SUMMARY_WRITER_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=300,
    )

    # ── Parse JSON response ───────────────────────────────────────────────────
    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[write_summary] LLM returned unparseable JSON. "
            f"Raw: {raw_response[:300]}"
        )
        raise ValueError(f"Summary Writer returned invalid JSON: {e}")

    summary = result.get("summary", "")

    if not summary:
        logger.warning("[write_summary] LLM returned empty summary")
        raise ValueError("Summary Writer returned empty summary string")

    # Log sentence count sebagai sanity check (bukan blocking validation)
    # Gunakan titik sebagai estimasi — tidak 100% akurat tapi cukup untuk logging
    sentence_estimate = len([s for s in summary.split(".") if s.strip()])
    if not (3 <= sentence_estimate <= 6):  # 6 untuk toleransi estimasi
        logger.warning(
            f"[write_summary] summary may not be 3-5 sentences "
            f"(estimated {sentence_estimate} sentences)"
        )

    logger.info(
        f"[write_summary] summary generated: "
        f"~{sentence_estimate} sentences, {len(summary.split())} words"
    )

    # Return string langsung — node generate_content set ke cv_output["summary"]
    return summary