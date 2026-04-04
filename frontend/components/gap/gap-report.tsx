// cv-agent/frontend/components/gap/gap-report.tsx

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────
type Category = "exact_match" | "implicit_match" | "gap";
type Verdict = "sangat_cocok" | "cukup_cocok" | "kurang_cocok";
type Dimension = "JD" | "JR";
type Priority = "must" | "nice_to_have";

interface Evidence {
  source: string;
  entry_title: string;
  detail: string;
}

interface GapItem {
  item_id: string;
  text: string;
  dimension: Dimension;
  category: Category;
  priority?: Priority;
  evidence?: Evidence[];
  reasoning?: string;
  suggestion?: string;
}

interface GapScore {
  quantitative_score: number;
  verdict: Verdict;
  strength: string;
  concern: string;
  recommendation: string;
}

interface GapData {
  results: GapItem[];
  score: GapScore;
}

interface GapReportProps {
  applicationId: string;
  data: Record<string, unknown>;
}

// ── Verdict config ────────────────────────────────────────────────────────────
const VERDICT_CONFIG: Record
  Verdict,
  { label: string; bg: string; text: string; border: string }
> = {
  sangat_cocok: {
    label:  "Sangat Cocok",
    bg:     "bg-green-50",
    text:   "text-green-800",
    border: "border-green-200",
  },
  cukup_cocok: {
    label:  "Cukup Cocok",
    bg:     "bg-yellow-50",
    text:   "text-yellow-800",
    border: "border-yellow-200",
  },
  kurang_cocok: {
    label:  "Kurang Cocok",
    bg:     "bg-red-50",
    text:   "text-red-800",
    border: "border-red-200",
  },
};

// ── Section config ────────────────────────────────────────────────────────────
const SECTION_CONFIG = {
  exact_match: {
    icon:        "✅",
    label:       "Exact Match",
    headerBg:    "bg-green-50",
    headerText:  "text-green-800",
    headerBorder:"border-green-200",
  },
  implicit_match: {
    icon:        "⚡",
    label:       "Implicit Match",
    headerBg:    "bg-yellow-50",
    headerText:  "text-yellow-800",
    headerBorder:"border-yellow-200",
  },
  gap: {
    icon:        "❌",
    label:       "Gap",
    headerBg:    "bg-red-50",
    headerText:  "text-red-800",
    headerBorder:"border-red-200",
  },
} as const;

// ── Sub-components ────────────────────────────────────────────────────────────
function GapItemRow({ item }: { item: GapItem }) {
  return (
    <div className="flex flex-col gap-2 border-b border-gray-100 py-3 last:border-0 last:pb-0">
      {/* Item text + badges */}
      <div className="flex flex-wrap items-start gap-2">
        <p className="text-sm text-gray-800 flex-1">{item.text}</p>
        <div className="flex items-center gap-1.5 shrink-0">
          <Badge variant="neutral">{item.dimension}</Badge>
          {item.category === "gap" && item.priority && (
            <Badge variant={item.priority === "must" ? "error" : "warning"}>
              {item.priority === "must" ? "MUST" : "NICE TO HAVE"}
            </Badge>
          )}
        </div>
      </div>

      {/* Evidence list — untuk exact_match dan implicit_match */}
      {item.evidence && item.evidence.length > 0 && (
        <div className="flex flex-col gap-1 pl-3 border-l-2 border-gray-200">
          <p className="text-xs font-medium text-gray-500">Evidence:</p>
          {item.evidence.map((ev, i) => (
            <p key={i} className="text-xs text-gray-600">
              <span className="font-medium capitalize">{ev.source}</span>
              {" — "}
              {ev.entry_title}: {ev.detail}
            </p>
          ))}
        </div>
      )}

      {/* Reasoning — untuk implicit_match */}
      {item.reasoning && (
        <div className="pl-3 border-l-2 border-yellow-200">
          <p className="text-xs font-medium text-gray-500">Reasoning:</p>
          <p className="text-xs text-gray-600">{item.reasoning}</p>
        </div>
      )}

      {/* Suggestion — untuk gap */}
      {item.suggestion && (
        <div className="pl-3 border-l-2 border-red-200">
          <p className="text-xs text-gray-600">
            <span className="font-medium">→ </span>
            {item.suggestion}
          </p>
        </div>
      )}
    </div>
  );
}

function CollapsibleSection({
  category,
  items,
}: {
  category: Category;
  items: GapItem[];
}) {
  const [isOpen, setIsOpen] = useState(true);
  const config = SECTION_CONFIG[category];

  // Hitung breakdown JD vs JR
  const jdCount = items.filter((i) => i.dimension === "JD").length;
  const jrCount = items.filter((i) => i.dimension === "JR").length;

  return (
    <div className={cn("rounded-lg border overflow-hidden", config.headerBorder)}>
      {/* Section header — clickable untuk collapse */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "w-full flex items-center justify-between px-4 py-3 text-left",
          "transition-colors hover:brightness-95",
          config.headerBg
        )}
      >
        <div className="flex items-center gap-2">
          <span>{config.icon}</span>
          <span className={cn("text-sm font-semibold", config.headerText)}>
            {config.label}
          </span>
          <span className={cn("text-sm", config.headerText)}>
            ({items.length} items — {jrCount} JR, {jdCount} JD)
          </span>
        </div>
        <span className={cn("text-sm", config.headerText)}>
          {isOpen ? "▲" : "▼"}
        </span>
      </button>

      {/* Section body */}
      {isOpen && (
        <div className="px-4 py-2 bg-white">
          {items.length === 0 ? (
            <p className="py-4 text-center text-sm text-gray-400">
              No items in this category
            </p>
          ) : (
            items.map((item) => (
              <GapItemRow key={item.item_id} item={item} />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export function GapReport({ applicationId, data }: GapReportProps) {
  const router = useRouter();
  const [proceedLoading, setProceedLoading] = useState(false);
  const [goBackLoading, setGoBackLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Cast data ke GapData — data datang dari server sebagai unknown
  const gapData = data as unknown as GapData;
  const { results = [], score } = gapData;

  // Kelompokkan items per kategori
  const exactMatches   = results.filter((r) => r.category === "exact_match");
  const implicitMatches = results.filter((r) => r.category === "implicit_match");
  const gaps           = results.filter((r) => r.category === "gap");

  const verdictConfig = score?.verdict
    ? VERDICT_CONFIG[score.verdict]
    : VERDICT_CONFIG.cukup_cocok;

  async function handleProceed() {
    setProceedLoading(true);
    setActionError(null);
    try {
      await apiFetch(`/applications/${applicationId}/resume`, {
        method: "POST",
        body: JSON.stringify({ action: "proceed" }),
      });
      router.push(`/apply/${applicationId}/brief`);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to proceed. Please try again."
      );
      setProceedLoading(false);
    }
  }

  async function handleGoBack() {
    setGoBackLoading(true);
    setActionError(null);
    try {
      await apiFetch(`/applications/${applicationId}/resume`, {
        method: "POST",
        body: JSON.stringify({ action: "go_back" }),
      });
      router.push("/profile");
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to go back. Please try again."
      );
      setGoBackLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto">
      {/* Page title */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Gap Analysis Report</h1>
        <p className="mt-1 text-sm text-gray-500">
          Review how your profile matches the job requirements
        </p>
      </div>

      {/* Score section */}
      {score && (
        <div
          className={cn(
            "rounded-lg border p-6 flex flex-col gap-4",
            verdictConfig.bg,
            verdictConfig.border
          )}
        >
          {/* Score + verdict */}
          <div className="flex items-center gap-4">
            <div className="flex items-baseline gap-1">
              <span className={cn("text-5xl font-bold", verdictConfig.text)}>
                {Math.round(score.quantitative_score)}
              </span>
              <span className={cn("text-xl", verdictConfig.text)}>/100</span>
            </div>
            <div
              className={cn(
                "rounded-full px-3 py-1 text-sm font-semibold",
                verdictConfig.bg,
                verdictConfig.text,
                "border",
                verdictConfig.border
              )}
            >
              {verdictConfig.label}
            </div>
          </div>

          {/* Qualitative assessment rows */}
          <div className="flex flex-col gap-2">
            <div className="flex gap-2 text-sm">
              <span className={cn("font-medium shrink-0", verdictConfig.text)}>
                Kekuatan :
              </span>
              <span className={cn(verdictConfig.text)}>{score.strength}</span>
            </div>
            <div className="flex gap-2 text-sm">
              <span className={cn("font-medium shrink-0", verdictConfig.text)}>
                Perhatian :
              </span>
              <span className={cn(verdictConfig.text)}>{score.concern}</span>
            </div>
            <div className="flex gap-2 text-sm">
              <span className={cn("font-medium shrink-0", verdictConfig.text)}>
                Saran :
              </span>
              <span className={cn(verdictConfig.text)}>{score.recommendation}</span>
            </div>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <Button onClick={handleProceed} loading={proceedLoading}>
          Lanjut Generate CV
        </Button>
        <Button
          variant="ghost"
          onClick={handleGoBack}
          loading={goBackLoading}
        >
          Kembali Update Profil
        </Button>
      </div>

      {actionError && (
        <p className="text-sm text-red-600">{actionError}</p>
      )}

      {/* Three collapsible sections */}
      <div className="flex flex-col gap-3">
        <CollapsibleSection category="exact_match"    items={exactMatches} />
        <CollapsibleSection category="implicit_match" items={implicitMatches} />
        <CollapsibleSection category="gap"            items={gaps} />
      </div>
    </div>
  );
}