// cv-agent/frontend/components/ui/app-shell.tsx

"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "./button";
import { Spinner } from "./spinner";

const navLinks = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/profile", label: "Profile" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // Tetap redirect meskipun request gagal — lebih aman daripada
      // membiarkan user terjebak di halaman authenticated
    } finally {
      router.push("/login");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          {/* Logo / App Name */}
          <Link
            href="/dashboard"
            className="text-base font-semibold text-gray-900 hover:text-blue-600 transition-colors"
          >
            CV Agent
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive =
                pathname === link.href ||
                pathname.startsWith(link.href + "/");
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-blue-50 text-blue-600"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>

          {/* User Info + Logout */}
          <div className="flex items-center gap-3">
            {loading ? (
              <Spinner size="sm" />
            ) : (
              <span className="text-sm text-gray-600">
                {user?.email ?? ""}
              </span>
            )}
            <Button
              variant="secondary"
              size="sm"
              loading={loggingOut}
              onClick={handleLogout}
            >
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Page Content */}
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}