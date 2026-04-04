// cv-agent/frontend/components/cv/cv-section-card.tsx

"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

// ── Types ─────────────────────────────────────────────────────────────────────
type ApprovalStatus = "approved" | "revision_requested";

interface QCResult {
  section: string;
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

interface CVSectionCardProps {
  sectionName: string;
  sectionData: unknown;
  qcResult: QCResult | null;
  approvalStatus: ApprovalStatus | null;
  onApprovalChange: (status: ApprovalStatus, instruction: string) => void;
}

// ── QC Status Badge ───────────────────────────────────────────────────────────
function QCStatusBadge({ qcResult }: { qcResult: QCResult | null }) {
  if (!qcResult) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500">
        No QC data
      </span>
    );
  }

  const passed = !qcResult.action_required;
  const iteration = qcResult.iteration ?? 1;
  const passedAfterRetry = passed && iteration > 1;

  if (!passed) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-medium text-yellow-700">
        ⚠️ QC did not pass
      </span>
    );
  }

  if (passedAfterRetry) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">
        🔄 QC Passed after {iteration} iterations
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
      ✅ QC Passed
    </span>
  );
}

// ── Section Content Renderer ──────────────────────────────────────────────────
function SectionContent({
  sectionName,
  sectionData,
}: {
  sectionName: string;
  sectionData: unknown;
}) {
  // Summary — plain paragraph
  if (sectionName === "summary") {
    return (
      <p className="text-sm text-gray-700 leading-relaxed">
        {String(sectionData)}
      </p>
    );
  }

  // Skills — grouped layout
  if (sectionName === "skills") {
    const groups = sectionData as Record<string, string[]>;
    return (
      <div className="flex flex-col gap-2">
        {Object.entries(groups).map(([groupLabel, skillList]) => (
          <div key={groupLabel} className="flex gap-2 text-sm">
            <span className="font-medium text-gray-600 shrink-0 w-28 capitalize">
              {groupLabel}:
            </span>
            <span className="text-gray-700">{skillList.join(", ")}</span>
          </div>
        ))}
      </div>
    );
  }

  // Certificates — simple list
  if (sectionName === "certificates") {
    const certs = sectionData as Array<{ name: string; issuer?: string }>;
    return (
      <div className="flex flex-col gap-1.5">
        {certs.map((cert, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <span className="text-gray-700 font-medium">{cert.name}</span>
            {cert.issuer && (
              <span className="text-gray-400">— {cert.issuer}</span>
            )}
          </div>
        ))}
      </div>
    );
  }

  // Bullet-point sections: experience, education, projects, awards, organizations
  const entries = sectionData as Array<{
    company?: string;
    role?: string;
    title?: string;
    institution?: string;
    name?: string;
    bullets?: string[];
    [key: string]: unknown;
  }>;

  if (!Array.isArray(entries)) return null;

  return (
    <div className="flex flex-col gap-4">
      {entries.map((entry, i) => {
        // Derive display title per section type
        const entryTitle =
          entry.role ?? entry.title ?? entry.institution ?? entry.name ?? `Entry ${i + 1}`;
        const entrySubtitle =
          entry.company ?? entry.issuer ?? entry.url ?? null;
        const bullets = entry.bullets ?? [];

        return (
          <div key={i} className="flex flex-col gap-1.5">
            <div className="flex flex-col gap-0">
              <p className="text-sm font-semibold text-gray-900">{entryTitle}</p>
              {entrySubtitle && (
                <p className="text-xs text-gray-500">{String(entrySubtitle)}</p>
              )}
            </div>
            {bullets.length > 0 && (
              <ul className="flex flex-col gap-1 pl-4">
                {bullets.map((bullet, j) => (
                  <li
                    key={j}
                    className="text-sm text-gray-700 list-disc leading-relaxed"
                  >
                    {bullet}
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── QC Details Panel ──────────────────────────────────────────────────────────
function QCDetailsPanel({ qcResult }: { qcResult: QCResult }) {
  const [isOpen, setIsOpen] = useState(false);
  const hasPreserve = qcResult.preserve?.length > 0;
  const hasRevise = qcResult.revise?.length > 0;

  if (!hasPreserve && !hasRevise) return null;

  return (
    <div className="border-t border-gray-100 pt-3">
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors"
      >
        <span>{isOpen ? "▲" : "▼"}</span>
        QC Details
      </button>

      {isOpen && (
        <div className="mt-3 flex flex-col gap-3">
          {hasPreserve && (
            <div className="flex flex-col gap-1.5">
              <p className="text-xs font-semibold text-green-700">
                ✅ What's working well
              </p>
              <ul className="flex flex-col gap-1 pl-3">
                {qcResult.preserve.map((item, i) => (
                  <li key={i} className="text-xs text-green-700 list-disc">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasRevise && (
            <div className="flex flex-col gap-1.5">
              <p className="text-xs font-semibold text-amber-700">
                💡 Suggested improvements
              </p>
              <ul className="flex flex-col gap-1 pl-3">
                {qcResult.revise.map((item, i) => (
                  <li key={i} className="text-xs text-amber-700 list-disc">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export function CVSectionCard({
  sectionName,
  sectionData,
  qcResult,
  approvalStatus,
  onApprovalChange,
}: CVSectionCardProps) {
  const [showRevisionInput, setShowRevisionInput] = useState(
    approvalStatus === "revision_requested"
  );
  const [revisionText, setRevisionText] = useState("");

  // Left border color berdasarkan approval status
  const borderColor = {
    approved:           "border-l-green-400",
    revision_requested: "border-l-amber-400",
    null:               "border-l-gray-200",
  }[approvalStatus ?? "null"];

  function handleApprove() {
    setShowRevisionInput(false);
    onApprovalChange("approved", "");
  }

  function handleRequestRevision() {
    setShowRevisionInput(true);
  }

  function handleConfirmRevision() {
    if (!revisionText.trim()) return;
    onApprovalChange("revision_requested", revisionText.trim());
    setShowRevisionInput(false);
  }

  function handleCancelRevision() {
    setShowRevisionInput(false);
    if (approvalStatus !== "revision_requested") {
      setRevisionText("");
    }
  }

  return (
    <Card
      className={cn(
        "flex flex-col gap-4 border-l-4 transition-colors",
        borderColor
      )}
    >
      {/* Card header */}
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-gray-900 capitalize">
          {sectionName}
        </h3>
        <QCStatusBadge qcResult={qcResult} />
      </div>

      {/* Section content */}
      <SectionContent sectionName={sectionName} sectionData={sectionData} />

      {/* QC details collapsible */}
      {qcResult && <QCDetailsPanel qcResult={qcResult} />}

      {/* Revision textarea */}
      {showRevisionInput && (
        <div className="flex flex-col gap-2 border-t border-gray-100 pt-3">
          <label className="text-xs font-medium text-gray-600">
            Describe the revision you want:
          </label>
          <textarea
            value={revisionText}
            onChange={(e) => setRevisionText(e.target.value)}
            rows={3}
            placeholder="e.g. Add context that this project was used in production by 500+ users..."
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 resize-y"
          />
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" size="sm" onClick={handleCancelRevision}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleConfirmRevision}
              disabled={!revisionText.trim()}
            >
              Confirm revision
            </Button>
          </div>
        </div>
      )}

      {/* Approval controls */}
      {!showRevisionInput && (
        <div className="flex items-center gap-2 border-t border-gray-100 pt-3">
          <Button
            variant={approvalStatus === "approved" ? "primary" : "secondary"}
            size="sm"
            onClick={handleApprove}
          >
            ✅ Approve this section
          </Button>
          <Button
            variant={
              approvalStatus === "revision_requested" ? "primary" : "ghost"
            }
            size="sm"
            onClick={handleRequestRevision}
          >
            ✏️ Request revision
          </Button>
        </div>
      )}
    </Card>
  );
}