-- Migration: Create job_descriptions table
-- Cluster 2 — Job Analyzer
-- Stores atomic JD responsibility items parsed by Parser Agent.
-- Each row = one atomic responsibility (one thing the role will do).
-- responsibility_id assigned by Parser Agent (e.g. d001, d002).
-- No updated_at — immutable. Re-parsing creates new rows.

CREATE TABLE IF NOT EXISTS public.job_descriptions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id    UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    responsibility_id VARCHAR(10) NOT NULL,
    text              TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.job_descriptions IS 'Atomic JD responsibility items. Each row is one parsed responsibility.';
COMMENT ON COLUMN public.job_descriptions.responsibility_id IS 'Short ID assigned by Parser Agent (e.g. d001). Used for cross-table references.';