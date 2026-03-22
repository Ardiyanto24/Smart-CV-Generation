"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { User } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase";

// ── Context Type ──────────────────────────────────────────────────────────────
interface AuthContextValue {
  user: User | null;
  loading: boolean;
}

// ── Context ───────────────────────────────────────────────────────────────────
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ── Provider ──────────────────────────────────────────────────────────────────
/**
 * AuthProvider — wraps the app and provides current user state to all
 * Client Components via React context.
 *
 * Place this at the root layout so all pages have access to auth state.
 *
 * Usage:
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = createClient();

    // Step 1 — Get existing session on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Step 2 — Subscribe to auth state changes
    // Keeps user state in sync when session changes in any tab
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Cleanup subscription on unmount
    return () => {
      subscription.unsubscribe();
    };
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────
/**
 * useAuth — returns the current auth context value.
 *
 * Must be used inside AuthProvider — throws if used outside.
 *
 * Usage:
 *   const { user, loading } = useAuth()
 *   if (loading) return <Spinner />
 *   if (!user) return <LoginPrompt />
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}