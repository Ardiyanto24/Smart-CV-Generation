// cv-agent/frontend/components/ui/error-boundary.tsx

"use client";

import { Component, ErrorInfo, ReactNode } from "react";
import { Button } from "./button";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Log ke console untuk debugging lokal
    // Di production, ini bisa dikirim ke Sentry
    console.error("[ErrorBoundary] Caught error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-4 rounded-lg border border-red-200 bg-red-50 p-8 text-center">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-semibold text-red-700">
              Something went wrong
            </p>
            <p className="text-xs text-red-500">
              {this.state.error?.message ?? "An unexpected error occurred."}
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => window.location.reload()}
          >
            Try again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}

// HOC untuk membungkus komponen dengan ErrorBoundary secara deklaratif
export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ReactNode
) {
  const displayName =
    WrappedComponent.displayName ?? WrappedComponent.name ?? "Component";

  function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    );
  }

  WithErrorBoundary.displayName = `withErrorBoundary(${displayName})`;
  return WithErrorBoundary;
}