// cv-agent/frontend/app/(app)/profile/page.tsx

import { redirect } from "next/navigation";
import Link from "next/link";
import { createServerClient } from "@/lib/supabase-server";
import { cn } from "@/lib/utils";
import { ComponentList } from "@/components/profile/component-list";
import { ErrorBoundary } from "@/components/ui/error-boundary";

// ── Tab config ────────────────────────────────────────────────────────────────
// Urutan tab sesuai urutan tampilan di sidebar
const TABS = [
  { key: "experience",    label: "Experience" },
  { key: "education",     label: "Education" },
  { key: "projects",      label: "Projects" },
  { key: "awards",        label: "Awards" },
  { key: "organizations", label: "Organizations" },
  { key: "certificates",  label: "Certificates" },
  { key: "skills",        label: "Skills" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const VALID_TABS = TABS.map((t) => t.key) as string[];

// ── Supabase table mapping ────────────────────────────────────────────────────
// Setiap komponen punya kolom yang berbeda di DB — kita select semuanya
// agar ComponentList bisa menampilkan field yang relevan
const TABLE_SELECT: Record<TabKey, string> = {
  experience:    "id, company, role, start_date, end_date, is_current, what_i_did, challenge, impact, skills_used, is_inferred",
  education:     "id, institution, degree, field_of_study, start_date, end_date, is_current, what_i_did, challenge, impact, skills_used, is_inferred",
  projects:      "id, title, url, start_date, end_date, what_i_did, challenge, impact, skills_used, is_inferred",
  awards:        "id, title, issuer, date, what_i_did, challenge, impact, skills_used, is_inferred",
  organizations: "id, name, role, start_date, end_date, is_current, what_i_did, challenge, impact, skills_used, is_inferred",
  certificates:  "id, name, issuer, issue_date, expiry_date, url, is_inferred",
  skills:        "id, name, category, is_inferred, source",
};

// ── Page ──────────────────────────────────────────────────────────────────────
export default async function ProfilePage({
  searchParams,
}: {
  searchParams: { tab?: string };
}) {
  const supabase = await createServerClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Validasi tab dari query param — fallback ke "experience" jika tidak valid
  const activeTab: TabKey =
    searchParams.tab && VALID_TABS.includes(searchParams.tab)
      ? (searchParams.tab as TabKey)
      : "experience";

  // Fetch entries untuk tab yang aktif
  const { data: entries, error } = await supabase
    .from(activeTab)
    .select(TABLE_SELECT[activeTab])
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  if (error) {
    throw new Error(`Failed to load ${activeTab} data. Please try again.`);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Profile</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage your professional information
        </p>
      </div>

      {/* Two-column layout */}
      <div className="flex gap-8 items-start">
        {/* Left Sidebar — Tab Navigation */}
        <nav className="w-48 shrink-0 flex flex-col gap-1">
          {TABS.map((tab) => (
            <Link
              key={tab.key}
              href={`/profile?tab=${tab.key}`}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "bg-blue-50 text-blue-600"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              )}
            >
              {tab.label}
            </Link>
          ))}
        </nav>

        {/* Right Content Area */}
        <div className="flex-1 min-w-0">
          <ErrorBoundary>
            <ComponentList
              component={activeTab}
              entries={entries ?? []}
            />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}