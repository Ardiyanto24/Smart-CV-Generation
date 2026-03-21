-- Migration: Create experience table
-- Cluster 1 — Master Data
-- Stores professional work experience entries per user.
-- what_i_did is NOT NULL (required, unlike education).

CREATE TABLE IF NOT EXISTS public.experience (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    company     VARCHAR(255) NOT NULL,
    role        VARCHAR(255) NOT NULL,
    start_date  DATE,
    end_date    DATE,
    is_current  BOOLEAN DEFAULT FALSE,
    what_i_did  TEXT[] NOT NULL,
    challenge   TEXT[],
    impact      TEXT[],
    skills_used TEXT[],
    is_inferred BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.experience IS 'Professional work experience entries. what_i_did is required.';
COMMENT ON COLUMN public.experience.is_inferred IS 'True if skills were inferred by Profile Ingestion Agent.';