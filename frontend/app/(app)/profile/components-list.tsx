// cv-agent/frontend/components/profile/component-list.tsx

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { EntryForm } from "./entry-form";

// ── Display config ────────────────────────────────────────────────────────────
// Menentukan field mana yang ditampilkan sebagai judul dan subtitle per komponen
type DisplayConfig = {
  title: (entry: Record<string, unknown>) => string;
  subtitle?: (entry: Record<string, unknown>) => string;
};

const DISPLAY_CONFIG: Record<string, DisplayConfig> = {
  experience: {
    title:    (e) => String(e.role ?? ""),
    subtitle: (e) => String(e.company ?? ""),
  },
  education: {
    title:    (e) => String(e.institution ?? ""),
    subtitle: (e) => [e.degree, e.field_of_study].filter(Boolean).join(", "),
  },
  projects: {
    title:    (e) => String(e.title ?? ""),
    subtitle: (e) => e.url ? String(e.url) : "",
  },
  awards: {
    title:    (e) => String(e.title ?? ""),
    subtitle: (e) => String(e.issuer ?? ""),
  },
  organizations: {
    title:    (e) => String(e.name ?? ""),
    subtitle: (e) => String(e.role ?? ""),
  },
  certificates: {
    title:    (e) => String(e.name ?? ""),
    subtitle: (e) => String(e.issuer ?? ""),
  },
  skills: {
    title:    (e) => String(e.name ?? ""),
    subtitle: (e) => String(e.category ?? ""),
  },
};

// ── Props ─────────────────────────────────────────────────────────────────────
interface ComponentListProps {
  component: string;
  entries: Record<string, unknown>[];
}

// ── Component ─────────────────────────────────────────────────────────────────
export function ComponentList({ component, entries }: ComponentListProps) {
  const router = useRouter();
  const config = DISPLAY_CONFIG[component];

  // State untuk inline add/edit form
  const [formMode, setFormMode] = useState<"add" | "edit" | null>(null);
  const [editingEntry, setEditingEntry] = useState<Record<string, unknown> | null>(null);

  // State untuk delete confirmation
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function handleAdd() {
    setEditingEntry(null);
    setFormMode("add");
  }

  function handleEdit(entry: Record<string, unknown>) {
    setEditingEntry(entry);
    setFormMode("edit");
  }

  function handleFormSuccess() {
    setFormMode(null);
    setEditingEntry(null);
    // Refresh server data dengan re-fetch halaman
    router.refresh();
  }

  function handleFormCancel() {
    setFormMode(null);
    setEditingEntry(null);
  }

  async function handleDelete(id: string) {
    setDeleteLoading(true);
    setDeleteError(null);
    try {
      await apiFetch(`/profile/${component}/${id}`, { method: "DELETE" });
      setDeletingId(null);
      router.refresh();
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete. Please try again."
      );
    } finally {
      setDeleteLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900 capitalize">
          {component}
        </h2>
        {formMode === null && (
          <button
            onClick={handleAdd}
            className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 h-9 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
          >
            + Add
          </button>
        )}
      </div>

      {/* Inline Add/Edit Form */}
      {formMode !== null && (
        <Card>
          <EntryForm
            component={component}
            entry={formMode === "edit" ? editingEntry : null}
            onSuccess={handleFormSuccess}
            onCancel={handleFormCancel}
          />
        </Card>
      )}

      {/* Entry List */}
      {entries.length === 0 && formMode === null ? (
        <EmptyState
          title={`No ${component} added yet`}
          description="Add your first entry to build your profile."
          action={
            <button
              onClick={handleAdd}
              className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 h-9 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
            >
              Add {component}
            </button>
          }
        />
      ) : (
        <div className="flex flex-col gap-2">
          {entries.map((entry) => {
            const id = String(entry.id);
            const isDeleting = deletingId === id;

            return (
              <Card key={id} className="flex items-start justify-between gap-4 py-4">
                {/* Entry display */}
                <div className="flex flex-col gap-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {config?.title(entry)}
                    </p>
                    {entry.is_inferred && (
                      <Badge variant="info">Inferred</Badge>
                    )}
                  </div>
                  {config?.subtitle && (
                    <p className="text-xs text-gray-500 truncate">
                      {config.subtitle(entry)}
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {isDeleting ? (
                    // Delete confirmation prompt
                    <div className="flex flex-col items-end gap-2">
                      {deleteError && (
                        <p className="text-xs text-red-600">{deleteError}</p>
                      )}
                      <div className="flex gap-2">
                        <span className="text-xs text-gray-600 self-center">
                          Delete this entry?
                        </span>
                        <Button
                          variant="destructive"
                          size="sm"
                          loading={deleteLoading}
                          onClick={() => handleDelete(id)}
                        >
                          Confirm
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setDeletingId(null);
                            setDeleteError(null);
                          }}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEdit(entry)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeletingId(id)}
                      >
                        <span className="text-red-500">Delete</span>
                      </Button>
                    </>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}