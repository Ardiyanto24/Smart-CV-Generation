import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Next.js Edge Middleware — Route Protection
 *
 * Runs before every matched request to enforce auth rules:
 * - Protected routes: redirect to /login if no valid session
 * - Auth routes: redirect to /dashboard if already logged in
 * - All other routes: public, no session check needed
 */
export async function middleware(request: NextRequest) {
  const response = NextResponse.next({
    request,
  });

  // Create Supabase client that reads cookies from the incoming request
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Get current session — does not throw, returns null if no session
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const { pathname } = request.nextUrl;

  // ── Protected routes ────────────────────────────────────────────────────────
  // Redirect to /login if user has no valid session
  const isProtectedRoute =
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/profile") ||
    pathname.startsWith("/apply");

  if (isProtectedRoute && !session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // ── Auth routes ─────────────────────────────────────────────────────────────
  // Redirect to /dashboard if user is already logged in
  const isAuthRoute =
    pathname.startsWith("/login") || pathname.startsWith("/register");

  if (isAuthRoute && session) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return response;
}

// ── Matcher config ────────────────────────────────────────────────────────────
// Only run middleware on routes that need session checking.
// Excludes: static files, Next.js internals, favicon
export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};