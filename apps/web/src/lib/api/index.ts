import { LiveApiClient } from "./live";
import { MockApiClient } from "./mock/client";
import type { ApiClient } from "./types";

export * from "./types";

/** NEXT_PUBLIC_API_MODE=mock (default) uses built-in sample data; =live talks to the FastAPI backend. */
export function createApiClient(): ApiClient {
  if (process.env.NEXT_PUBLIC_API_MODE === "live") {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    if (!apiUrl || !supabaseUrl || !supabaseKey) {
      throw new Error(
        "Live mode needs NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY.",
      );
    }
    return new LiveApiClient({ apiUrl, supabaseUrl, supabaseKey });
  }
  return new MockApiClient();
}
