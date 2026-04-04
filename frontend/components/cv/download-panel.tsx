// cv-agent/frontend/components/cv/download-panel.tsx

"use client";

import { useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// ── Types ─────────────────────────────────────────────────────────────────────
type ApplicationStatus =
  | "draft"
  | "applied"
  | "interview"
  | "offer"
  | "rejected"
  | "accepted";

interface ApplicationData {
  company_name: string;
  position: string;
  status: string;
}

interface DownloadPanelProps {
  applicationId: string;
  application: ApplicationData | null;
}

// ── Status config ─────────────────────────────────────────────────────────────
const STATUS_OPTIONS: { value: ApplicationStatus; label: string }[] = [
  { value: "draft",     label: "Draft" },
  { value: "applied",   label: "Applied" },
  { value: "interview", label: "Interview" },
  { value: "offer",     label: "Offer" },
  { value: "rejected",  label: "Rejected" },
  { value: "accepted",  label: "Accepted" },
];

const STATUS_BADGE_VARIANT: Record
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

// ── Main Component ────────────────────────────────────────────────────────────
export function DownloadPanel({ applicationId, application }: DownloadPanelProps) {
  // Download states — terpisah per format
  const [pdfLoading, setPdfLoading]   = useState(false);
  const [docxLoading, setDocxLoading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Status update states
  const [currentStatus, setCurrentStatus] = useState<ApplicationStatus>(
    (application?.status as ApplicationStatus) ?? "draft"
  );
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError]     = useState<string | null>(null);
  const [statusSuccess, setStatusSuccess] = useState(false);

  // ── Download handlers ───────────────────────────────────────────────────────
  async function handleDownload(format: "pdf" | "docx") {
    const setLoading = format === "pdf" ? setPdfLoading : setDocxLoading;
    setLoading(true);
    setDownloadError(null);

    try {
      const response = await apiFetch(
        `/applications/${applicationId}/download?format=${format}`
      );

      if (!response?.url) {
        throw new Error("No download URL returned from server.");
      }

      // Buka signed URL di tab baru — tidak navigate away dari halaman ini
      window.open(response.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setDownloadError(
        err instanceof Error
          ? err.message
          : "Failed to generate download link. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  // ── Status update handler ───────────────────────────────────────────────────
  async function handleStatusUpdate(newStatus: ApplicationStatus) {
    if (newStatus === currentStatus) return;

    setStatusLoading(true);
    setStatusError(null);
    setStatusSuccess(false);

    try {
      await apiFetch(`/applications/${applicationId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      setCurrentStatus(newStatus);
      setStatusSuccess(true);

      // Reset success message setelah 3 detik
      setTimeout(() => setStatusSuccess(false), 3000);
    } catch (err) {
      setStatusError(
        err instanceof Error
          ? err.message
          : "Failed to update status. Please try again."
      );
    } finally {
      setStatusLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl mx-auto">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">
          Your CV is Ready
        </h1>
        {application && (
          <p className="mt-1 text-sm text-gray-500">
            {application.position} at {application.company_name}
          </p>
        )}
      </div>

      {/* Download section */}
      <Card className="flex flex-col gap-5">
        <div>
          <h2 className="text-base font-semibold text-gray-900">
            Download your CV
          </h2>
          <p className="mt-0.5 text-sm text-gray-500">
            Choose your preferred format
          </p>
        </div>

        {/* Download buttons */}
        <div className="flex flex-col sm:flex-row gap-3">
          {/* PDF */}
          <button
            onClick={() => handleDownload("pdf")}
            disabled={pdfLoading || docxLoading}
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-md bg-blue-600 px-6 h-12 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
          >
            {pdfLoading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Generating link...
              </>
            ) : (
              <>
                <span>📄</span>
                Download PDF
              </>
            )}
          </button>

          {/* DOCX */}
          <button
            onClick={() => handleDownload("docx")}
            disabled={pdfLoading || docxLoading}
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-md border border-gray-300 bg-white px-6 h-12 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2"
          >
            {docxLoading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
                Generating link...
              </>
            ) : (
              <>
                <span>📝</span>
                Download DOCX
              </>
            )}
          </button>
        </div>

        {/* Download error */}
        {downloadError && (
          <p className="text-sm text-red-600">{downloadError}</p>
        )}

        {/* Expiry notice */}
        <p className="text-xs text-gray-400">
          Download links expire after 1 hour. Return to this page to generate
          a new link if needed.
        </p>
      </Card>

      {/* Application status section */}
      <Card className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            Application Status
          </h2>
          <Badge variant={STATUS_BADGE_VARIANT[currentStatus]}>
            {STATUS_OPTIONS.find((o) => o.value === currentStatus)?.label ??
              currentStatus}
          </Badge>
        </div>

        <p className="text-sm text-gray-500">
          Update the status of this application as it progresses.
        </p>

        {/* Status options */}
        <div className="flex flex-wrap gap-2">
          {STATUS_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => handleStatusUpdate(option.value)}
              disabled={statusLoading || option.value === currentStatus}
              className={
                option.value === currentStatus
                  ? "inline-flex items-center rounded-md border-2 border-blue-500 bg-blue-50 px-3 h-8 text-xs font-medium text-blue-700 cursor-default"
                  : "inline-flex items-center rounded-md border border-gray-200 bg-white px-3 h-8 text-xs font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors disabled:opacity-50 disabled:pointer-events-none"
              }
            >
              {option.label}
            </button>
          ))}
        </div>

        {/* Status feedback */}
        {statusLoading && (
          <p className="text-xs text-gray-500">Updating status...</p>
        )}
        {statusSuccess && (
          <p className="text-xs text-green-600">
            ✓ Status updated successfully
          </p>
        )}
        {statusError && (
          <p className="text-xs text-red-600">{statusError}</p>
        )}
      </Card>

      {/* Back to dashboard */}
      <div className="flex justify-start pb-8">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          ← Back to Dashboard
        </Link>
      </div>
    </div>
  );
}