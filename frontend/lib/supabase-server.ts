import { createServerClient as createSupabaseServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Creates a Supabase client for use in Server Components and Route Handlers.
 *
 * Distinct from the browser client (lib/supabase.ts) — this client reads
 * cookies via Next.js `cookies()` API instead of browser document.cookie.
 *
 * Must be a factory function (not singleton) because each server request
 * has its own cookie store belonging to a different user.
 *
 * Usage in Server Components:
 *   const supabase = createServerClient()
 *   const { data: { session } } = await supabase.auth.getSession()
 */
export async function createServerClient() {
  const cookieStore = await cookies();

  return createSupabaseServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options);
            });
          } catch {
            // setAll called from Server Component — cookies can only be
            // set in Route Handlers or Server Actions, not Server Components.
            // This is safe to ignore for read-only usage.
          }
        },
      },
    }
  );
}