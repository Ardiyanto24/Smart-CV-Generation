// cv-agent/frontend/components/cv/cv-review.tsx

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CVSectionCard } from "./cv-section-card";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────
type ApprovalStatus = "approved" | "revision_requested";

interface QCSection {
  section: string;
  entry_id?: string;
  ats_score: number;
  ats_status: "passed" | "failed";
  semantic_score: number;
  semantic_status: "passed" | "failed";
  action_required: boolean;
  preserve: string[];
  revise: string[];
  missed_keywords: string[];
  iteration?: number;
}

interface QCReport {
  overall_ats_score: number;
  sections: QCSection[];
}

interface CVOutput {
  header?: Record<string, unknown>;
  summary?: string;
  experience?: unknown[];
  education?: unknown[];
  projects?: unknown[];
  awards?: unknown[];
  organizations?: unknown[];
  skills?: unknown[];
  certificates?: unknown[];
}

interface CVReviewProps {
  applicationId: string;
  cvOutput: Record<string, unknown>;
  qcReport: Record<string, unknown>;
}

// ── Section order ─────────────────────────────────────────────────────────────
// Urutan tetap sesuai spec — summary selalu pertama, skills dan certificates terakhir
const SECTION_ORDER = [
  "summary",
  "experience",
  "education",
  "projects",
  "awards",
  "organizations",
  "skills",
  "certificates",
] as const;

type SectionKey = (typeof SECTION_ORDER)[number];

// ── Main Component ────────────────────────────────────────────────────────────
export function CVReview({ applicationId, cvOutput, qcReport }: CVReviewProps) {
  const router = useRouter();
  const cv = cvOutput as unknown as CVOutput;
  const qc = qcReport as unknown as QCReport;

  // Map approvals dan instructions per section key
  const [approvals, setApprovals] = useState
    Record<string, ApprovalStatus | null>
  >(() =>
    Object.fromEntries(SECTION_ORDER.map((key) => [key, null]))
  );
  const [instructions, setInstructions] = useState<Record<string, string>>(
    () => Object.fromEntries(SECTION_ORDER.map((key) => [key, ""]))
  );

  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // ── Derived stats ───────────────────────────────────────────────────────────
  const sections = qc.sections ?? [];
  const totalSections = sections.length;
  const passedSections = sections.filter((s) => !s.action_required).length;
  const failedSections = totalSections - passedSections;
  const overallATS = Math.round(qc.overall_ats_score ?? 0);

  // Submit disabled sampai semua section punya approval status
  const allApproved = SECTION_ORDER
    .filter((key) => cv[key] !== undefined && cv[key] !== null)
    .every((key) => approvals[key] !== null);

  function handleApprovalChange(
    sectionKey: string,
    status: ApprovalStatus,
    instruction: string
  ) {
    setApprovals((prev) => ({ ...prev, [sectionKey]: status }));
    setInstructions((prev) => ({ ...prev, [sectionKey]: instruction }));
  }

  async function handleSubmit() {
    setSubmitLoading(true);
    setSubmitError(null);

    // Filter hanya section yang punya data dan approval status
    const filteredApprovals = Object.fromEntries(
      Object.entries(approvals).filter(([_, v]) => v !== null)
    ) as Record<string, ApprovalStatus>;

    const filteredInstructions = Object.fromEntries(
      Object.entries(instructions).filter(([k]) => filteredApprovals[k] === "revision_requested")
    );

    try {
      await apiFetch(`/applications/${applicationId}/resume`, {
        method: "POST",
        body: JSON.stringify({
          action:       "submit_review",
          approvals:    filteredApprovals,
          instructions: filteredInstructions,
        }),
      });
      router.push(`/apply/${applicationId}/download`);
    } catch (err) {
      setSubmitError(
        err instanceof Error
          ? err.message
          : "Failed to submit review. Please try again."
      );
      setSubmitLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">CV Review</h1>
        <p className="mt-1 text-sm text-gray-500">
          Review each section and approve or request revisions
        </p>
      </div>

      {/* Global QC summary */}
      <Card className="flex items-center gap-6 flex-wrap">
        <div className="flex flex-col gap-0.5">
          <p className="text-xs text-gray-500">Overall ATS Score</p>
          <p className="text-2xl font-bold text-gray-900">{overallATS}/100</p>
        </div>
        <div className="h-10 w-px bg-gray-200" />
        <div className="flex items-center gap-4">
          <div className="flex flex-col gap-0.5">
            <p className="text-xs text-gray-500">Sections</p>
            <p className="text-lg font-semibold text-gray-900">{totalSections}</p>
          </div>
          <div className="flex flex-col gap-0.5">
            <p className="text-xs text-green-600">QC Passed</p>
            <p className="text-lg font-semibold text-green-700">{passedSections}</p>
          </div>
          <div className="flex flex-col gap-0.5">
            <p className="text-xs text-red-500">QC Failed</p>
            <p className="text-lg font-semibold text-red-600">{failedSections}</p>
          </div>
        </div>
        <div className="ml-auto">
          <div
            className={cn(
              "h-2 w-32 rounded-full bg-gray-100 overflow-hidden"
            )}
          >
            <div
              className="h-full bg-blue-500 rounded-full transition-all"
              style={{ width: `${overallATS}%` }}
            />
          </div>
        </div>
      </Card>

      {/* Section cards */}
      <div className="flex flex-col gap-4">
        {SECTION_ORDER.map((key) => {
          const sectionData = cv[key];
          if (sectionData === undefined || sectionData === null) return null;

          // Cari QC result yang matching untuk section ini
          const qcResult = sections.find((s) => s.section === key) ?? null;

          return (
            <CVSectionCard
              key={key}
              sectionName={key}
              sectionData={sectionData}
              qcResult={qcResult}
              approvalStatus={approvals[key]}
              onApprovalChange={(status, instruction) =>
                handleApprovalChange(key, status, instruction)
              }
            />
          );
        })}
      </div>

      {/* Submit error */}
      {submitError && (
        <p className="text-sm text-red-600">{submitError}</p>
      )}

      {/* Submit button */}
      <div className="flex items-center justify-between pb-8">
        <p className="text-sm text-gray-500">
          {allApproved
            ? "All sections reviewed. Ready to submit."
            : `${
                SECTION_ORDER.filter(
                  (k) => cv[k] !== undefined && cv[k] !== null && approvals[k] !== null
                ).length
              } of ${
                SECTION_ORDER.filter(
                  (k) => cv[k] !== undefined && cv[k] !== null
                ).length
              } sections reviewed`}
        </p>
        <Button
          size="lg"
          loading={submitLoading}
          disabled={!allApproved}
          onClick={handleSubmit}
        >
          Submit Review
        </Button>
      </div>
    </div>
  );
}