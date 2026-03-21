-- Migration: Create applications table
-- Cluster 2 — Job Analyzer
-- Anchor table for every job application in the system.
-- All tables from Cluster 2 through Cluster 6 reference this table.

CREATE TABLE IF NOT EXISTS public.applications (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    position     VARCHAR(255) NOT NULL,
    status       VARCHAR(50) NOT NULL DEFAULT 'draft'
                 CHECK (status IN ('draft', 'applied', 'interview',
                                   'offer', 'rejected', 'accepted')),
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.applications IS 'Anchor table for job applications. All downstream tables cascade from here.';
COMMENT ON COLUMN public.applications.status IS 'Application tracking status. Defaults to draft on creation.';