// cv-agent/frontend/components/profile/skill-suggestions-panel.tsx

"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// ── Types ─────────────────────────────────────────────────────────────────────
interface SkillSuggestion {
  name: string;
  category: string;
  source: string;
}

interface SkillSuggestionsProps {
  suggestions: SkillSuggestion[];
  onDone: () => void;
}

// ── Component ─────────────────────────────────────────────────────────────────
export function SkillSuggestionsPanel({ suggestions, onDone }: SkillSuggestionsProps) {
  // Semua skill pre-checked by default sesuai spec
  const [checked, setChecked] = useState<Record<string, boolean>>(
    () => Object.fromEntries(suggestions.map((s) => [s.name, true]))
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleSkill(name: string) {
    setChecked((prev) => ({ ...prev, [name]: !prev[name] }));
  }

  async function handleSave() {
    setLoading(true);
    setError(null);

    // Pisahkan menjadi approved dan rejected berdasarkan checkbox state
    const approved = suggestions.filter((s) => checked[s.name]);
    const rejected = suggestions.filter((s) => !checked[s.name]);

    try {
      await apiFetch("/profile/inferred-skills/batch", {
        method: "POST",
        body: JSON.stringify({ approved, rejected }),
      });
      onDone();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save skills. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  const categoryBadgeVariant: Record<string, "info" | "success" | "neutral"> = {
    technical: "info",
    soft:      "success",
    tool:      "neutral",
  };

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">
          Skill Suggestions
        </h3>
        <p className="mt-0.5 text-xs text-gray-500">
          Based on the entry you just saved, the system detected the following
          skills. Select which ones to add to your profile.
        </p>
      </div>

      {/* Skill list with checkboxes */}
      <div className="flex flex-col gap-2">
        {suggestions.map((skill) => (
          <label
            key={skill.name}
            className="flex items-start gap-3 rounded-md border border-gray-200 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
          >
            <input
              type="checkbox"
              checked={checked[skill.name] ?? true}
              onChange={() => toggleSkill(skill.name)}
              className="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <div className="flex flex-col gap-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">
                  {skill.name}
                </span>
                <Badge variant={categoryBadgeVariant[skill.category] ?? "neutral"}>
                  {skill.category}
                </Badge>
              </div>
              <span className="text-xs text-gray-500">{skill.source}</span>
            </div>
          </label>
        ))}
      </div>

      {/* Error */}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Actions */}
      <div className="flex items-center justify-between pt-1">
        <p className="text-xs text-gray-500">
          {Object.values(checked).filter(Boolean).length} of {suggestions.length} selected
        </p>
        <Button
          variant="primary"
          size="sm"
          loading={loading}
          onClick={handleSave}
        >
          Save selected skills
        </Button>
      </div>
    </div>
  );
}