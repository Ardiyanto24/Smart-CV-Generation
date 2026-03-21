-- Migration: Create skills table
-- Cluster 1 — Master Data
-- Aggregated view of all user skills — manual input and agent-inferred.
-- Uses case-insensitive unique index to prevent duplicate skill names.

CREATE TABLE IF NOT EXISTS public.skills (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    category    VARCHAR(50) NOT NULL CHECK (category IN ('technical', 'soft', 'tool')),
    is_inferred BOOLEAN DEFAULT FALSE,
    source      TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Case-insensitive unique constraint: prevents "Python" and "python" as separate entries
CREATE UNIQUE INDEX IF NOT EXISTS skills_user_id_name_unique
    ON public.skills (user_id, lower(name));

COMMENT ON TABLE public.skills IS 'Aggregated skills per user — manual and agent-inferred.';
COMMENT ON COLUMN public.skills.is_inferred IS 'True when suggested by Profile Ingestion Agent and approved by user.';
COMMENT ON COLUMN public.skills.source IS 'Human-readable explanation of inference source for UI transparency.';
COMMENT ON COLUMN public.skills.category IS 'Constrained to: technical, soft, tool.';