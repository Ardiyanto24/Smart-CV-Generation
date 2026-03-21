-- Migration: Create cv_outputs table
-- Cluster 5 — CV Generator
-- Stores every CV version as immutable JSONB document.
-- Every revision creates a new row — old versions never deleted.
-- Enables rollback and best-version selection by Cluster 6.
-- No updated_at — rows are immutable by design.

CREATE TABLE IF NOT EXISTS public.cv_outputs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    version        INTEGER NOT NULL DEFAULT 1,
    content        JSONB NOT NULL,
    revision_type  VARCHAR(20)
                   CHECK (revision_type IN ('initial', 'qc_driven', 'user_driven')),
    section_revised VARCHAR(50),
    status         VARCHAR(20) NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft', 'qc_passed', 'user_approved', 'final')),
    created_at     TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.cv_outputs IS 'Immutable CV versions. Every revision = new row. Enables rollback and best-version selection.';
COMMENT ON COLUMN public.cv_outputs.version IS 'Increments with each revision. Start at 1 for initial generation.';
COMMENT ON COLUMN public.cv_outputs.content IS 'Full Final Structured Output JSON per cluster5_specification.md Section 8.';
COMMENT ON COLUMN public.cv_outputs.revision_type IS 'NULL not allowed — initial for first gen, qc_driven/user_driven for revisions.';
COMMENT ON COLUMN public.cv_outputs.section_revised IS 'NULL means entire CV generated (initial). Non-null means specific section revised.';
COMMENT ON COLUMN public.cv_outputs.status IS 'draft → qc_passed → user_approved → final lifecycle.';