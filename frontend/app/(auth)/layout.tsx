import type { ReactNode } from "react";

/**
 * Auth Layout — wraps /login and /register pages.
 *
 * Intentionally isolated from the main app shell:
 * - No navigation header
 * - Centered form layout
 * - Distinct neutral background
 *
 * Uses Next.js Route Group (auth) so URLs remain /login and /register,
 * not /auth/login and /auth/register.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      {children}
    </div>
  );
}