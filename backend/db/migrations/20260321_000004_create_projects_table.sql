-- Migration: Create projects table
-- Cluster 1 — Master Data
-- Stores personal or professional project entries per user.
-- url is VARCHAR(500) to accommodate long GitHub/project URLs.

CREATE TABLE IF NOT EXISTS public.projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL,
    url         VARCHAR(500),
    start_date  DATE,
    end_date    DATE,
    what_i_did  TEXT[] NOT NULL,
    challenge   TEXT[],
    impact      TEXT[],
    skills_used TEXT[],
    is_inferred BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.projects IS 'Personal or professional project entries per user.';
COMMENT ON COLUMN public.projects.url IS 'Project URL or GitHub link. VARCHAR(500) to accommodate long URLs.';