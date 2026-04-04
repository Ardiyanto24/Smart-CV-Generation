// cv-agent/frontend/app/(app)/layout.tsx

import { redirect } from "next/navigation";
import { createServerClient } from "@/lib/supabase-server";
import { AuthProvider } from "@/lib/auth-context";
import { AppShell } from "@/components/ui/app-shell";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Double-guard: baca session server-side, tidak bergantung pada middleware saja
  const supabase = await createServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}