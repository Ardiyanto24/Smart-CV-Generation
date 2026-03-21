-- Migration: Create gap_analysis_results table
-- Cluster 3 — Gap Analyzer
-- One row per JD/JR item per application.
-- category determines which nullable columns are populated:
--   exact_match   → evidence populated
--   implicit_match → evidence + reasoning populated
--   gap           → suggestion populated

CREATE TABLE IF NOT EXISTS public.gap_analysis_results (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    item_id        VARCHAR(10) NOT NULL,
    text           TEXT NOT NULL,
    dimension      VARCHAR(5) NOT NULL CHECK (dimension IN ('JD', 'JR')),
    category       VARCHAR(20) NOT NULL
                   CHECK (category IN ('exact_match', 'implicit_match', 'gap')),
    priority       VARCHAR(20) CHECK (priority IN ('must', 'nice_to_have')),
    evidence       JSONB,
    reasoning      TEXT,
    suggestion     TEXT,
    created_at     TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.gap_analysis_results IS 'Gap Analyzer output. One row per JD/JR item per application.';
COMMENT ON COLUMN public.gap_analysis_results.item_id IS 'References requirement_id or responsibility_id from Cluster 2 tables.';
COMMENT ON COLUMN public.gap_analysis_results.evidence IS 'Array of evidence objects: {source, entry_id, entry_title, detail}. For exact/implicit matches.';
COMMENT ON COLUMN public.gap_analysis_results.reasoning IS 'Transferable skill reasoning. Required for implicit_match items.';
COMMENT ON COLUMN public.gap_analysis_results.suggestion IS 'Actionable advice for user. Populated for gap items only.';