// cv-agent/frontend/components/ui/empty-state.tsx

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-lg",
        "border border-dashed border-gray-300 bg-gray-50 px-8 py-16 text-center",
        className
      )}
    >
      <div className="flex flex-col gap-1.5">
        <p className="text-sm font-semibold text-gray-700">{title}</p>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}