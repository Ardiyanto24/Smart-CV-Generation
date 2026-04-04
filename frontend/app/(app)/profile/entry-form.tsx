// cv-agent/frontend/components/profile/entry-form.tsx

"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { SkillSuggestionsPanel } from "./skill-suggestions-panel";

// ── Field definitions ─────────────────────────────────────────────────────────
type FieldType = "text" | "textarea" | "date" | "checkbox" | "select";

interface FieldDef {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: { value: string; label: string }[]; // untuk select
  placeholder?: string;
}

const FIELD_CONFIG: Record<string, FieldDef[]> = {
  experience: [
    { name: "company",    label: "Company",    type: "text",     required: true },
    { name: "role",       label: "Role",       type: "text",     required: true },
    { name: "start_date", label: "Start Date", type: "date" },
    { name: "end_date",   label: "End Date",   type: "date" },
    { name: "is_current", label: "Currently working here", type: "checkbox" },
    { name: "what_i_did", label: "What I Did", type: "textarea", required: true,
      placeholder: "Describe your responsibilities and activities..." },
    { name: "challenge",  label: "Challenges", type: "textarea",
      placeholder: "What challenges did you face?" },
    { name: "impact",     label: "Impact",     type: "textarea",
      placeholder: "What was the outcome or impact?" },
  ],
  education: [
    { name: "institution",    label: "Institution",     type: "text", required: true },
    { name: "degree",         label: "Degree",          type: "text" },
    { name: "field_of_study", label: "Field of Study",  type: "text" },
    { name: "start_date",     label: "Start Date",      type: "date" },
    { name: "end_date",       label: "End Date",        type: "date" },
    { name: "is_current",     label: "Currently studying here", type: "checkbox" },
    { name: "what_i_did",     label: "Activities",      type: "textarea",
      placeholder: "Describe your academic activities..." },
    { name: "impact",         label: "Achievements",    type: "textarea",
      placeholder: "GPA, awards, notable achievements..." },
  ],
  projects: [
    { name: "title",      label: "Project Title", type: "text",     required: true },
    { name: "url",        label: "URL",           type: "text",     placeholder: "https://..." },
    { name: "start_date", label: "Start Date",    type: "date" },
    { name: "end_date",   label: "End Date",      type: "date" },
    { name: "what_i_did", label: "What I Built",  type: "textarea", required: true,
      placeholder: "Describe what you built and your role..." },
    { name: "challenge",  label: "Challenges",    type: "textarea",
      placeholder: "What technical or non-technical challenges did you face?" },
    { name: "impact",     label: "Impact",        type: "textarea",
      placeholder: "Users, metrics, outcomes..." },
  ],
  awards: [
    { name: "title",      label: "Award Title",  type: "text", required: true },
    { name: "issuer",     label: "Issued By",    type: "text" },
    { name: "date",       label: "Date",         type: "date" },
    { name: "what_i_did", label: "What I Did",   type: "textarea",
      placeholder: "Describe what you did to earn this award..." },
    { name: "impact",     label: "Significance", type: "textarea",
      placeholder: "Why is this award significant?" },
  ],
  organizations: [
    { name: "name",       label: "Organization Name", type: "text", required: true },
    { name: "role",       label: "Role",              type: "text" },
    { name: "start_date", label: "Start Date",        type: "date" },
    { name: "end_date",   label: "End Date",          type: "date" },
    { name: "is_current", label: "Currently active",  type: "checkbox" },
    { name: "what_i_did", label: "What I Did",        type: "textarea",
      placeholder: "Describe your contributions..." },
    { name: "impact",     label: "Impact",            type: "textarea",
      placeholder: "What impact did you make?" },
  ],
  certificates: [
    { name: "name",         label: "Certificate Name", type: "text", required: true },
    { name: "issuer",       label: "Issued By",        type: "text" },
    { name: "issue_date",   label: "Issue Date",       type: "date" },
    { name: "expiry_date",  label: "Expiry Date",      type: "date" },
    { name: "url",          label: "Certificate URL",  type: "text", placeholder: "https://..." },
  ],
  skills: [
    { name: "name",     label: "Skill Name", type: "text", required: true },
    { name: "category", label: "Category",   type: "select", required: true,
      options: [
        { value: "technical", label: "Technical" },
        { value: "soft",      label: "Soft Skill" },
        { value: "tool",      label: "Tool" },
      ],
    },
  ],
};

// ── Types ─────────────────────────────────────────────────────────────────────
interface SkillSuggestion {
  name: string;
  category: string;
  source: string;
}

interface EntryFormProps {
  component: string;
  entry: Record<string, unknown> | null;
  onSuccess: () => void;
  onCancel: () => void;
}

// ── Component ─────────────────────────────────────────────────────────────────
export function EntryForm({ component, entry, onSuccess, onCancel }: EntryFormProps) {
  const fields = FIELD_CONFIG[component] ?? [];
  const isEdit = entry !== null;

  // Inisialisasi form values dari entry (edit) atau kosong (add)
  const [values, setValues] = useState<Record<string, string | boolean>>(() => {
    const initial: Record<string, string | boolean> = {};
    for (const field of fields) {
      if (field.type === "checkbox") {
        initial[field.name] = Boolean(entry?.[field.name] ?? false);
      } else {
        initial[field.name] = String(entry?.[field.name] ?? "");
      }
    }
    return initial;
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [skillSuggestions, setSkillSuggestions] = useState<SkillSuggestion[] | null>(null);
  const [staleSkills, setStaleSkills] = useState<string[] | null>(null);
  const [showStaleBanner, setShowStaleBanner] = useState(true);

  function handleChange(name: string, value: string | boolean) {
    setValues((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Validasi required fields
    for (const field of fields) {
      if (field.required && !values[field.name]) {
        setError(`${field.label} is required.`);
        setLoading(false);
        return;
      }
    }

    try {
      const url = isEdit
        ? `/profile/${component}/${String(entry!.id)}`
        : `/profile/${component}`;
      const method = isEdit ? "PUT" : "POST";

      const response = await apiFetch(url, {
        method,
        body: JSON.stringify(values),
      });

      // Handle skill suggestions dari Profile Ingestion Agent
      if (response?.skill_suggestions?.length > 0) {
        setSkillSuggestions(response.skill_suggestions);
        return; // Tahan onSuccess sampai user selesai review suggestions
      }

      // Handle stale skills notification
      if (response?.stale_skills?.length > 0) {
        setStaleSkills(response.stale_skills);
        setShowStaleBanner(true);
      }

      onSuccess();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  // Tampilkan SkillSuggestionsPanel jika ada suggestions
  if (skillSuggestions) {
    return (
      <SkillSuggestionsPanel
        suggestions={skillSuggestions}
        onDone={onSuccess}
      />
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-gray-900">
        {isEdit ? `Edit ${component}` : `Add ${component}`}
      </h3>

      {/* Stale skills warning banner */}
      {staleSkills && showStaleBanner && (
        <div className="flex items-start justify-between gap-3 rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3">
          <div>
            <p className="text-sm font-medium text-yellow-800">
              Skills no longer detected
            </p>
            <p className="mt-0.5 text-xs text-yellow-700">
              The following skills were previously inferred from this entry but
              are no longer detected:{" "}
              <span className="font-medium">{staleSkills.join(", ")}</span>.
              You may want to review and remove them from your skills list.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowStaleBanner(false)}
            className="text-yellow-600 hover:text-yellow-800 text-sm shrink-0"
          >
            ✕
          </button>
        </div>
      )}

      {/* Dynamic form fields */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {fields.map((field) => {
          if (field.type === "checkbox") {
            return (
              <label
                key={field.name}
                className="flex items-center gap-2 text-sm text-gray-700 sm:col-span-2"
              >
                <input
                  type="checkbox"
                  checked={Boolean(values[field.name])}
                  onChange={(e) => handleChange(field.name, e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                {field.label}
              </label>
            );
          }

          if (field.type === "textarea") {
            return (
              <div key={field.name} className="sm:col-span-2">
                <Textarea
                  label={field.label}
                  value={String(values[field.name] ?? "")}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  rows={3}
                />
              </div>
            );
          }

          if (field.type === "select") {
            return (
              <div key={field.name} className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-gray-700">
                  {field.label}
                </label>
                <select
                  value={String(values[field.name] ?? "")}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  className="h-10 w-full rounded-md border border-gray-300 px-3 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
                >
                  <option value="">Select {field.label}</option>
                  {field.options?.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            );
          }

          // Default: text or date input
          return (
            <Input
              key={field.name}
              label={field.label}
              type={field.type}
              value={String(values[field.name] ?? "")}
              onChange={(e) => handleChange(field.name, e.target.value)}
              placeholder={field.placeholder}
            />
          );
        })}
      </div>

      {/* Error message */}
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {/* Form actions */}
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button variant="ghost" size="sm" type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" size="sm" type="submit" loading={loading}>
          {isEdit ? "Save changes" : "Add entry"}
        </Button>
      </div>
    </form>
  );
}