// cv-agent/frontend/components/brief/brief-review.tsx

"use client";

import { useState, KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { NarrativeInstructionCard } from "./narrative-instruction-card";

// ── Types ─────────────────────────────────────────────────────────────────────
type Tone =
  | "technical_concise"
  | "professional_formal"
  | "professional_conversational";

interface ContentInstructionComponent {
  include: string[];
  top_n: number;
}

interface NarrativeInstruction {
  id: string;
  type: "implicit_match" | "gap_bridge";
  requirement: string;
  matched_with: string | null;
  suggested_angle: string;
  user_decision: "approved" | "adjusted" | "rejected" | null;
  custom_angle?: string;
}

interface BriefData {
  content_instructions: Record<string, ContentInstructionComponent>;
  narrative_instructions: NarrativeInstruction[];
  keyword_targets: string[];
  primary_angle: string;
  summary_hook_direction: string;
  tone: Tone;
}

interface BriefReviewProps {
  applicationId: string;
  data: Record<string, unknown>;
}

// ── Tone options ──────────────────────────────────────────────────────────────
const TONE_OPTIONS: { value: Tone; label: string; description: string }[] = [
  {
    value: "technical_concise",
    label: "Technical & Concise",
    description: "Direct, data-driven, minimal fluff",
  },
  {
    value: "professional_formal",
    label: "Professional & Formal",
    description: "Polished, structured, traditional",
  },
  {
    value: "professional_conversational",
    label: "Professional & Conversational",
    description: "Warm, approachable, narrative-driven",
  },
];

// ── Zone Section Wrapper ──────────────────────────────────────────────────────
function ZoneSection({
  color,
  label,
  description,
  children,
}: {
  color: "red" | "yellow" | "green";
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  const colorMap = {
    red:    { border: "border-red-200",    label: "text-red-700",    bg: "bg-red-50" },
    yellow: { border: "border-yellow-200", label: "text-yellow-700", bg: "bg-yellow-50" },
    green:  { border: "border-green-200",  label: "text-green-700",  bg: "bg-green-50" },
  };
  const c = colorMap[color];

  return (
    <div className={cn("rounded-lg border-2 overflow-hidden", c.border)}>
      {/* Zone header */}
      <div className={cn("px-5 py-3 flex items-center gap-2", c.bg)}>
        <span className={cn("text-sm font-semibold", c.label)}>{label}</span>
        <span className="text-xs text-gray-500">— {description}</span>
      </div>
      {/* Zone body */}
      <div className="px-5 py-5 bg-white flex flex-col gap-4">{children}</div>
    </div>
  );
}

// ── Tag Input ─────────────────────────────────────────────────────────────────
function TagInput({
  tags,
  onChange,
  error,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
  error?: string;
}) {
  const [inputValue, setInputValue] = useState("");

  function addTag(value: string) {
    const trimmed = value.trim();
    if (!trimmed || tags.includes(trimmed)) return;
    onChange([...tags, trimmed]);
    setInputValue("");
  }

  function removeTag(index: number) {
    const next = tags.filter((_, i) => i !== index);
    onChange(next);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(inputValue);
    }
    // Backspace pada input kosong → hapus tag terakhir
    if (e.key === "Backspace" && !inputValue && tags.length > 0) {
      removeTag(tags.length - 1);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-gray-700">
        Keyword Targets
      </label>
      <div
        className={cn(
          "min-h-10 w-full rounded-md border px-3 py-2",
          "flex flex-wrap gap-1.5 items-center",
          "focus-within:ring-2 focus-within:ring-blue-500 focus-within:ring-offset-1",
          error ? "border-red-400" : "border-gray-300"
        )}
      >
        {tags.map((tag, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(i)}
              className="text-blue-500 hover:text-blue-700 leading-none"
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => addTag(inputValue)}
          placeholder={tags.length === 0 ? "Type a keyword and press Enter..." : ""}
          className="flex-1 min-w-24 text-sm outline-none bg-transparent placeholder:text-gray-400"
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <p className="text-xs text-gray-500">
        Press Enter or comma to add a keyword
      </p>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export function BriefReview({ applicationId, data }: BriefReviewProps) {
  const router = useRouter();
  const brief = data as unknown as BriefData;

  // ── Zona Kuning state ───────────────────────────────────────────────────────
  const [keywords, setKeywords] = useState<string[]>(
    brief.keyword_targets ?? []
  );
  const [keywordError, setKeywordError] = useState<string | null>(null);
  const [narrativeInstructions, setNarrativeInstructions] = useState
    NarrativeInstruction[]
  >(brief.narrative_instructions ?? []);

  // ── Zona Hijau state ────────────────────────────────────────────────────────
  const [primaryAngle, setPrimaryAngle] = useState(brief.primary_angle ?? "");
  const [summaryHook, setSummaryHook] = useState(
    brief.summary_hook_direction ?? ""
  );
  const [tone, setTone] = useState<Tone>(brief.tone ?? "technical_concise");

  // ── Submit state ────────────────────────────────────────────────────────────
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function handleKeywordsChange(next: string[]) {
    setKeywords(next);
    if (next.length === 0) {
      setKeywordError("Keyword targets cannot be empty.");
    } else {
      setKeywordError(null);
    }
  }

  function handleNarrativeChange(updated: NarrativeInstruction) {
    setNarrativeInstructions((prev) =>
      prev.map((ni) => (ni.id === updated.id ? updated : ni))
    );
  }

  async function handleApprove() {
    // Validasi Zona Kuning sebelum submit
    if (keywords.length === 0) {
      setKeywordError("Keyword targets cannot be empty.");
      return;
    }

    setSubmitLoading(true);
    setSubmitError(null);

    const adjustedBrief = {
      keyword_targets:        keywords,
      narrative_instructions: narrativeInstructions,
      primary_angle:          primaryAngle,
      summary_hook_direction: summaryHook,
      tone,
    };

    try {
      await apiFetch(`/applications/${applicationId}/resume`, {
        method: "POST",
        body: JSON.stringify({
          action:         "approve",
          adjusted_brief: adjustedBrief,
        }),
      });
      router.push(`/apply/${applicationId}/cv`);
    } catch (err) {
      setSubmitError(
        err instanceof Error
          ? err.message
          : "Failed to approve brief. Please try again."
      );
      setSubmitLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">
          CV Strategy Brief
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Review and adjust the strategy before generating your CV
        </p>
      </div>

      {/* ── Zona Merah — Read-only ── */}
      <ZoneSection
        color="red"
        label="Zona Merah"
        description="Controlled by the system — cannot be edited"
      >
        <div className="flex items-start gap-2">
          <span className="text-lg mt-0.5">🔒</span>
          <div className="flex flex-col gap-3 flex-1">
            <p className="text-xs text-gray-500">
              This section is controlled by the system based on your profile data
              and the gap analysis results. Editing this would break consistency
              with your actual data.
            </p>
            <div className="flex flex-col gap-2">
              {Object.entries(brief.content_instructions ?? {}).map(
                ([component, config]) => (
                  <div
                    key={component}
                    className="flex items-center justify-between rounded-md bg-gray-50 border border-gray-200 px-3 py-2"
                  >
                    <span className="text-sm font-medium text-gray-700 capitalize">
                      {component}
                    </span>
                    <span className="text-xs text-gray-500">
                      {config.include?.length ?? 0} entries selected (top{" "}
                      {config.top_n})
                    </span>
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      </ZoneSection>

      {/* ── Zona Kuning — Editable with constraints ── */}
      <ZoneSection
        color="yellow"
        label="Zona Kuning"
        description="Editable with constraints"
      >
        {/* Tag input untuk keywords */}
        <TagInput
          tags={keywords}
          onChange={handleKeywordsChange}
          error={keywordError ?? undefined}
        />

        {/* Narrative instruction cards */}
        {narrativeInstructions.length > 0 && (
          <div className="flex flex-col gap-3">
            <p className="text-sm font-medium text-gray-700">
              Narrative Instructions
            </p>
            {narrativeInstructions.map((ni) => (
              <NarrativeInstructionCard
                key={ni.id}
                instruction={ni}
                onChange={handleNarrativeChange}
              />
            ))}
          </div>
        )}
      </ZoneSection>

      {/* ── Zona Hijau — Freely editable ── */}
      <ZoneSection
        color="green"
        label="Zona Hijau"
        description="Freely editable"
      >
        <Input
          label="Primary Angle"
          value={primaryAngle}
          onChange={(e) => setPrimaryAngle(e.target.value)}
          placeholder="e.g. Data professional dengan background ML yang kuat..."
        />

        <Textarea
          label="Summary Hook Direction"
          value={summaryHook}
          onChange={(e) => setSummaryHook(e.target.value)}
          placeholder="e.g. Buka dengan posisi sebagai data professional yang..."
          rows={3}
        />

        {/* Tone radio group */}
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-gray-700">Tone</p>
          <div className="flex flex-col gap-2">
            {TONE_OPTIONS.map((option) => (
              <label
                key={option.value}
                className={cn(
                  "flex items-start gap-3 rounded-md border px-4 py-3 cursor-pointer transition-colors",
                  tone === option.value
                    ? "border-blue-400 bg-blue-50"
                    : "border-gray-200 hover:bg-gray-50"
                )}
              >
                <input
                  type="radio"
                  name="tone"
                  value={option.value}
                  checked={tone === option.value}
                  onChange={() => setTone(option.value)}
                  className="mt-0.5 text-blue-600 focus:ring-blue-500"
                />
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-gray-900">
                    {option.label}
                  </span>
                  <span className="text-xs text-gray-500">
                    {option.description}
                  </span>
                </div>
              </label>
            ))}
          </div>
        </div>
      </ZoneSection>

      {/* Submit error */}
      {submitError && (
        <p className="text-sm text-red-600">{submitError}</p>
      )}

      {/* Approve button */}
      <div className="flex justify-end pb-8">
        <Button
          size="lg"
          loading={submitLoading}
          onClick={handleApprove}
        >
          Approve & Generate CV
        </Button>
      </div>
    </div>
  );
}