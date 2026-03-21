-- Migration: Create revision_history table
-- Cluster 4 — Orchestrator
-- Audit log of every revision instruction sent from Cluster 4 to Cluster 5.
-- revision_type distinguishes QC-driven (automatic) vs user-driven (manual).
-- sections JSONB stores full instruction payload — structure varies by type.

CREATE TABLE IF NOT EXISTS public.revision_history (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    revision_type  VARCHAR(20) NOT NULL
                   CHECK (revision_type IN ('qc_driven', 'user_driven')),
    iteration      INTEGER NOT NULL DEFAULT 1,
    sections       JSONB NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'completed', 'max_reached')),
    created_at     TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.revision_history IS 'Audit log of revision instructions from Cluster 4 to Cluster 5.';
COMMENT ON COLUMN public.revision_history.revision_type IS 'qc_driven = automatic from QC. user_driven = manual from user request.';
COMMENT ON COLUMN public.revision_history.iteration IS 'QC iteration number at time of revision. Always 1 for user_driven.';
COMMENT ON COLUMN public.revision_history.sections IS 'Full revision payload. Structure differs between qc_driven and user_driven.';
COMMENT ON COLUMN public.revision_history.status IS 'pending → completed → max_reached lifecycle.';