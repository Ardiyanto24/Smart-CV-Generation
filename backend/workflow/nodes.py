# cv-agent/backend/workflow/nodes.py

"""
LangGraph node functions untuk CV Agent workflow.

Setiap node adalah async function yang:
1. Menerima CVAgentState sebagai input
2. Melakukan satu unit pekerjaan (LLM call, DB query, atau kalkulasi)
3. Mengembalikan dict berisi HANYA field state yang berubah

LangGraph otomatis merge partial dict ini ke full state —
node tidak perlu return seluruh state, hanya yang berubah.

Phase 5: semua node adalah stubs dengan placeholder data berstruktur benar.
Phase 6: setiap stub diganti dengan real LLM agent call.
"""

import logging
from datetime import datetime, timezone

from config import get_settings
from db.supabase import get_supabase
from workflow.state import CVAgentState

# ── Logger ────────────────────────────────────────────────────────────────────
# Module-level logger — dipakai oleh semua node di file ini
# Format: "workflow.nodes" sebagai logger name untuk mudah difilter di log output
# Contoh log: "workflow.nodes - INFO - [parse_jd_jr] called for application uuid-123"

logger = logging.getLogger("workflow.nodes")


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER 2 — Job Analyzer
# Node: parse_jd_jr
# ══════════════════════════════════════════════════════════════════════════════

async def parse_jd_jr(state: CVAgentState) -> dict:
    """
    Node 1: Parse raw JD/JR text into structured atomic requirement items.

    Reads raw JD/JR from job_postings table, calls Parser Agent to decompose
    into atomic items, and returns structured jd_jr_context (Context Package 2).

    Input  : state.application_id
    Output : state.jd_jr_context
    Cluster: 2 — Parser Agent
    """
    application_id = state["application_id"]
    logger.info(f"[parse_jd_jr] called for application_id={application_id}")

    supabase = get_supabase()

    # Query raw JD/JR yang sudah disimpan oleh POST /applications/{id}/start
    # Di Phase 6, data ini akan dikirim ke Parser Agent untuk diproses
    response = (
        supabase.table("job_postings")
        .select("jd_raw, jr_raw")
        .eq("application_id", application_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    # Log apa yang ditemukan di DB untuk membantu debugging
    if response.data:
        logger.info(
            f"[parse_jd_jr] found job_posting for application_id={application_id}"
        )
    else:
        logger.warning(
            f"[parse_jd_jr] no job_posting found for application_id={application_id}"
        )

    # TODO Phase 6: Replace with real Parser Agent call
    # from agents.cluster2.parser import run_parser
    # jd_raw = response.data[0]["jd_raw"]
    # jr_raw = response.data[0]["jr_raw"]
    # return {"jd_jr_context": await run_parser(application_id, jd_raw, jr_raw)}

    # ── Placeholder data — struktur harus persis sesuai Context Package 2 ──────
    # Downstream nodes (analyze_gap, plan_strategy, content_writer) membaca dari
    # jd_jr_context ini — kalau strukturnya salah, mereka akan error
    jd_jr_context = {
        "application_id": application_id,

        # job_descriptions: hasil parsing JD — satu item = satu tanggung jawab
        "job_descriptions": [
            {
                "responsibility_id": "d001",
                "text": "Menganalisis data pelanggan untuk mendukung keputusan bisnis",
            },
            {
                "responsibility_id": "d002",
                "text": "Membangun dashboard reporting untuk tim bisnis",
            },
        ],

        # job_requirements: hasil parsing JR — satu item = satu requirement
        "job_requirements": [
            {
                "requirement_id": "r001",
                "text": "Menguasai Python",
                "source": "JR",
                "priority": "must",
            },
            {
                "requirement_id": "r002",
                "text": "Pengalaman dengan SQL",
                "source": "JR",
                "priority": "must",
            },
            {
                "requirement_id": "r003",
                "text": "Pengalaman dengan AWS atau GCP",
                "source": "JR",
                "priority": "nice_to_have",
            },
        ],
    }

    logger.info(
        f"[parse_jd_jr] returning placeholder jd_jr_context "
        f"with {len(jd_jr_context['job_descriptions'])} JD items "
        f"and {len(jd_jr_context['job_requirements'])} JR items"
    )

    # Return HANYA field yang berubah — LangGraph merge otomatis ke full state
    return {"jd_jr_context": jd_jr_context}