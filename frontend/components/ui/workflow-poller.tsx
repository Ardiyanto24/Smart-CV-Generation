// cv-agent/frontend/components/ui/workflow-poller.tsx

"use client";

import { useEffect, useRef, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

const POLL_INTERVAL_MS = 3000;
const INTERRUPT_STATUSES = ["interrupted", "completed", "error"];

interface WorkflowPollerProps {
  applicationId: string;
  children: ReactNode;
}

export function WorkflowPoller({ applicationId, children }: WorkflowPollerProps) {
  const router = useRouter();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isUnmountedRef = useRef(false);

  useEffect(() => {
    isUnmountedRef.current = false;

    intervalRef.current = setInterval(async () => {
      if (isUnmountedRef.current) return;

      try {
        const response = await apiFetch(`/applications/${applicationId}/status`);

        // Saat workflow mencapai interrupt atau selesai,
        // refresh Server Component agar page re-fetch status dan gap data
        if (INTERRUPT_STATUSES.includes(response?.status)) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          router.refresh();
        }
      } catch {
        // Polling gagal — coba lagi di interval berikutnya
      }
    }, POLL_INTERVAL_MS);

    return () => {
      isUnmountedRef.current = true;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [applicationId, router]);

  // WorkflowPoller hanya polling di background — render children apa adanya
  return <>{children}</>;
}