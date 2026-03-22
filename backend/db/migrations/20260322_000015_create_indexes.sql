-- Migration: Create performance indexes
-- Covers most frequent query patterns across all clusters.
-- All indexes use CREATE INDEX IF NOT EXISTS for idempotency.

-- ── Cluster 1 — Master Data (user_id lookups) ────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_experience_user_id
    ON public.experience(user_id);

CREATE INDEX IF NOT EXISTS idx_projects_user_id
    ON public.projects(user_id);

CREATE INDEX IF NOT EXISTS idx_education_user_id
    ON public.education(user_id);

CREATE INDEX IF NOT EXISTS idx_awards_user_id
    ON public.awards(user_id);

CREATE INDEX IF NOT EXISTS idx_organizations_user_id
    ON public.organizations(user_id);

CREATE INDEX IF NOT EXISTS idx_certificates_user_id
    ON public.certificates(user_id);

CREATE INDEX IF NOT EXISTS idx_skills_user_id
    ON public.skills(user_id);

-- ── Cluster 2 — Applications ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_applications_user_id
    ON public.applications(user_id);

CREATE INDEX IF NOT EXISTS idx_applications_status
    ON public.applications(status);

-- ── Cluster 2 — Job data (application_id lookups) ────────────────────────────
CREATE INDEX IF NOT EXISTS idx_job_requirements_application_id
    ON public.job_requirements(application_id);

CREATE INDEX IF NOT EXISTS idx_job_descriptions_application_id
    ON public.job_descriptions(application_id);

-- ── Cluster 3 — Gap Analysis ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_gap_analysis_results_application_id
    ON public.gap_analysis_results(application_id);

-- ── Cluster 5 — CV Outputs (composite: latest version per application) ────────
CREATE INDEX IF NOT EXISTS idx_cv_outputs_application_id_version
    ON public.cv_outputs(application_id, version);

-- ── Cluster 6 — QC Results (composite: specific version + iteration) ──────────
CREATE INDEX IF NOT EXISTS idx_qc_results_application_id_version_iteration
    ON public.qc_results(application_id, cv_version, iteration);