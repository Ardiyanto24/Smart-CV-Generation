-- Migration: Create qc_results table
-- Cluster 6 — Quality Control
-- One row per section per QC iteration.
-- Combines ATS Scoring Agent + Semantic Reviewer Agent output.
-- action_required is single source of truth for Cluster 4 Revision Handler.

CREATE TABLE IF NOT EXISTS public.qc_results (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id   UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    cv_version       INTEGER NOT NULL,
    iteration        INTEGER NOT NULL DEFAULT 1,
    section          VARCHAR(50) NOT NULL,
    entry_id         UUID,
    ats_score        NUMERIC(5,2),
    ats_status       VARCHAR(10) CHECK (ats_status IN ('passed', 'failed')),
    semantic_score   NUMERIC(5,2),
    semantic_status  VARCHAR(10) CHECK (semantic_status IN ('passed', 'failed')),
    action_required  BOOLEAN NOT NULL DEFAULT FALSE,
    preserve         JSONB,
    revise           JSONB,
    missed_keywords  TEXT[],
    combined_score   NUMERIC(5,2),
    created_at       TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.qc_results IS 'QC output per section per iteration. Combines ATS + Semantic scores.';
COMMENT ON COLUMN public.qc_results.cv_version IS 'References version field of cv_outputs row being evaluated.';
COMMENT ON COLUMN public.qc_results.entry_id IS 'NULL for sections like summary. Non-null for experience/projects entries.';
COMMENT ON COLUMN public.qc_results.action_required IS 'Single source of truth for Cluster 4. True = section needs revision.';
COMMENT ON COLUMN public.qc_results.preserve IS 'Array of strings: what must be kept in any revision.';
COMMENT ON COLUMN public.qc_results.revise IS 'Array of strings: what must be changed in revision.';
COMMENT ON COLUMN public.qc_results.combined_score IS '(ats_score × weight_ats) + (semantic_score × weight_semantic). Used for best-version selection.';