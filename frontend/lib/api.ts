/**
 * Generic wrapper for all HTTP calls to the FastAPI backend.
 *
 * Centralizes:
 * - Base URL construction
 * - Default headers (Content-Type, credentials)
 * - Error handling (extracts FastAPI's "detail" field)
 *
 * Usage:
 *   const data = await apiFetch<User>("/auth/me")
 *   const result = await apiFetch<Application>("/applications", {
 *     method: "POST",
 *     body: JSON.stringify({ company_name: "Acme", position: "Engineer" }),
 *   })
 */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  const url = `${baseUrl}${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    // Always send cookies (JWT session) with every request
    credentials: "include",
  });

  if (!response.ok) {
    // FastAPI returns errors in the shape: { "detail": "message" }
    const errorBody = await response.json().catch(() => ({}));
    const message =
      errorBody.detail ?? `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  // Handle 204 No Content (e.g., DELETE responses)
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}