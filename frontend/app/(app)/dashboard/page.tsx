// cv-agent/frontend/app/(app)/dashboard/page.tsx

import { redirect } from "next/navigation";
import Link from "next/link";
import { createServerClient } from "@/lib/supabase-server";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBoundary } from "@/components/ui/error-boundary";

// ── Types ─────────────────────────────────────────────────────────────────────
type ApplicationStatus =
  | "draft"
  | "applied"
  | "interview"
  | "offer"
  | "rejected"
  | "accepted";

// ── Status mappings ───────────────────────────────────────────────────────────
const statusBadgeVariant: Record
  ApplicationStatus,
  "neutral" | "info" | "warning" | "success" | "error"
> = {
  draft:     "neutral",
  applied:   "info",
  interview: "warning",
  offer:     "success",
  rejected:  "error",
  accepted:  "success",
};

const statusLabel: Record<ApplicationStatus, string> = {
  draft:     "Draft",
  applied:   "Applied",
  interview: "Interview",
  offer:     "Offer",
  rejected:  "Rejected",
  accepted:  "Accepted",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("id-ID", {
    day:   "numeric",
    month: "short",
    year:  "numeric",
  });
}

function getApplicationHref(id: string, status: ApplicationStatus): string {
  if (status === "draft") return `/apply/${id}`;
  return `/apply/${id}/gap`;
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default async function DashboardPage() {
  const supabase = await createServerClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const { data: applications, error } = await supabase
    .from("applications")
    .select("id, company_name, position, status, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  if (error) {
    throw new Error("Failed to load applications. Please try again.");
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            My Applications
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage and track your job applications
          </p>
        </div>
        <Link
          href="/apply/new"
          className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 h-10 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
        >
          New Application
        </Link>
      </div>

      {/* Application List */}
      <ErrorBoundary>
        {!applications || applications.length === 0 ? (
          <EmptyState
            title="No applications yet"
            description="Start by creating your first application and let CV Agent tailor your CV."
            action={
              <Link
                href="/apply/new"
                className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 h-10 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
              >
                Start your first application
              </Link>
            }
          />
        ) : (
          <div className="flex flex-col gap-3">
            {applications.map((app) => {
              const status = app.status as ApplicationStatus;
              return (
                <Link
                  key={app.id}
                  href={getApplicationHref(app.id, status)}
                  className="block rounded-lg transition-shadow hover:shadow-md"
                >
                  <Card className="flex items-center justify-between gap-4">
                    {/* Company + Position */}
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <p className="text-sm font-semibold text-gray-900 truncate">
                        {app.company_name}
                      </p>
                      <p className="text-sm text-gray-500 truncate">
                        {app.position}
                      </p>
                    </div>

                    {/* Status + Date */}
                    <div className="flex items-center gap-4 shrink-0">
                      <Badge variant={statusBadgeVariant[status]}>
                        {statusLabel[status]}
                      </Badge>
                      <span className="text-xs text-gray-400">
                        {formatDate(app.created_at)}
                      </span>
                    </div>
                  </Card>
                </Link>
              );
            })}
          </div>
        )}
      </ErrorBoundary>
    </div>
  );
}