// cv-agent/frontend/app/(app)/apply/[id]/download/page.tsx

import { redirect } from "next/navigation";
import { createServerClient } from "@/lib/supabase-server";
import { WorkflowProgress } from "@/components/ui/workflow-progress";
import { WorkflowPoller } from "@/components/ui/workflow-poller";
import { DownloadPanel } from "@/components/cv/download-panel";
import { ErrorBoundary } from "@/components/ui/error-boundary";

interface DownloadPageProps {
  params: { id: string };
}

export default async function DownloadPage({ params }: DownloadPageProps) {
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
  let workflowStatus: { status: string; current_node?: string } | null = null;
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

  // Workflow masih berjalan jika status "running" atau node aktif adalah render_document
  const isStillRunning =
    workflowStatus?.status === "running" ||
    workflowStatus?.current_node === "render_document";

  // Fetch application data untuk ditampilkan di download page
  let applicationData: {
    company_name: string;
    position: string;
    status: string;
  } | null = null;

  if (!isStillRunning) {
    const { data } = await supabase
      .from("applications")
      .select("company_name, position, status")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    applicationData = data;
  }

  return (
    <ErrorBoundary>
      {isStillRunning ? (
        <WorkflowPoller applicationId={id}>
          <WorkflowProgress applicationId={id} />
        </WorkflowPoller>
      ) : (
        <DownloadPanel
          applicationId={id}
          application={applicationData}
        />
      )}
    </ErrorBoundary>
  );
}