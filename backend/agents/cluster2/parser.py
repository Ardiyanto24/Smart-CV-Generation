# cv-agent/backend/agents/cluster2/parser.py

"""
Parser Agent — Cluster 2

Mengubah raw JD/JR text menjadi atomic requirement items.
Output disimpan ke dua tabel: job_descriptions dan job_requirements.
Items dengan source "JD+JR" masuk ke kedua tabel.
"""

import json
import logging

from agents.llm_client import call_llm
from db.supabase import get_supabase

logger = logging.getLogger("agents.cluster2.parser")


async def run_parser(
    application_id: str,
    jd_raw: str,
    jr_raw: str,
) -> dict:
    """
    Parse raw JD and JR text into structured atomic requirement items.

    Decomposes compound sentences, detects priority signals, deduplicates
    items that appear in both JD and JR, then saves to DB.

    Args:
        application_id: UUID of the application being processed
        jd_raw: raw Job Description text (may be None/empty)
        jr_raw: raw Job Requirements text (may be None/empty)

    Returns:
        jd_jr_context dict following Context Package 2 structure:
        {
            "application_id": str,
            "job_descriptions": [{"responsibility_id": str, "text": str}],
            "job_requirements": [{"requirement_id": str, "text": str,
                                  "source": str, "priority": str}]
        }
    """
    logger.info(f"[run_parser] parsing JD/JR for application_id={application_id}")

    # ── System prompt ─────────────────────────────────────────────────────────
    system_prompt = """You are an expert job description parser. Your job is to decompose raw Job Description (JD) and Job Requirements (JR) texts into atomic requirement items.

Rules:
1. ATOMIZE: Split every compound sentence into separate items. "Python and SQL" → two items. "Analyze data and build dashboards" → two items.
2. PRIORITY DETECTION: Mark as "nice_to_have" if the item contains signals like: "nilai plus", "diutamakan", "menjadi keunggulan", "preferred", "a plus", "nice to have", "would be great", "bonus", "advantage". Everything else is "must".
3. DEDUPLICATE: If the same requirement appears in both JD and JR, output it ONCE with source "JD+JR".
4. PRESERVE PHRASING: Keep the original phrasing as close as possible — do not paraphrase or generalize.
5. ID FORMAT: Use "d001", "d002"... for JD items. Use "r001", "r002"... for JR items. For JD+JR items, use "r" prefix.
6. Respond ONLY with a valid JSON array — no markdown fences, no preamble.

Output structure (JSON array):
[
  {
    "id": "d001",
    "text": "atomic requirement or responsibility text",
    "source": "JD",
    "priority": "must"
  },
  {
    "id": "r001",
    "text": "atomic requirement text",
    "source": "JR",
    "priority": "must"
  },
  {
    "id": "r002",
    "text": "item appearing in both JD and JR",
    "source": "JD+JR",
    "priority": "must"
  }
]"""

    # ── User prompt — kirim raw JD dan JR ─────────────────────────────────────
    # Handle None/empty gracefully — agent tetap bisa proses satu saja
    jd_section = f"JOB DESCRIPTION (JD):\n{jd_raw}" if jd_raw else "JOB DESCRIPTION (JD): (not provided)"
    jr_section = f"JOB REQUIREMENTS (JR):\n{jr_raw}" if jr_raw else "JOB REQUIREMENTS (JR): (not provided)"

    user_prompt = f"""Parse and atomize the following job posting:

{jd_section}

{jr_section}

Return a JSON array of atomic items following the specified structure."""

    # ── LLM call ──────────────────────────────────────────────────────────────
    raw_response = await call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=2000,    # JD/JR bisa panjang — butuh token lebih banyak
    )

    # ── Parse JSON response ───────────────────────────────────────────────────
    try:
        parsed_items = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[run_parser] LLM returned unparseable JSON for "
            f"application_id={application_id}. Raw: {raw_response[:500]}"
        )
        raise ValueError(
            f"Parser Agent returned invalid JSON for "
            f"application_id={application_id}: {e}"
        )

    if not isinstance(parsed_items, list):
        raise ValueError(
            f"Parser Agent returned non-list response for "
            f"application_id={application_id}"
        )

    logger.info(
        f"[run_parser] parsed {len(parsed_items)} items for "
        f"application_id={application_id}"
    )

    # ── Pisahkan items berdasarkan source ─────────────────────────────────────
    # JD items  : source = "JD" atau "JD+JR"
    # JR items  : source = "JR" atau "JD+JR"
    # JD+JR items masuk ke KEDUA tabel — downstream consumer membaca tabel masing-masing

    jd_items = [item for item in parsed_items if item.get("source") in ("JD", "JD+JR")]
    jr_items = [item for item in parsed_items if item.get("source") in ("JR", "JD+JR")]

    supabase = get_supabase()

    # ── Insert ke job_descriptions table ──────────────────────────────────────
    # Satu row per JD item — responsibility_id menggunakan id dari parser output
    if jd_items:
        jd_rows = [
            {
                "application_id": application_id,
                "responsibility_id": item["id"],
                "text": item["text"],
            }
            for item in jd_items
        ]
        supabase.table("job_descriptions").insert(jd_rows).execute()

        logger.info(
            f"[run_parser] inserted {len(jd_rows)} rows into job_descriptions"
        )

    # ── Insert ke job_requirements table ──────────────────────────────────────
    # Satu row per JR item — requirement_id menggunakan id dari parser output
    if jr_items:
        jr_rows = [
            {
                "application_id": application_id,
                "requirement_id": item["id"],
                "text": item["text"],
                "source": item["source"],
                "priority": item.get("priority", "must"),
            }
            for item in jr_items
        ]
        supabase.table("job_requirements").insert(jr_rows).execute()

        logger.info(
            f"[run_parser] inserted {len(jr_rows)} rows into job_requirements"
        )

    # ── Build jd_jr_context — Context Package 2 ───────────────────────────────
    # Format yang dikonsumsi oleh node berikutnya (analyze_gap)
    # job_descriptions: hanya responsibility_id dan text — no priority/source
    # job_requirements: responsibility_id, text, source, priority — full info
    jd_jr_context = {
        "application_id": application_id,
        "job_descriptions": [
            {
                "responsibility_id": item["id"],
                "text": item["text"],
            }
            for item in jd_items
        ],
        "job_requirements": [
            {
                "requirement_id": item["id"],
                "text": item["text"],
                "source": item["source"],
                "priority": item.get("priority", "must"),
            }
            for item in jr_items
        ],
    }

    logger.info(
        f"[run_parser] context built: "
        f"{len(jd_jr_context['job_descriptions'])} JD items, "
        f"{len(jd_jr_context['job_requirements'])} JR items"
    )

    return jd_jr_context