-- Migration: Create awards table
-- Cluster 1 — Master Data
-- Stores awards, competitions, and recognition entries per user.
-- Uses single `date` column (not a range) — awards are point-in-time events.
-- what_i_did is nullable (not all awards have activity narratives).

CREATE TABLE IF NOT EXISTS public.awards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL,
    issuer      VARCHAR(255),
    date        DATE,
    what_i_did  TEXT[],
    challenge   TEXT[],
    impact      TEXT[],
    skills_used TEXT[],
    is_inferred BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.awards IS 'Awards, competitions, and recognition entries per user.';
COMMENT ON COLUMN public.awards.date IS 'Single point-in-time date, not a range. Awards occur at one moment.';