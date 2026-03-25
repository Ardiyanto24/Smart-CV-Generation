# cv-agent/backend/agents/cluster6/ats_scoring.py

"""
ATS Scoring Agent — Cluster 6

Mengevaluasi CV output dari perspektif ATS keyword compatibility.

Dua bagian:
  Part 1: Kalkulasi weighted keyword score — deterministik, tanpa LLM
  Part 2: LLM Preserve Analyzer — identifikasi apa yang harus dipertahankan

Dijalankan paralel dengan Semantic Reviewer Agent di qc_evaluate node.

Prompts dikelola di: agents/prompts/ats_scoring_prompt.py
"""

import json
import logging
import re

from agents.llm_client import call_llm
from agents.prompts.ats_scoring_prompt import ATS_PRESERVE_SYSTEM

logger = logging.getLogger("agents.cluster6.ats_scoring")

# ── Abbreviation map untuk common technical terms ─────────────────────────────
# Key: full term (lowercase), Value: list of accepted abbreviations
# Dipakai untuk mendeteksi keyword match meskipun ditulis dengan singkatan
ABBREVIATION_MAP: dict[str, list[str]] = {
    "machine learning":         ["ml"],
    "artificial intelligence":  ["ai"],
    "natural language processing": ["nlp"],
    "large language model":     ["llm", "llms"],
    "application programming interface": ["api", "apis"],
    "continuous integration":   ["ci"],
    "continuous deployment":    ["cd"],
    "continuous integration and deployment": ["ci/cd", "cicd"],
    "user interface":           ["ui"],
    "user experience":          ["ux"],
    "user interface and experience": ["ui/ux"],
    "amazon web services":      ["aws"],
    "google cloud platform":    ["gcp"],
    "microsoft azure":          ["azure"],
    "kubernetes":               ["k8s"],
    "infrastructure as code":   ["iac"],
    "object oriented programming": ["oop"],
    "structured query language": ["sql"],
    "extract transform load":   ["etl"],
    "key performance indicator": ["kpi", "kpis"],
    "return on investment":     ["roi"],
    "minimum viable product":   ["mvp"],
    "software development lifecycle": ["sdlc"],
    "agile software development": ["agile"],
    "test driven development":  ["tdd"],
    "domain driven design":     ["ddd"],
    "convolutional neural network": ["cnn"],
    "recurrent neural network": ["rnn"],
    "deep learning":            ["dl"],
    "exploratory data analysis": ["eda"],
    "business intelligence":    ["bi"],
    "power business intelligence": ["power bi"],
}

# Reverse map: abbreviation → full term (untuk lookup saat checking)
_ABBREV_REVERSE: dict[str, str] = {}
for full, abbrevs in ABBREVIATION_MAP.items():
    for abbrev in abbrevs:
        _ABBREV_REVERSE[abbrev] = full


def _flatten_cv_text(cv_output: dict) -> str:
    """
    Flatten seluruh CV output menjadi satu lowercase string untuk keyword matching.

    Mengumpulkan: summary, semua bullets dari semua sections, semua skill names.
    Sections yang di-flatten: summary, experience, education, awards,
    projects, organizations, skills.

    Returns:
        Satu string lowercase yang berisi seluruh teks CV
    """
    parts = []

    # Summary
    if cv_output.get("summary"):
        parts.append(str(cv_output["summary"]))

    # List sections — experience, education, awards, projects, organizations
    for section_name in ["experience", "education", "awards", "projects", "organizations"]:
        entries = cv_output.get(section_name, [])
        if isinstance(entries, list):
            for entry in entries:
                # Tambahkan title/company/role untuk context matching
                for field in ["company", "role", "institution", "degree", "title", "name"]:
                    if entry.get(field):
                        parts.append(str(entry[field]))
                # Bullets adalah konten utama
                for bullet in entry.get("bullets", []):
                    parts.append(str(bullet))

    # Skills — dari skills_grouped structure
    skills_data = cv_output.get("skills", {})
    if isinstance(skills_data, dict):
        for group in skills_data.get("skills_grouped", []):
            for item in group.get("items", []):
                parts.append(str(item))

    return " ".join(parts).lower()


def _get_section_text(entry: dict) -> str:
    """
    Ambil text content dari satu CV entry untuk per-section keyword matching.
    """
    parts = []
    for field in ["company", "role", "institution", "degree", "title", "name", "summary"]:
        if entry.get(field):
            parts.append(str(entry[field]))
    for bullet in entry.get("bullets", []):
        parts.append(str(bullet))
    # Untuk summary yang berupa string langsung
    if isinstance(entry, str):
        parts.append(entry)
    return " ".join(parts).lower()


def _keyword_found_in_text(keyword: str, text: str) -> bool:
    """
    Check apakah keyword ada di text, dengan abbreviation expansion.

    Cek dua arah:
    1. Keyword langsung (case-insensitive)
    2. Abbreviation dari keyword (kalau keyword ada di ABBREVIATION_MAP)
    3. Full form dari abbreviation (kalau keyword adalah abbreviation di _ABBREV_REVERSE)
    """
    keyword_lower = keyword.lower()

    # Direct match
    if keyword_lower in text:
        return True

    # Keyword → abbreviation check
    if keyword_lower in ABBREVIATION_MAP:
        for abbrev in ABBREVIATION_MAP[keyword_lower]:
            if abbrev in text:
                return True

    # Abbreviation → full term check (reverse)
    if keyword_lower in _ABBREV_REVERSE:
        full_term = _ABBREV_REVERSE[keyword_lower]
        if full_term in text:
            return True

    return False


def _calculate_weighted_score(
    keyword_targets: list,
    job_requirements: list,
    cv_text: str,
) -> tuple[float, list, list, dict]:
    """
    Part 1: Kalkulasi weighted keyword score secara deterministik.

    Builds unified keyword pool dari dua sumber:
    - job_requirements: weight 1.0 untuk must, 0.5 untuk nice_to_have
    - keyword_targets: weight 0.8

    Returns:
        tuple of:
        - weighted_score (float, 0-100)
        - keywords_found (list of str)
        - keywords_missed (list of str)
        - keyword_weights (dict: keyword → weight, untuk logging)
    """
    # Build keyword pool — deduplicate dengan prefer higher weight
    keyword_pool: dict[str, float] = {}

    # Dari job_requirements
    for req in job_requirements:
        text = req.get("text", "").strip()
        if not text:
            continue
        priority = req.get("priority", "must")
        weight = 1.0 if priority == "must" else 0.5

        # Gunakan lowercase sebagai key untuk deduplication
        key = text.lower()
        if key not in keyword_pool or keyword_pool[key] < weight:
            keyword_pool[key] = weight

    # Dari keyword_targets — weight 0.8
    for kw in keyword_targets:
        if not kw:
            continue
        key = kw.lower()
        # Jika sudah ada dari requirements dengan weight lebih tinggi, skip
        if key not in keyword_pool or keyword_pool[key] < 0.8:
            keyword_pool[key] = 0.8

    if not keyword_pool:
        logger.warning("[_calculate_weighted_score] empty keyword pool")
        return 0.0, [], [], {}

    # Hitung weighted score
    total_weight = 0.0
    weighted_found = 0.0
    keywords_found = []
    keywords_missed = []

    for keyword, weight in keyword_pool.items():
        total_weight += weight
        if _keyword_found_in_text(keyword, cv_text):
            weighted_found += weight
            keywords_found.append(keyword)
        else:
            keywords_missed.append(keyword)

    weighted_score = round((weighted_found / total_weight) * 100, 2) if total_weight > 0 else 0.0

    logger.info(
        f"[_calculate_weighted_score] "
        f"pool={len(keyword_pool)} keywords, "
        f"found={len(keywords_found)}, "
        f"missed={len(keywords_missed)}, "
        f"score={weighted_score}"
    )

    return weighted_score, keywords_found, keywords_missed, keyword_pool


def _build_section_keyword_presence(
    cv_output: dict,
    keyword_pool: dict,
) -> list:
    """
    Build per-section keyword presence data.

    Untuk setiap section entry di CV, cek keywords mana yang ada
    di content section tersebut. Dipakai oleh LLM Preserve Analyzer
    untuk tahu context keyword per section.

    Returns:
        List of dicts: [{"section": str, "entry_id": str|None, "keywords_found": list}]
    """
    section_presence = []

    all_keywords = list(keyword_pool.keys())

    # Summary — section-level, tidak punya entry_id
    if cv_output.get("summary"):
        summary_text = str(cv_output["summary"]).lower()
        found_here = [kw for kw in all_keywords if _keyword_found_in_text(kw, summary_text)]
        if found_here:
            section_presence.append({
                "section": "summary",
                "entry_id": None,
                "keywords_found": found_here,
            })

    # List sections
    for section_name in ["experience", "education", "awards", "projects", "organizations"]:
        entries = cv_output.get(section_name, [])
        if isinstance(entries, list):
            for entry in entries:
                section_text = _get_section_text(entry)
                found_here = [
                    kw for kw in all_keywords
                    if _keyword_found_in_text(kw, section_text)
                ]
                if found_here:
                    section_presence.append({
                        "section": section_name,
                        "entry_id": entry.get("entry_id"),
                        "keywords_found": found_here,
                    })

    # Skills — section-level
    skills_data = cv_output.get("skills", {})
    if isinstance(skills_data, dict):
        skills_text = " ".join(
            item
            for group in skills_data.get("skills_grouped", [])
            for item in group.get("items", [])
        ).lower()
        found_here = [kw for kw in all_keywords if _keyword_found_in_text(kw, skills_text)]
        if found_here:
            section_presence.append({
                "section": "skills",
                "entry_id": None,
                "keywords_found": found_here,
            })

    return section_presence


async def run_ats_scoring(
    cv_output: dict,
    keyword_targets: list,
    job_requirements: list,
) -> dict:
    """
    Run ATS scoring — Part 1 deterministik + Part 2 LLM Preserve Analyzer.

    Part 1 menghasilkan:
    - weighted_score (0-100)
    - keywords_found, keywords_missed
    - per-section keyword presence

    Part 2 menghasilkan:
    - section_analysis: apa yang harus dipertahankan per section

    Dijalankan secara paralel dengan Semantic Reviewer di qc_evaluate node.

    Args:
        cv_output: Final Structured Output JSON dari state["cv_output"]
        keyword_targets: list of keyword strings dari strategy_brief
        job_requirements: list of requirement objects dari jd_jr_context

    Returns:
        dict berisi weighted_score, keywords_found, keywords_missed,
        section_presence, dan section_analysis dari LLM
    """
    logger.info("[run_ats_scoring] starting ATS scoring")

    # ── Part 1: Deterministik ─────────────────────────────────────────────────
    cv_text = _flatten_cv_text(cv_output)

    weighted_score, keywords_found, keywords_missed, keyword_pool = (
        _calculate_weighted_score(keyword_targets, job_requirements, cv_text)
    )

    section_presence = _build_section_keyword_presence(cv_output, keyword_pool)

    logger.info(
        f"[run_ats_scoring] Part 1 complete: "
        f"score={weighted_score}, "
        f"found={len(keywords_found)}, missed={len(keywords_missed)}, "
        f"sections_with_keywords={len(section_presence)}"
    )

    # ── Part 2: LLM Preserve Analyzer ────────────────────────────────────────
    # Kirim CV content + hasil keyword analysis ke LLM
    # LLM mengidentifikasi apa yang harus dipertahankan saat revisi nanti
    # System prompt dikelola di agents/prompts/ats_scoring_prompt.py

    # Build CV sections snapshot — hanya konten yang relevan untuk preserve analysis
    cv_sections_for_llm = {
        "summary": cv_output.get("summary", ""),
    }
    for section_name in ["experience", "education", "awards", "projects", "organizations"]:
        entries = cv_output.get(section_name, [])
        if isinstance(entries, list) and entries:
            cv_sections_for_llm[section_name] = [
                {
                    "entry_id": e.get("entry_id"),
                    "title": e.get("company") or e.get("title") or e.get("institution") or e.get("name"),
                    "bullets": e.get("bullets", []),
                }
                for e in entries
            ]

    user_prompt = f"""Analyze this CV for ATS preservation targets.

CV SECTIONS:
{json.dumps(cv_sections_for_llm, ensure_ascii=False, indent=2)}

KEYWORD ANALYSIS:
Keywords found: {json.dumps(keywords_found)}
Keywords missed: {json.dumps(keywords_missed)}
Per-section keyword presence: {json.dumps(section_presence, ensure_ascii=False, indent=2)}

Identify what should be preserved in each section to maintain ATS compatibility."""

    raw_response = await call_llm(
        system_prompt=ATS_PRESERVE_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=1000,
    )

    # ── Parse LLM response ────────────────────────────────────────────────────
    try:
        preserve_result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[run_ats_scoring] LLM Preserve Analyzer returned unparseable JSON. "
            f"Raw: {raw_response[:300]}"
        )
        raise ValueError(f"ATS Preserve Analyzer returned invalid JSON: {e}")

    section_analysis = preserve_result.get("section_analysis", [])

    logger.info(
        f"[run_ats_scoring] Part 2 complete: "
        f"{len(section_analysis)} sections analyzed for preserve targets"
    )

    # ── Combine results ───────────────────────────────────────────────────────
    return {
        "weighted_score": weighted_score,
        "keywords_found": keywords_found,
        "keywords_missed": keywords_missed,
        "section_presence": section_presence,
        "section_analysis": section_analysis,
    }