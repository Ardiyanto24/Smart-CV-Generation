-- Migration: Enable RLS on Master Data tables (Cluster 1)

-- ── users ────────────────────────────────────────────────────────────────────
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_row_policy" ON public.users FOR ALL USING (id = auth.uid());

-- ── education ────────────────────────────────────────────────────────────────
ALTER TABLE public.education ENABLE ROW LEVEL SECURITY;
CREATE POLICY "education_own_data_policy" ON public.education FOR ALL USING (user_id = auth.uid());

-- ── experience ───────────────────────────────────────────────────────────────
ALTER TABLE public.experience ENABLE ROW LEVEL SECURITY;
CREATE POLICY "experience_own_data_policy" ON public.experience FOR ALL USING (user_id = auth.uid());

-- ── projects ─────────────────────────────────────────────────────────────────
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY "projects_own_data_policy" ON public.projects FOR ALL USING (user_id = auth.uid());

-- ── awards ───────────────────────────────────────────────────────────────────
ALTER TABLE public.awards ENABLE ROW LEVEL SECURITY;
CREATE POLICY "awards_own_data_policy" ON public.awards FOR ALL USING (user_id = auth.uid());

-- ── organizations ────────────────────────────────────────────────────────────
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "organizations_own_data_policy" ON public.organizations FOR ALL USING (user_id = auth.uid());

-- ── certificates ─────────────────────────────────────────────────────────────
ALTER TABLE public.certificates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "certificates_own_data_policy" ON public.certificates FOR ALL USING (user_id = auth.uid());

-- ── skills ───────────────────────────────────────────────────────────────────
ALTER TABLE public.skills ENABLE ROW LEVEL SECURITY;
CREATE POLICY "skills_own_data_policy" ON public.skills FOR ALL USING (user_id = auth.uid());