-- Migration: Create job_requirements table
-- Cluster 2 — Job Analyzer
-- Stores atomic requirement items parsed from JD and/or JR by Parser Agent.
-- source = 'JD+JR' when Parser Agent deduplicates identical items from both sources.
-- priority detected from linguistic signals in original text.
-- No updated_at — immutable. Re-parsing creates new rows.

CREATE TABLE IF NOT EXISTS public.job_requirements (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    requirement_id VARCHAR(10) NOT NULL,
    text           TEXT NOT NULL,
    source         VARCHAR(10) NOT NULL CHECK (source IN ('JD', 'JR', 'JD+JR')),
    priority       VARCHAR(20) NOT NULL CHECK (priority IN ('must', 'nice_to_have')),
    created_at     TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.job_requirements IS 'Atomic requirement items parsed from JD/JR. Each row is one requirement.';
COMMENT ON COLUMN public.job_requirements.source IS 'JD+JR means deduplicated — same requirement appeared in both sources.';
COMMENT ON COLUMN public.job_requirements.priority IS 'Detected from linguistic signals. Default must, nice_to_have if signaled.';
COMMENT ON COLUMN public.job_requirements.requirement_id IS 'Short ID assigned by Parser Agent (e.g. r001). Used for cross-table references.';