-- Migration: Create cv_strategy_briefs table
-- Cluster 4 — Orchestrator
-- Stores the CV strategy "contract" from Planner Agent.
-- Three zones of editability:
--   content_instructions  → Zona Merah (read-only for user)
--   narrative_instructions + keyword_targets → Zona Kuning (limited edit)
--   primary_angle + summary_hook_direction + tone → Zona Hijau (free edit)

CREATE TABLE IF NOT EXISTS public.cv_strategy_briefs (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id         UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    content_instructions   JSONB NOT NULL,
    narrative_instructions JSONB,
    keyword_targets        TEXT[],
    primary_angle          TEXT,
    summary_hook_direction TEXT,
    tone                   VARCHAR(30) NOT NULL DEFAULT 'technical_concise'
                           CHECK (tone IN ('technical_concise',
                                           'professional_formal',
                                           'professional_conversational')),
    user_approved          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at             TIMESTAMP DEFAULT NOW(),
    updated_at             TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.cv_strategy_briefs IS 'CV strategy contract from Planner Agent. Governs all downstream content generation.';
COMMENT ON COLUMN public.cv_strategy_briefs.content_instructions IS 'Zona Merah — which entries to include per component. Read-only for user.';
COMMENT ON COLUMN public.cv_strategy_briefs.narrative_instructions IS 'Zona Kuning — implicit match and gap bridge instructions with user decisions.';
COMMENT ON COLUMN public.cv_strategy_briefs.keyword_targets IS 'Zona Kuning — target keywords for injection into CV content.';
COMMENT ON COLUMN public.cv_strategy_briefs.primary_angle IS 'Zona Hijau — CV positioning statement. Freely editable by user.';
COMMENT ON COLUMN public.cv_strategy_briefs.user_approved IS 'Becomes true only after user explicitly approves brief in UI.';