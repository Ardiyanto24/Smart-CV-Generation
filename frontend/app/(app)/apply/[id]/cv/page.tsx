// cv-agent/frontend/app/(app)/apply/[id]/cv/page.tsx

import { redirect } from "next/navigation";
import { createServerClient } from "@/lib/supabase-server";
import { WorkflowProgress } from "@/components/ui/workflow-progress";
import { WorkflowPoller } from "@/components/ui/workflow-poller";
import { CVReview } from "@/components/cv/cv-review";
import { ErrorBoundary } from "@/components/ui/error-boundary";

interface CVPageProps {
  params: { id: string };
}

export default async function CVPage({ params }: CVPageProps) {
  const { id } = params;
  const supabase = await createServerClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const { data: sessionData } = await supabase.auth.getSession();
  const accessToken = sessionData?.session?.access_token;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  // Cek status workflow
  let workflowStatus: { status: string; interrupt_type?: string } | null = null;
  try {
    const statusRes = await fetch(`${apiBase}/applications/${id}/status`, {
      headers,
      cache: "no-store",
    });
    if (statusRes.ok) {
      workflowStatus = await statusRes.json();
    }
  } catch {
    // Fallback ke WorkflowProgress
  }

  const isInterrupted =
    workflowStatus?.status === "interrupted" &&
    workflowStatus?.interrupt_type === "user_cv_review";

  // Fetch CV dan QC data secara paralel hanya jika sudah di interrupt point
  let cvData: Record<string, unknown> | null = null;
  let qcData: Record<string, unknown> | null = null;

  if (isInterrupted) {
    try {
      const [cvRes, qcRes] = await Promise.all([
        fetch(`${apiBase}/applications/${id}/cv`, {
          headers,
          cache: "no-store",
        }),
        fetch(`${apiBase}/applications/${id}/qc`, {
          headers,
          cache: "no-store",
        }),
      ]);

      if (cvRes.ok) cvData = await cvRes.json();
      if (qcRes.ok) qcData = await qcRes.json();
    } catch {
      // ErrorBoundary akan menangkap jika render gagal
    }
  }

  return (
    <ErrorBoundary>
      {isInterrupted && cvData && qcData ? (
        <CVReview
          applicationId={id}
          cvOutput={cvData}
          qcReport={qcData}
        />
      ) : (
        <WorkflowPoller applicationId={id}>
          <WorkflowProgress applicationId={id} />
        </WorkflowPoller>
      )}
    </ErrorBoundary>
  );
}