-- Migration: Enable RLS on application child tables (Cluster 2–6)
-- Subquery pattern: verify ownership via applications table.
-- These tables have no direct user_id — ownership checked through application_id.

-- ── job_postings ─────────────────────────────────────────────────────────────
ALTER TABLE public.job_postings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "job_postings_own_data_policy"
ON public.job_postings FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── job_descriptions ─────────────────────────────────────────────────────────
ALTER TABLE public.job_descriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "job_descriptions_own_data_policy"
ON public.job_descriptions FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── job_requirements ─────────────────────────────────────────────────────────
ALTER TABLE public.job_requirements ENABLE ROW LEVEL SECURITY;
CREATE POLICY "job_requirements_own_data_policy"
ON public.job_requirements FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── gap_analysis_results ─────────────────────────────────────────────────────
ALTER TABLE public.gap_analysis_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY "gap_analysis_results_own_data_policy"
ON public.gap_analysis_results FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── gap_analysis_scores ──────────────────────────────────────────────────────
ALTER TABLE public.gap_analysis_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "gap_analysis_scores_own_data_policy"
ON public.gap_analysis_scores FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── cv_strategy_briefs ───────────────────────────────────────────────────────
ALTER TABLE public.cv_strategy_briefs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "cv_strategy_briefs_own_data_policy"
ON public.cv_strategy_briefs FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── selected_content_packages ────────────────────────────────────────────────
ALTER TABLE public.selected_content_packages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "selected_content_packages_own_data_policy"
ON public.selected_content_packages FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── revision_history ─────────────────────────────────────────────────────────
ALTER TABLE public.revision_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "revision_history_own_data_policy"
ON public.revision_history FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── cv_outputs ───────────────────────────────────────────────────────────────
ALTER TABLE public.cv_outputs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "cv_outputs_own_data_policy"
ON public.cv_outputs FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── qc_results ───────────────────────────────────────────────────────────────
ALTER TABLE public.qc_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY "qc_results_own_data_policy"
ON public.qc_results FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));

-- ── qc_overall_scores ────────────────────────────────────────────────────────
ALTER TABLE public.qc_overall_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "qc_overall_scores_own_data_policy"
ON public.qc_overall_scores FOR ALL
USING (application_id IN (
    SELECT id FROM public.applications WHERE user_id = auth.uid()
));