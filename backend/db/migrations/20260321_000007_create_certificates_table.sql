-- Migration: Create certificates table
-- Cluster 1 — Master Data
-- Simple metadata listing — no what_i_did/challenge/impact/skills_used.
-- Profile Ingestion Agent does NOT process this table.

CREATE TABLE IF NOT EXISTS public.certificates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    issuer      VARCHAR(255),
    issue_date  DATE,
    expiry_date DATE,
    url         VARCHAR(500),
    is_inferred BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.certificates IS 'Certificate metadata only. No activity narrative columns.';
COMMENT ON COLUMN public.certificates.expiry_date IS 'Nullable — not all certificates expire (e.g. degrees).';
COMMENT ON COLUMN public.certificates.url IS 'Verification link. VARCHAR(500) for long URLs.';