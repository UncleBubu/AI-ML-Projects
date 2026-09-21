import { supabase } from "../supabaseClient";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:4000";

// Every backend call goes through here: attaches the logged-in user's JWT (the
// backend verifies it) and turns error responses into thrown Errors with the
// server's message, so components just try/catch.
export async function authorizedFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error("You are logged out. Please log in again.");

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...options.headers,
    },
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error ?? `Request failed: ${response.status}`);
  return body as T;
}
