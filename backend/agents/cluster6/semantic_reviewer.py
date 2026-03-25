# cv-agent/backend/agents/cluster6/semantic_reviewer.py

"""
Semantic Reviewer Agent — Cluster 6

Mengevaluasi setiap CV section terhadap JD/JR items yang relevan
dari perspektif semantic — relevansi narasi, convincingness, dan
compliance terhadap narrative instructions.

Fixed section-to-JD/JR mapping (dari spec Section 5):
  summary       → semua JD + JR
  experience    → semua JD + semua JR
  projects      → technical JR + JD responsibilities
  education     → education JR
  awards        → domain-specific JR
  skills        → hard skill JR
  organizations → soft skill JR
  certificates  → certification JR

Setiap section diproses paralel via asyncio.gather.

Prompts dikelola di: agents/prompts/semantic_reviewer_prompt.py
"""

import asyncio
import json
import logging

from agents.llm_client import call_llm
from agents.prompts.semantic_reviewer_prompt import SEMANTIC_REVIEWER_SYSTEM
from config import get_settings

logger = logging.getLogger("agents.cluster6.semantic_reviewer")


def _filter_jd_jr_for_section(
    section_name: str,
    jd_items: list,
    jr_items: list,
) -> list:
    """
    Filter JD/JR items yang relevan untuk section tertentu.

    Fixed mapping dari cluster6_specification Section 5:
    - summary       : semua JD + semua JR
    - experience    : semua JD + semua JR
    - projects      : technical JR + JD responsibilities
    - education     : education JR
    - awards        : domain-specific JR
    - skills        : hard skill JR
    - organizations : soft skill JR
    - certificates  : certification JR

    Untuk filtering berbasis konten (technical, education, soft, domain),
    kita pakai heuristic keyword matching pada teks requirement.

    Args:
        section_name: nama section CV
        jd_items: list of JD items dari jd_jr_context["job_descriptions"]
        jr_items: list of JR items dari jd_jr_context["job_requirements"]

    Returns:
        List of relevant JD/JR item objects, masing-masing dengan
        "text", "dimension" (JD/JR), dan optional "priority"
    """
    # Normalize — label dimension ke setiap item
    jd_labeled = [
        {**item, "dimension": "JD"}
        for item in jd_items
    ]
    jr_labeled = [
        {**item, "dimension": "JR"}
        for item in jr_items
    ]

    if section_name in ("summary", "experience"):
        # Summary dan experience: semua JD + semua JR
        return jd_labeled + jr_labeled

    if section_name == "projects":
        # Technical JR + JD responsibilities
        technical_keywords = {
            "python", "sql", "java", "javascript", "typescript", "r",
            "framework", "library", "machine learning", "ml", "ai",
            "data", "model", "api", "backend", "frontend", "cloud",
            "aws", "gcp", "azure", "docker", "kubernetes", "database",
            "algorithm", "analytics", "pipeline", "architecture",
            "system", "software", "code", "programming", "develop",
            "build", "implement", "deploy", "engineer",
        }
        technical_jr = [
            item for item in jr_labeled
            if any(kw in item.get("text", "").lower() for kw in technical_keywords)
        ]
        return jd_labeled + technical_jr

    if section_name == "education":
        # Education requirements dari JR
        education_keywords = {
            "degree", "bachelor", "master", "phd", "s1", "s2", "s3",
            "sarjana", "magister", "diploma", "gelar", "jurusan",
            "universitas", "university", "college", "gpa", "ipk",
            "pendidikan", "education", "study", "graduate", "lulusan",
            "ilmu komputer", "computer science", "informatika",
            "statistics", "statistika", "mathematics", "matematika",
            "engineering", "teknik",
        }
        edu_jr = [
            item for item in jr_labeled
            if any(kw in item.get("text", "").lower() for kw in education_keywords)
        ]
        return edu_jr

    if section_name == "awards":
        # Domain-specific JR — requirements yang menyebut prestasi atau kompetisi
        domain_keywords = {
            "award", "penghargaan", "kompetisi", "competition", "achievement",
            "winner", "juara", "recognition", "certification", "sertifikasi",
            "experience", "pengalaman", "domain", "expertise", "keahlian",
        }
        domain_jr = [
            item for item in jr_labeled
            if any(kw in item.get("text", "").lower() for kw in domain_keywords)
        ]
        # Fallback kalau tidak ada yang cocok: ambil semua must requirements
        if not domain_jr:
            domain_jr = [item for item in jr_labeled if item.get("priority") == "must"]
        return domain_jr

    if section_name == "skills":
        # Hard skill requirements — explicit technical skill mentions
        hard_skill_keywords = {
            "menguasai", "memiliki kemampuan", "skilled in", "proficient",
            "experience with", "knowledge of", "familiar with",
            "python", "sql", "java", "javascript", "typescript",
            "framework", "tool", "platform", "software", "technology",
            "machine learning", "data", "cloud", "aws", "gcp", "azure",
            "programming", "coding", "scripting",
        }
        hard_skill_jr = [
            item for item in jr_labeled
            if any(kw in item.get("text", "").lower() for kw in hard_skill_keywords)
        ]
        return hard_skill_jr

    if section_name == "organizations":
        # Soft skill requirements
        soft_skill_keywords = {
            "komunikasi", "communication", "leadership", "kepemimpinan",
            "teamwork", "kolaborasi", "collaboration", "interpersonal",
            "presentasi", "presentation", "negosiasi", "negotiation",
            "problem solving", "analytical", "analytical thinking",
            "stakeholder", "manajemen", "management", "organizational",
            "soft skill", "attitude", "proactive",
        }
        soft_skill_jr = [
            item for item in jr_labeled
            if any(kw in item.get("text", "").lower() for kw in soft_skill_keywords)
        ]
        return soft_skill_jr

    if section_name == "certificates":
        # Certification requirements
        cert_keywords = {
            "sertifikat", "sertifikasi", "certificate", "certification",
            "certified", "license", "lisensi", "accredited", "credential",
            "aws certified", "google certified", "microsoft certified",
        }
        cert_jr = [
            item for item in jr_labeled
            if any(kw in item.get("text", "").lower() for kw in cert_keywords)
        ]
        return cert_jr

    # Default fallback: return semua JR must requirements
    return [item for item in jr_labeled if item.get("priority") == "must"]


async def _review_section(
    section_name: str,
    entry: dict | str,
    entry_id: str | None,
    relevant_jd_jr: list,
    narrative_instructions: list,
    threshold: int,
) -> dict:
    """
    Helper: evaluate satu section atau satu entry dalam section.
    Dipanggil secara paralel untuk semua sections.

    Args:
        section_name: nama section ("experience", "projects", dll)
        entry: dict berisi content section/entry, atau string untuk summary
        entry_id: UUID entry atau None untuk section-level
        relevant_jd_jr: list JD/JR yang relevan untuk section ini
        narrative_instructions: list dari brief — hanya approved/adjusted yang dievaluasi
        threshold: SEMANTIC_THRESHOLD dari settings

    Returns:
        dict berisi section, entry_id, semantic_score, verdict,
        strengths, issues, revise
    """
    logger.info(
        f"[_review_section] reviewing section={section_name}, "
        f"entry_id={entry_id}"
    )

    # Filter narrative instructions yang approved/adjusted dan relevan untuk section ini
    # null dan rejected diabaikan — sesuai prinsip yang sama dengan Content Writer
    approved_instructions = [
        ni for ni in narrative_instructions
        if ni.get("user_decision") in ("approved", "adjusted")
    ]

    # Build content snapshot untuk LLM
    if section_name == "summary":
        content_for_llm = {"text": entry if isinstance(entry, str) else str(entry)}
    elif section_name == "skills":
        # Skills punya struktur berbeda — skills_grouped
        content_for_llm = entry if isinstance(entry, dict) else {}
    else:
        # List sections — experience, education, awards, projects, organizations
        content_for_llm = {
            k: v for k, v in entry.items()
            if k not in ("user_id", "application_id", "created_at", "updated_at", "bullet_quota")
        } if isinstance(entry, dict) else {}

    # User prompt untuk satu section
    user_prompt = f"""Evaluate this CV section against the relevant job requirements.

SECTION: {section_name}
ENTRY_ID: {entry_id or "N/A"}

CV CONTENT:
{json.dumps(content_for_llm, ensure_ascii=False, indent=2)}

RELEVANT JD/JR ITEMS ({len(relevant_jd_jr)} items):
{json.dumps(relevant_jd_jr, ensure_ascii=False, indent=2)}

NARRATIVE INSTRUCTIONS TO VERIFY ({len(approved_instructions)} approved):
{json.dumps(approved_instructions, ensure_ascii=False, indent=2)}

THRESHOLD: {threshold} (score >= {threshold} = passed)

Evaluate all three dimensions and return your assessment as JSON."""

    raw_response = await call_llm(
        system_prompt=SEMANTIC_REVIEWER_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=600,
    )

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            f"[_review_section] unparseable JSON for "
            f"section={section_name}, entry_id={entry_id}. "
            f"Raw: {raw_response[:300]}"
        )
        raise ValueError(
            f"Semantic Reviewer returned invalid JSON for "
            f"section={section_name}: {e}"
        )

    # Normalize fields
    result.setdefault("section", section_name)
    result.setdefault("entry_id", entry_id)
    result.setdefault("strengths", [])
    result.setdefault("issues", [])
    result.setdefault("revise", [])

    # Enforce verdict consistency dengan threshold
    score = result.get("semantic_score", 0)
    if score >= threshold:
        result["verdict"] = "passed"
        result["issues"] = []
        result["revise"] = []
    else:
        result["verdict"] = "failed"

    logger.info(
        f"[_review_section] section={section_name}, "
        f"entry_id={entry_id}: score={score}, verdict={result['verdict']}"
    )

    return result


async def run_semantic_review(
    cv_output: dict,
    jd_jr_context: dict,
    narrative_instructions: list,
) -> list:
    """
    Run semantic review for all CV sections in parallel.

    Setiap section mendapat satu LLM call dengan relevant JD/JR yang sudah
    di-filter sesuai fixed mapping dari spec Section 5.

    Multi-entry sections (experience, education, awards, projects, organizations)
    di-evaluate per entry — setiap entry adalah satu LLM call.

    Args:
        cv_output: Final Structured Output JSON dari state["cv_output"]
        jd_jr_context: Context Package 2 — berisi job_descriptions dan job_requirements
        narrative_instructions: list dari strategy_brief

    Returns:
        List of per-section review result dicts, satu per section/entry
    """
    logger.info("[run_semantic_review] starting semantic review")

    settings = get_settings()
    threshold = settings.semantic_threshold

    jd_items = jd_jr_context.get("job_descriptions", [])
    jr_items = jd_jr_context.get("job_requirements", [])

    # ── Build coroutines untuk semua sections ─────────────────────────────────
    review_coroutines = []

    # Summary — section-level, satu call
    if cv_output.get("summary"):
        relevant = _filter_jd_jr_for_section("summary", jd_items, jr_items)
        if relevant:
            review_coroutines.append(
                _review_section(
                    section_name="summary",
                    entry=cv_output["summary"],
                    entry_id=None,
                    relevant_jd_jr=relevant,
                    narrative_instructions=narrative_instructions,
                    threshold=threshold,
                )
            )

    # List sections — satu call per entry
    for section_name in ["experience", "education", "awards", "projects", "organizations"]:
        entries = cv_output.get(section_name, [])
        if not isinstance(entries, list) or not entries:
            continue

        relevant = _filter_jd_jr_for_section(section_name, jd_items, jr_items)
        if not relevant:
            logger.info(
                f"[run_semantic_review] no relevant JD/JR for section={section_name}, "
                f"skipping"
            )
            continue

        for entry in entries:
            review_coroutines.append(
                _review_section(
                    section_name=section_name,
                    entry=entry,
                    entry_id=entry.get("entry_id"),
                    relevant_jd_jr=relevant,
                    narrative_instructions=narrative_instructions,
                    threshold=threshold,
                )
            )

    # Skills — section-level, satu call
    skills_data = cv_output.get("skills", {})
    if isinstance(skills_data, dict) and skills_data.get("skills_grouped"):
        relevant = _filter_jd_jr_for_section("skills", jd_items, jr_items)
        if relevant:
            review_coroutines.append(
                _review_section(
                    section_name="skills",
                    entry=skills_data,
                    entry_id=None,
                    relevant_jd_jr=relevant,
                    narrative_instructions=narrative_instructions,
                    threshold=threshold,
                )
            )

    # Organizations — satu call per entry
    orgs = cv_output.get("organizations", [])
    if isinstance(orgs, list) and orgs:
        relevant = _filter_jd_jr_for_section("organizations", jd_items, jr_items)
        if relevant:
            for entry in orgs:
                review_coroutines.append(
                    _review_section(
                        section_name="organizations",
                        entry=entry,
                        entry_id=entry.get("entry_id"),
                        relevant_jd_jr=relevant,
                        narrative_instructions=narrative_instructions,
                        threshold=threshold,
                    )
                )

    # Certificates — section-level, satu call
    certs = cv_output.get("certificates", [])
    if isinstance(certs, list) and certs:
        relevant = _filter_jd_jr_for_section("certificates", jd_items, jr_items)
        if relevant:
            review_coroutines.append(
                _review_section(
                    section_name="certificates",
                    entry={"certificates": certs},
                    entry_id=None,
                    relevant_jd_jr=relevant,
                    narrative_instructions=narrative_instructions,
                    threshold=threshold,
                )
            )

    if not review_coroutines:
        logger.warning("[run_semantic_review] no sections to review")
        return []

    logger.info(
        f"[run_semantic_review] running {len(review_coroutines)} section reviews in parallel"
    )

    # ── Parallel execution ────────────────────────────────────────────────────
    results = await asyncio.gather(*review_coroutines)

    passed = sum(1 for r in results if r.get("verdict") == "passed")
    failed = sum(1 for r in results if r.get("verdict") == "failed")

    logger.info(
        f"[run_semantic_review] complete: "
        f"{len(results)} sections reviewed, "
        f"passed={passed}, failed={failed}"
    )

    return list(results)