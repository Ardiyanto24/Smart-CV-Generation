# cv-agent/backend/agents/cluster4/selection.py

"""
Selection Agent — Cluster 4

Memilih dan meranking entry Master Data yang akan masuk ke CV
berdasarkan CV Strategy Brief yang sudah diapprove user.

Dua tahap:
1. LLM ranking — hanya dipanggil kalau candidates > top_n
2. DB fetch + package assembly — build Context Package 4

Output disimpan ke selected_content_packages table.

Prompts dikelola di: agents/prompts/selection_prompt.py
"""

import json
import logging

from agents.llm_client import call_llm
from agents.prompts.selection_prompt import SELECTION_SYSTEM
from db.supabase import get_supabase

logger = logging.getLogger("agents.cluster4.selection")

# Komponen yang menggunakan LLM ranking (punya what_i_did, bukan flat metadata)
# Certificates dan skills tidak diranking oleh LLM — diambil semua sesuai top_n
RANKED_COMPONENTS = ["experience", "projects", "education", "awards", "organizations"]


async def run_selection(
    application_id: str,
    user_id: str,
    strategy_brief: dict,
) -> dict:
    """
    Select and rank Master Data entries for CV based on approved strategy brief.

    Reads content_instructions from brief to know which entry UUIDs are eligible.
    Calls LLM to rank entries only when candidates exceed top_n.
    Assembles full Selected Content Package (Context Package 4).

    Args:
        application_id: UUID of the application being processed
        user_id: UUID of the user — for querying Master Data
        strategy_brief: approved brief dict — must contain content_instructions,
                        primary_angle, keyword_targets, and brief_id

    Returns:
        selected_content_package dict following Context Package 4 structure
    """
    logger.info(
        f"[run_selection] selecting content for application_id={application_id}"
    )

    supabase = get_supabase()
    content_instructions = strategy_brief.get("content_instructions", {})
    brief_id = strategy_brief.get("brief_id")

    # ── Fetch candidate entries dari DB ───────────────────────────────────────
    # Untuk setiap komponen, query DB hanya untuk entry UUIDs yang ada di "include"
    # Kalau include kosong, query semua entries milik user (skills + certificates)
    candidates_by_component = {}

    for component, instruction in content_instructions.items():
        include_ids = instruction.get("include", [])
        top_n = instruction.get("top_n", 3)

        if include_ids:
            # Query hanya entries yang masuk dalam include list dari Planner
            response = (
                supabase.table(component)
                .select("*")
                .eq("user_id", user_id)
                .in_("id", include_ids)
                .execute()
            )
        else:
            # Untuk skills dan certificates — tidak ada include list dari gap analysis
            # Ambil semua entries milik user, dibatasi top_n
            response = (
                supabase.table(component)
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(top_n)
                .execute()
            )

        candidates_by_component[component] = {
            "entries": response.data,
            "top_n": top_n,
        }

        logger.info(
            f"[run_selection] {component}: {len(response.data)} candidates, top_n={top_n}"
        )

    # ── LLM ranking — hanya untuk komponen yang candidates > top_n ───────────
    # Komponen yang tidak perlu ranking: semua candidates langsung masuk
    components_needing_ranking = {
        component: data
        for component, data in candidates_by_component.items()
        if component in RANKED_COMPONENTS
        and len(data["entries"]) > data["top_n"]
    }

    ranked_ids_by_component = {}

    if components_needing_ranking:
        logger.info(
            f"[run_selection] {len(components_needing_ranking)} components need ranking: "
            f"{list(components_needing_ranking.keys())}"
        )

        # Build ranking input — hanya summary fields, bukan full entry
        # LLM tidak butuh content lengkap untuk ranking
        components_to_rank = {}
        for component, data in components_needing_ranking.items():
            # Buat summary per entry untuk ranking context
            summarized = []
            for entry in data["entries"]:
                summary = {"entry_id": entry["id"]}
                # Tambahkan fields yang relevan untuk ranking per component type
                if component == "experience":
                    summary.update({
                        "company": entry.get("company"),
                        "role": entry.get("role"),
                        "skills_used": entry.get("skills_used", []),
                    })
                elif component == "projects":
                    summary.update({
                        "title": entry.get("title"),
                        "skills_used": entry.get("skills_used", []),
                    })
                elif component == "education":
                    summary.update({
                        "institution": entry.get("institution"),
                        "degree": entry.get("degree"),
                        "field_of_study": entry.get("field_of_study"),
                    })
                elif component in ("awards", "organizations"):
                    summary.update({
                        "title": entry.get("title") or entry.get("name"),
                        "skills_used": entry.get("skills_used", []),
                    })
                summarized.append(summary)

            components_to_rank[component] = {
                "top_n": data["top_n"],
                "candidates": summarized,
            }

        # User prompt untuk LLM ranking
        # System prompt dikelola di agents/prompts/selection_prompt.py
        user_prompt = f"""Rank these candidate entries for the CV.

PRIMARY ANGLE: {strategy_brief.get('primary_angle', '')}
KEYWORD TARGETS: {json.dumps(strategy_brief.get('keyword_targets', []))}

COMPONENTS TO RANK:
{json.dumps(components_to_rank, ensure_ascii=False, indent=2)}

Return a JSON object with ranked entry_id lists per component."""

        raw_response = await call_llm(
            system_prompt=SELECTION_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=800,
        )

        # Parse ranking response
        try:
            ranked_ids_by_component = json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.error(
                f"[run_selection] LLM returned unparseable JSON for "
                f"application_id={application_id}. Raw: {raw_response[:500]}"
            )
            raise ValueError(
                f"Selection Agent returned invalid JSON for "
                f"application_id={application_id}: {e}"
            )

    # ── Build selected entries per component ──────────────────────────────────
    selected_content = {}

    for component, data in candidates_by_component.items():
        entries = data["entries"]
        top_n = data["top_n"]

        if component in ranked_ids_by_component:
            # Gunakan urutan dari LLM ranking
            # Re-fetch full entry data berdasarkan ranked order
            ranked_ids = ranked_ids_by_component[component][:top_n]
            entry_map = {e["id"]: e for e in entries}
            ordered_entries = [
                entry_map[eid]
                for eid in ranked_ids
                if eid in entry_map
            ]
        else:
            # Tidak perlu ranking — ambil semua candidates (sudah di-limit saat query)
            ordered_entries = entries[:top_n]

        # Tambahkan bullet_quota ke setiap entry
        # bullet_quota = 3: Content Writer akan menulis 3 bullets per entry
        # Ini adalah instruksi strategis dari Cluster 4 ke Cluster 5
        selected_content[component] = [
            {**entry, "bullet_quota": 3}
            for entry in ordered_entries
        ]

        logger.info(
            f"[run_selection] {component}: {len(selected_content[component])} entries selected"
        )

    # ── Build Context Package 4 ───────────────────────────────────────────────
    # brief subset: hanya fields yang dibutuhkan oleh Content Writer Agent
    selected_content_package = {
        "application_id": application_id,
        "brief_id": brief_id,
        "brief": {
            "primary_angle": strategy_brief.get("primary_angle"),
            "summary_hook_direction": strategy_brief.get("summary_hook_direction"),
            "keyword_targets": strategy_brief.get("keyword_targets", []),
            "tone": strategy_brief.get("tone", "technical_concise"),
            "narrative_instructions": strategy_brief.get("narrative_instructions", []),
        },
        "selected_content": selected_content,
    }

    # ── Simpan ke selected_content_packages table ─────────────────────────────
    supabase.table("selected_content_packages").insert({
        "application_id": application_id,
        "brief_id": brief_id,
        "content": selected_content_package,
    }).execute()

    total_selected = sum(len(v) for v in selected_content.values())
    logger.info(
        f"[run_selection] package saved — {total_selected} total entries selected "
        f"for application_id={application_id}"
    )

    return selected_content_package