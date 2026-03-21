-- Migration: Enable RLS on applications table (Cluster 2)
-- Direct user_id check — same pattern as Master Data tables.

ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "applications_own_data_policy"
ON public.applications
FOR ALL
USING (user_id = auth.uid());