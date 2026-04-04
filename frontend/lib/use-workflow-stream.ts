// cv-agent/frontend/lib/use-workflow-stream.ts

"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Status workflow yang menandakan workflow sudah selesai —
// saat polling mendeteksi salah satu status ini, polling berhenti
const TERMINAL_STATUSES = ["completed", "interrupted", "error"];

// Interval polling saat SSE connection drop (dalam ms)
const POLL_INTERVAL_MS = 5000;

interface UseWorkflowStreamReturn {
  currentNode: string | null;
  isStreaming: boolean;
  error: string | null;
}

export function useWorkflowStream(applicationId: string): UseWorkflowStreamReturn {
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Refs untuk cleanup — disimpan di ref agar tidak trigger re-render
  const eventSourceRef = useRef<EventSource | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isUnmountedRef = useRef(false);

  // ── Polling fallback ────────────────────────────────────────────────────────
  // Dipanggil saat SSE connection drop untuk menjaga UI tetap update
  function startPolling() {
    if (pollIntervalRef.current) return; // Jangan buka dua polling sekaligus

    pollIntervalRef.current = setInterval(async () => {
      if (isUnmountedRef.current) return;

      try {
        const response = await apiFetch(`/applications/${applicationId}/status`);

        // Update node dari polling response
        if (response?.current_node) {
          setCurrentNode(response.current_node);
        }

        // Jika workflow sudah selesai/interrupted, hentikan polling
        // dan coba reconnect SSE
        if (TERMINAL_STATUSES.includes(response?.status)) {
          stopPolling();
          return;
        }

        // Coba reconnect SSE jika belum streaming
        if (!eventSourceRef.current) {
          stopPolling();
          connectSSE();
        }
      } catch {
        // Polling gagal — tetap coba lagi di interval berikutnya
      }
    }, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }

  // ── SSE Connection ──────────────────────────────────────────────────────────
  function connectSSE() {
    if (isUnmountedRef.current) return;

    // EventSource tidak support custom headers, sehingga auth via cookie
    // (httpOnly) akan otomatis dikirim oleh browser — tidak perlu setup manual
    const url = `${API_BASE_URL}/applications/${applicationId}/stream`;
    const es = new EventSource(url, { withCredentials: true });
    eventSourceRef.current = es;

    es.onopen = () => {
      if (isUnmountedRef.current) return;
      setIsStreaming(true);
      setError(null);
      stopPolling(); // SSE aktif — polling tidak diperlukan
    };

    es.onmessage = (event) => {
      if (isUnmountedRef.current) return;

      try {
        const data = JSON.parse(event.data);

        // Extract node dari payload SSE
        if (data?.node) {
          setCurrentNode(data.node);
        }

        // Jika backend mengirim event "done", tutup koneksi
        if (data?.status === "done" || data?.type === "interrupt") {
          es.close();
          eventSourceRef.current = null;
          setIsStreaming(false);
        }
      } catch {
        // Data SSE tidak valid JSON — abaikan dan tunggu event berikutnya
      }
    };

    es.onerror = () => {
      if (isUnmountedRef.current) return;

      // SSE error — bisa karena network drop atau server restart
      es.close();
      eventSourceRef.current = null;
      setIsStreaming(false);
      setError("Connection lost. Trying to reconnect...");

      // Fallback ke polling sampai SSE bisa reconnect
      startPolling();
    };
  }

  // ── Effect ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    isUnmountedRef.current = false;

    connectSSE();

    // Cleanup saat komponen unmount
    return () => {
      isUnmountedRef.current = true;

      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId]);

  return { currentNode, isStreaming, error };
}