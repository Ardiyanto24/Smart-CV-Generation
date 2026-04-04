// cv-agent/frontend/app/(app)/apply/[id]/brief/page.tsx

import { redirect } from "next/navigation";
import { createServerClient } from "@/lib/supabase-server";
import { WorkflowProgress } from "@/components/ui/workflow-progress";
import { WorkflowPoller } from "@/components/ui/workflow-poller";
import { BriefReview } from "@/components/brief/brief-review";
import { ErrorBoundary } from "@/components/ui/error-boundary";

interface BriefPageProps {
  params: { id: string };
}

export default async function BriefPage({ params }: BriefPageProps) {
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
    // Fallback ke WorkflowProgress jika status fetch gagal
  }

  const isInterrupted =
    workflowStatus?.status === "interrupted" &&
    workflowStatus?.interrupt_type === "user_brief_review";

  // Fetch brief data hanya jika sudah di interrupt point
  let briefData: Record<string, unknown> | null = null;
  if (isInterrupted) {
    try {
      const briefRes = await fetch(`${apiBase}/applications/${id}/brief`, {
        headers,
        cache: "no-store",
      });
      if (briefRes.ok) {
        briefData = await briefRes.json();
      }
    } catch {
      // ErrorBoundary akan menangkap jika render gagal
    }
  }

  return (
    <ErrorBoundary>
      {isInterrupted && briefData ? (
        <BriefReview applicationId={id} data={briefData} />
      ) : (
        <WorkflowPoller applicationId={id}>
          <WorkflowProgress applicationId={id} />
        </WorkflowPoller>
      )}
    </ErrorBoundary>
  );
}