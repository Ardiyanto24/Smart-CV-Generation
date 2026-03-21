import { createBrowserClient } from "@supabase/ssr";

/**
 * Creates a Supabase browser client for use in Client Components.
 *
 * Called as a factory function (not a singleton) because each
 * Client Component needs its own client instance to correctly
 * handle session state in the browser.
 *
 * Usage:
 *   const supabase = createClient()
 *   const { data } = await supabase.from("table").select()
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}