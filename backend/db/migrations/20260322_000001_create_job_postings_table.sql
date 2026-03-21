-- Migration: Create job_postings table
-- Cluster 2 — Job Analyzer
-- Stores raw JD/JR text as submitted by user — immutable audit trail.
-- Kept separate from parsed results to enable future re-parsing.
-- No updated_at — raw input is never modified after submission.

CREATE TABLE IF NOT EXISTS public.job_postings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    jd_raw         TEXT,
    jr_raw         TEXT,
    created_at     TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.job_postings IS 'Raw JD/JR input — immutable audit trail. No updated_at by design.';
COMMENT ON COLUMN public.job_postings.jd_raw IS 'Full raw Job Description text as submitted by user.';
COMMENT ON COLUMN public.job_postings.jr_raw IS 'Full raw Job Requirements text as submitted by user.';