-- Migration: Create qc_overall_scores table
-- Cluster 6 — Quality Control
-- One row per QC run (cv_version + iteration).
-- Aggregate summary across all sections in that run.
-- Companion to qc_results — overall vs per-section detail.

CREATE TABLE IF NOT EXISTS public.qc_overall_scores (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id   UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    cv_version       INTEGER NOT NULL,
    iteration        INTEGER NOT NULL DEFAULT 1,
    overall_ats_score NUMERIC(5,2),
    sections_passed  INTEGER,
    sections_failed  INTEGER,
    created_at       TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.qc_overall_scores IS 'Aggregate QC summary per run. One row per cv_version + iteration.';
COMMENT ON COLUMN public.qc_overall_scores.overall_ats_score IS 'Weighted average ATS score across all sections in this QC run.';
COMMENT ON COLUMN public.qc_overall_scores.sections_passed IS 'Count of sections where action_required = false.';
COMMENT ON COLUMN public.qc_overall_scores.sections_failed IS 'Count of sections where action_required = true.';