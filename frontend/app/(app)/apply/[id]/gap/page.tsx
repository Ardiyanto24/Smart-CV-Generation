// cv-agent/frontend/app/(app)/apply/[id]/gap/page.tsx

import { redirect } from "next/navigation";
import { createServerClient } from "@/lib/supabase-server";
import { WorkflowProgress } from "@/components/ui/workflow-progress";
import { GapReport } from "@/components/gap/gap-report";
import { WorkflowPoller } from "@/components/ui/workflow-poller";
import { ErrorBoundary } from "@/components/ui/error-boundary";

interface GapPageProps {
  params: { id: string };
}

export default async function GapPage({ params }: GapPageProps) {
  const { id } = params;
  const supabase = await createServerClient();

  // Double-guard session
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Fetch status workflow dari backend
  // Tidak pakai Supabase langsung — status workflow ada di LangGraph state,
  // bukan di DB. Kita fetch via backend API menggunakan service role key.
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  // Ambil session cookie untuk forward ke backend
  const { data: sessionData } = await supabase.auth.getSession();
  const accessToken = sessionData?.session?.access_token;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  let workflowStatus: { status: string; interrupt_type?: string } | null = null;
  let gapData: Record<string, unknown> | null = null;

  try {
    const statusRes = await fetch(`${apiBase}/applications/${id}/status`, {
      headers,
      cache: "no-store",
    });
    if (statusRes.ok) {
      workflowStatus = await statusRes.json();
    }
  } catch {
    // Jika status fetch gagal, fallback ke tampilkan WorkflowProgress
  }

  const isInterrupted =
    workflowStatus?.status === "interrupted" &&
    workflowStatus?.interrupt_type === "user_gap_review";

  // Fetch gap data hanya jika workflow sudah di interrupt point
  if (isInterrupted) {
    try {
      const gapRes = await fetch(`${apiBase}/applications/${id}/gap`, {
        headers,
        cache: "no-store",
      });
      if (gapRes.ok) {
        gapData = await gapRes.json();
      }
    } catch {
      // Jika fetch gagal, ErrorBoundary akan menangkap
    }
  }

  return (
    <ErrorBoundary>
      {isInterrupted && gapData ? (
        // Workflow sudah interrupt — tampilkan gap report
        <GapReport applicationId={id} data={gapData} />
      ) : (
        // Workflow masih berjalan — tampilkan progress
        // WorkflowPoller akan auto-refresh halaman saat interrupt tercapai
        <WorkflowPoller applicationId={id}>
          <WorkflowProgress applicationId={id} />
        </WorkflowPoller>
      )}
    </ErrorBoundary>
  );
}