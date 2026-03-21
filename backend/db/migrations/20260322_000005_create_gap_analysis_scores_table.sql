-- Migration: Create gap_analysis_scores table
-- Cluster 3 — Gap Analyzer
-- One row per application — overall Scoring Agent assessment.
-- Logical one-to-one with applications, not enforced at DB level
-- to allow re-scoring without DELETE + INSERT complexity.

CREATE TABLE IF NOT EXISTS public.gap_analysis_scores (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id         UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    quantitative_score     NUMERIC(5,2) NOT NULL,
    verdict                VARCHAR(20) NOT NULL
                           CHECK (verdict IN ('sangat_cocok', 'cukup_cocok', 'kurang_cocok')),
    strength               TEXT,
    concern                TEXT,
    recommendation         TEXT,
    proceed_recommendation VARCHAR(10)
                           CHECK (proceed_recommendation IN ('lanjut', 'tinjau')),
    created_at             TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.gap_analysis_scores IS 'Scoring Agent output. Logical one-to-one with applications.';
COMMENT ON COLUMN public.gap_analysis_scores.quantitative_score IS 'Calculated 0-100 score. Formula: (exact×1.0 + implicit×0.7) / total × 100.';
COMMENT ON COLUMN public.gap_analysis_scores.verdict IS 'sangat_cocok: 75-100, cukup_cocok: 50-74, kurang_cocok: 0-49.';
COMMENT ON COLUMN public.gap_analysis_scores.strength IS 'LLM-generated qualitative strength summary.';
COMMENT ON COLUMN public.gap_analysis_scores.concern IS 'LLM-generated qualitative concern summary.';
COMMENT ON COLUMN public.gap_analysis_scores.proceed_recommendation IS 'lanjut or tinjau — guides user decision after seeing the report.';