// cv-agent/frontend/components/ui/badge.tsx

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Variant = "success" | "warning" | "error" | "neutral" | "info";

interface BadgeProps {
  variant: Variant;
  children: ReactNode;
  className?: string;
}

const variantStyles: Record<Variant, string> = {
  success: "bg-green-100 text-green-700 border border-green-200",
  warning: "bg-yellow-100 text-yellow-700 border border-yellow-200",
  error:   "bg-red-100 text-red-700 border border-red-200",
  neutral: "bg-gray-100 text-gray-600 border border-gray-200",
  info:    "bg-blue-100 text-blue-700 border border-blue-200",
};

export function Badge({ variant, children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}