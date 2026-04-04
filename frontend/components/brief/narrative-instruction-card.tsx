// cv-agent/frontend/components/brief/narrative-instruction-card.tsx

"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

// ── Types ─────────────────────────────────────────────────────────────────────
interface NarrativeInstruction {
  id: string;
  type: "implicit_match" | "gap_bridge";
  requirement: string;
  matched_with: string | null;
  suggested_angle: string;
  user_decision: "approved" | "adjusted" | "rejected" | null;
  custom_angle?: string;
}

interface NarrativeInstructionCardProps {
  instruction: NarrativeInstruction;
  onChange: (updated: NarrativeInstruction) => void;
}

// ── Component ─────────────────────────────────────────────────────────────────
export function NarrativeInstructionCard({
  instruction,
  onChange,
}: NarrativeInstructionCardProps) {
  const [showAdjustInput, setShowAdjustInput] = useState(
    instruction.user_decision === "adjusted"
  );
  const [customAngle, setCustomAngle] = useState(
    instruction.custom_angle ?? ""
  );

  const decision = instruction.user_decision;

  // Border color berdasarkan keputusan user
  const borderColor = {
    approved: "border-green-400",
    adjusted: "border-blue-400",
    rejected: "border-gray-200 opacity-60",
    null:     "border-gray-200",
  }[decision ?? "null"];

  function handleApprove() {
    setShowAdjustInput(false);
    onChange({ ...instruction, user_decision: "approved", custom_angle: undefined });
  }

  function handleReject() {
    setShowAdjustInput(false);
    onChange({ ...instruction, user_decision: "rejected", custom_angle: undefined });
  }

  function handleShowAdjust() {
    setShowAdjustInput(true);
  }

  function handleConfirmAdjust() {
    if (!customAngle.trim()) return;
    onChange({
      ...instruction,
      user_decision: "adjusted",
      custom_angle:  customAngle.trim(),
    });
    setShowAdjustInput(false);
  }

  function handleCancelAdjust() {
    setShowAdjustInput(false);
    setCustomAngle(instruction.custom_angle ?? "");
  }

  return (
    <div
      className={cn(
        "rounded-lg border-2 overflow-hidden transition-all",
        borderColor
      )}
    >
      {/* Card Header */}
      <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b border-gray-100">
        <span className="text-base">
          {instruction.type === "implicit_match" ? "⚡" : "❌"}
        </span>
        <span className="text-sm font-semibold text-gray-800 capitalize">
          {instruction.type === "implicit_match"
            ? "Implicit Match"
            : "Gap Bridge"}{" "}
          —{" "}
        </span>
        <span className="text-sm text-gray-600 truncate">
          {instruction.requirement}
        </span>

        {/* Decision badge */}
        {decision && (
          <span
            className={cn(
              "ml-auto shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
              decision === "approved" && "bg-green-100 text-green-700",
              decision === "adjusted" && "bg-blue-100 text-blue-700",
              decision === "rejected" && "bg-gray-100 text-gray-500"
            )}
          >
            {decision === "approved"
              ? "✓ Setuju"
              : decision === "adjusted"
              ? "✏ Diubah"
              : "✕ Ditolak"}
          </span>
        )}
      </div>

      {/* Card body — disembunyikan saat rejected */}
      <div
        className={cn(
          "px-4 py-4 flex flex-col gap-3",
          decision === "rejected" && "opacity-50"
        )}
      >
        {/* Requirement + matched_with */}
        <div className="flex flex-col gap-1.5">
          <div className="flex gap-2 text-sm">
            <span className="font-medium text-gray-600 shrink-0 w-40">
              Perusahaan mensyaratkan:
            </span>
            <span className="text-gray-800">{instruction.requirement}</span>
          </div>
          <div className="flex gap-2 text-sm">
            <span className="font-medium text-gray-600 shrink-0 w-40">
              Yang Anda miliki:
            </span>
            <span className={cn(
              instruction.matched_with ? "text-gray-800" : "text-gray-400 italic"
            )}>
              {instruction.matched_with ?? "Tidak ditemukan"}
            </span>
          </div>
        </div>

        {/* Suggested angle */}
        <div className="rounded-md bg-blue-50 border border-blue-100 px-3 py-2">
          <p className="text-xs font-medium text-blue-600 mb-1">
            Suggested angle:
          </p>
          <p className="text-sm text-blue-800">{instruction.suggested_angle}</p>
        </div>

        {/* Custom angle (saat adjusted) */}
        {decision === "adjusted" && instruction.custom_angle && !showAdjustInput && (
          <div className="rounded-md bg-gray-50 border border-gray-200 px-3 py-2">
            <p className="text-xs font-medium text-gray-500 mb-1">
              Your angle:
            </p>
            <p className="text-sm text-gray-800">{instruction.custom_angle}</p>
          </div>
        )}

        {/* Adjust textarea — muncul saat user klik "Ubah angle" */}
        {showAdjustInput && (
          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-gray-600">
              Write your own angle:
            </label>
            <textarea
              value={customAngle}
              onChange={(e) => setCustomAngle(e.target.value)}
              rows={3}
              placeholder="Describe how you want this to be narrated in your CV..."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 resize-y"
            />
            <div className="flex gap-2 justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCancelAdjust}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmAdjust}
                disabled={!customAngle.trim()}
              >
                Confirm
              </Button>
            </div>
          </div>
        )}

        {/* Action buttons — tersembunyi saat adjust input terbuka */}
        {!showAdjustInput && (
          <div className="flex gap-2 pt-1">
            <Button
              variant={decision === "approved" ? "primary" : "secondary"}
              size="sm"
              onClick={handleApprove}
            >
              ✅ Setuju
            </Button>
            <Button
              variant={decision === "adjusted" ? "primary" : "secondary"}
              size="sm"
              onClick={handleShowAdjust}
            >
              ✏️ Ubah angle
            </Button>
            <Button
              variant={decision === "rejected" ? "destructive" : "ghost"}
              size="sm"
              onClick={handleReject}
            >
              ❌ Tidak masukkan
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}