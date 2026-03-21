-- Migration: Create education table
-- Cluster 1 — Master Data
-- Stores educational background entries per user.
-- what_i_did is nullable (optional for education, unlike experience).

CREATE TABLE IF NOT EXISTS public.education (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    institution    VARCHAR(255) NOT NULL,
    degree         VARCHAR(255),
    field_of_study VARCHAR(255),
    start_date     DATE,
    end_date       DATE,
    is_current     BOOLEAN DEFAULT FALSE,
    what_i_did     TEXT[],
    challenge      TEXT[],
    impact         TEXT[],
    skills_used    TEXT[],
    is_inferred    BOOLEAN DEFAULT FALSE,
    created_at     TIMESTAMP DEFAULT NOW(),
    updated_at     TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.education IS 'Educational background entries. what_i_did is optional unlike experience.';
COMMENT ON COLUMN public.education.is_inferred IS 'True if skills were inferred by Profile Ingestion Agent.';