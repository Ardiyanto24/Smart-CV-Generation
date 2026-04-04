// cv-agent/frontend/app/(app)/dashboard/page.tsx

import { redirect } from "next/navigation";
import Link from "next/link";
import { createServerClient } from "@/lib/supabase-server";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBoundary } from "@/components/ui/error-boundary";

// ── Status badge mapping ───────────────────────────────────────────────────────
// Memetakan status dari DB ke variant Badge dan label yang ditampilkan ke user
type ApplicationStatus =
  | "draft"
  | "applied"
  | "interview"
  | "offer"
  | "rejected"
  | "accepted";

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

// Menentukan destination URL saat card diklik.
// Jika status masih "draft", berarti workflow belum dimulai → ke /apply/{id}
// Jika sudah melewati start → ke /apply/{id}/gap (titik pertama setelah workflow start)
function getApplicationHref(id: string, status: ApplicationStatus): string {
  if (status === "draft") return `/apply/${id}`;
  return `/apply/${id}/gap`;
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default async function DashboardPage() {
  const supabase = await createServerClient();

  // Double-guard: pastikan session ada
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Fetch semua aplikasi milik user, diurutkan terbaru di atas
  const { data: applications, error } = await supabase
    .from("applications")
    .select("id, company_name, position, status, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  // Jika fetch gagal, lempar error agar ditangkap ErrorBoundary
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
        <Button asChild>
          <Link href="/apply/new">New Application</Link>
        </Button>
      </div>

      {/* Application List */}
      <ErrorBoundary>
        {!applications || applications.length === 0 ? (
          <EmptyState
            title="No applications yet"
            description="Start by creating your first application and let CV Agent tailor your CV."
            action={
              <Button asChild>
                <Link href="/apply/new">Start your first application</Link>
              </Button>
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
                  className="block transition-shadow hover:shadow-md rounded-lg"
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