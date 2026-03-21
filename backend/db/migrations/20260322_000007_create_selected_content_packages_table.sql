-- Migration: Create selected_content_packages table
-- Cluster 4 — Orchestrator
-- Stores Selection Agent output — exact Master Data subset for CV generation.
-- brief_id links package to the specific brief version that produced it.
-- No updated_at — brief changes create new packages, never mutate old ones.

CREATE TABLE IF NOT EXISTS public.selected_content_packages (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    brief_id       UUID NOT NULL REFERENCES public.cv_strategy_briefs(id) ON DELETE CASCADE,
    content        JSONB NOT NULL,
    created_at     TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.selected_content_packages IS 'Selection Agent output. Exact Master Data subset chosen for CV generation.';
COMMENT ON COLUMN public.selected_content_packages.brief_id IS 'Links package to the brief version that produced it. Enables audit trail.';
COMMENT ON COLUMN public.selected_content_packages.content IS 'Full selected content per component: experience, projects, education, etc.';