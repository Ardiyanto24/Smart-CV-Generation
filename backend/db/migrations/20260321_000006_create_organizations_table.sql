-- Migration: Create organizations table
-- Cluster 1 — Master Data
-- Stores organizational and extracurricular activity entries per user.
-- Similar to experience but role is nullable and what_i_did is optional.

CREATE TABLE IF NOT EXISTS public.organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    role        VARCHAR(255),
    start_date  DATE,
    end_date    DATE,
    is_current  BOOLEAN DEFAULT FALSE,
    what_i_did  TEXT[],
    challenge   TEXT[],
    impact      TEXT[],
    skills_used TEXT[],
    is_inferred BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.organizations IS 'Organizational and extracurricular activity entries per user.';
COMMENT ON COLUMN public.organizations.role IS 'Nullable — not all members have a formal title.';