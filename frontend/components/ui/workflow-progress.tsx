// cv-agent/frontend/components/ui/workflow-progress.tsx

"use client";

import { useWorkflowStream } from "@/lib/use-workflow-stream";
import { Spinner } from "./spinner";
import { cn } from "@/lib/utils";

// ── Node definitions ──────────────────────────────────────────────────────────
// Urutan node sesuai dengan alur workflow di system_architecture_guide Section 6
const WORKFLOW_NODES = [
  { key: "parse_jd_jr",      label: "Parse Job Description" },
  { key: "analyze_gap",      label: "Analyze Gap" },
  { key: "score_gap",        label: "Score Gap" },
  { key: "plan_strategy",    label: "Plan Strategy" },
  { key: "select_content",   label: "Select Content" },
  { key: "generate_content", label: "Generate CV Content" },
  { key: "qc_evaluate",      label: "Quality Check" },
  { key: "revise_content",   label: "Revise Content" },
  { key: "render_document",  label: "Render Document" },
] as const;

type NodeKey = (typeof WORKFLOW_NODES)[number]["key"];

// ── Status messages ───────────────────────────────────────────────────────────
const NODE_MESSAGES: Record<string, string> = {
  parse_jd_jr:      "Analyzing job description and requirements...",
  analyze_gap:      "Comparing your profile against the job requirements...",
  score_gap:        "Calculating your fit score...",
  plan_strategy:    "Building your CV strategy...",
  select_content:   "Selecting the most relevant experiences...",
  generate_content: "Writing your CV content...",
  qc_evaluate:      "Running quality checks...",
  revise_content:   "Refining sections based on quality feedback...",
  render_document:  "Rendering your CV document...",
};

function getStatusMessage(node: string | null): string {
  if (!node) return "Starting workflow...";
  return NODE_MESSAGES[node] ?? "Processing...";
}

// ── Node state derivation ─────────────────────────────────────────────────────
// Tentukan apakah sebuah node sudah done, active, atau pending
// berdasarkan posisi currentNode di urutan WORKFLOW_NODES
function getNodeState(
  nodeKey: string,
  currentNode: string | null
): "done" | "active" | "pending" {
  if (!currentNode) return "pending";

  const nodeIndex    = WORKFLOW_NODES.findIndex((n) => n.key === nodeKey);
  const currentIndex = WORKFLOW_NODES.findIndex((n) => n.key === currentNode);

  if (nodeIndex < currentIndex) return "done";
  if (nodeIndex === currentIndex) return "active";
  return "pending";
}

// ── Props ─────────────────────────────────────────────────────────────────────
interface WorkflowProgressProps {
  applicationId: string;
}

// ── Component ─────────────────────────────────────────────────────────────────
export function WorkflowProgress({ applicationId }: WorkflowProgressProps) {
  const { currentNode, isStreaming, error } = useWorkflowStream(applicationId);

  return (
    <div className="flex flex-col items-center gap-8 py-12">
      {/* Status message + spinner */}
      <div className="flex flex-col items-center gap-3">
        <Spinner size="lg" />
        <p className="text-sm font-medium text-gray-700">
          {getStatusMessage(currentNode)}
        </p>
        {error && (
          <p className="text-xs text-amber-600">{error}</p>
        )}
        {!isStreaming && !error && !currentNode && (
          <p className="text-xs text-gray-400">Connecting...</p>
        )}
      </div>

      {/* Vertical step indicator */}
      <div className="flex flex-col gap-0 w-full max-w-sm">
        {WORKFLOW_NODES.map((node, index) => {
          const state = getNodeState(node.key, currentNode);
          const isLast = index === WORKFLOW_NODES.length - 1;

          return (
            <div key={node.key} className="flex items-stretch gap-3">
              {/* Left column: circle + connector line */}
              <div className="flex flex-col items-center">
                {/* Node circle */}
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                    state === "done"
                      ? "bg-blue-600 text-white"
                      : state === "active"
                      ? "bg-blue-600 text-white ring-4 ring-blue-100"
                      : "bg-gray-100 text-gray-400"
                  )}
                >
                  {state === "done" ? "✓" : state === "active" ? (
                    <span className="h-2 w-2 rounded-full bg-white" />
                  ) : (
                    <span className="h-2 w-2 rounded-full bg-gray-300" />
                  )}
                </div>

                {/* Connector line — tidak ditampilkan untuk node terakhir */}
                {!isLast && (
                  <div
                    className={cn(
                      "w-px flex-1 my-1 transition-colors",
                      state === "done" ? "bg-blue-300" : "bg-gray-200"
                    )}
                  />
                )}
              </div>

              {/* Right column: node label */}
              <div className={cn("pb-4 pt-0.5", isLast && "pb-0")}>
                <p
                  className={cn(
                    "text-sm transition-colors",
                    state === "active"
                      ? "font-semibold text-blue-600"
                      : state === "done"
                      ? "font-medium text-gray-700"
                      : "text-gray-400"
                  )}
                >
                  {node.label}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}