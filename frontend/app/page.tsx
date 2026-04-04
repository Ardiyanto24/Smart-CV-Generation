// cv-agent/frontend/app/(app)/apply/[id]/page.tsx

import { redirect } from "next/navigation";
import { createServerClient } from "@/lib/supabase-server";
import { Card } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import Link from "next/link";

interface ApplicationPageProps {
  params: { id: string };
}

export default async function ApplicationPage({ params }: ApplicationPageProps) {
  const { id } = params;
  const supabase = await createServerClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Fetch application data — verifikasi ownership sekaligus
  const { data: application, error } = await supabase
    .from("applications")
    .select("id, company_name, position, status")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();

  // Tidak ditemukan atau bukan milik user ini
  if (error || !application) {
    redirect("/dashboard");
  }

  // Jika workflow sudah berjalan, redirect ke halaman yang tepat
  if (application.status !== "draft") {
    redirect(`/apply/${id}/gap`);
  }

  return (
    <ErrorBoundary>
      <div className="flex flex-col gap-8 max-w-xl mx-auto">
        {/* Page header */}
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Draft Application
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            This application has not been started yet
          </p>
        </div>

        {/* Application info */}
        <Card className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-xs text-gray-400 uppercase tracking-wide">
              Company
            </p>
            <p className="text-base font-semibold text-gray-900">
              {application.company_name}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-xs text-gray-400 uppercase tracking-wide">
              Position
            </p>
            <p className="text-base font-semibold text-gray-900">
              {application.position}
            </p>
          </div>

          <div className="border-t border-gray-100 pt-4">
            <p className="text-sm text-gray-500 mb-4">
              You have not started the CV generation workflow for this
              application yet. Click below to continue to the job description
              input and start the analysis.
            </p>

            {/* Start Workflow button — navigasi ke /apply/new dengan pre-filled data */}
            <Link
              href={`/apply/new?company=${encodeURIComponent(application.company_name)}&position=${encodeURIComponent(application.position)}&application_id=${id}`}
              className="inline-flex items-center justify-center rounded-md bg-blue-600 px-6 h-10 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
            >
              Start Workflow
            </Link>
          </div>
        </Card>

        {/* Back link */}
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          ← Back to Dashboard
        </Link>
      </div>
    </ErrorBoundary>
  );
}