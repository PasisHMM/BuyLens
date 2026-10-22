/**
 * Live API client: the FastAPI backend, authenticated with a Supabase (anonymous) session.
 * Progress streams over SSE with the bearer token (fetch-based; EventSource can't send headers).
 */
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import {
  ApiError,
  type ApiClient,
  type Brand,
  type CheckResult,
  type CheckSummary,
  type Feedback,
  type Profile,
  type ProfileIn,
  type ProgressEvent,
} from "./types";

type Config = { apiUrl: string; supabaseUrl: string; supabaseKey: string };

export class LiveApiClient implements ApiClient {
  mode = "live" as const;
  private supabase: SupabaseClient;

  constructor(private config: Config) {
    this.supabase = createClient(config.supabaseUrl, config.supabaseKey);
  }

  private async token(): Promise<string> {
    const { data } = await this.supabase.auth.getSession();
    if (data.session) return data.session.access_token;
    const { data: signedIn, error } =
      await this.supabase.auth.signInAnonymously();
    if (error || !signedIn.session)
      throw new ApiError(
        401,
        "We couldn't start a session. Please reload the page.",
      );
    return signedIn.session.access_token;
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
    { auth = true } = {},
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (auth) headers.set("Authorization", `Bearer ${await this.token()}`);
    if (init.body) headers.set("Content-Type", "application/json");
    const resp = await fetch(`${this.config.apiUrl}${path}`, {
      ...init,
      headers,
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => null);
      const detail =
        typeof body?.detail === "string"
          ? body.detail
          : "Something went wrong. Please try again.";
      throw new ApiError(resp.status, detail);
    }
    return (resp.status === 204 ? undefined : await resp.json()) as T;
  }

  async getProfile(): Promise<Profile | null> {
    try {
      return await this.request<Profile>("/v1/profile");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  }

  saveProfile(profile: ProfileIn): Promise<void> {
    return this.request("/v1/profile", {
      method: "PUT",
      body: JSON.stringify(profile),
    });
  }

  searchBrands(query?: string, limit = 20): Promise<Brand[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (query?.trim()) params.set("q", query.trim());
    return this.request(`/v1/brands?${params}`, {}, { auth: false });
  }

  createCheck(url: string): Promise<{ id: string }> {
    return this.request("/v1/checks", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
  }

  subscribe(id: string, onEvent: (event: ProgressEvent) => void): () => void {
    const controller = new AbortController();
    void (async () => {
      const token = await this.token();
      await fetchEventSource(`${this.config.apiUrl}/v1/checks/${id}/events`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
        openWhenHidden: true,
        onmessage(msg) {
          if (!msg.data) return;
          onEvent({
            ...(JSON.parse(msg.data) as ProgressEvent),
            type: msg.event as ProgressEvent["type"],
          });
        },
        onerror(err) {
          onEvent({
            type: "failed",
            message: "Lost connection to the check. Please try again.",
          });
          throw err; // stop retrying
        },
      });
    })();
    return () => controller.abort();
  }

  cancelCheck(id: string): Promise<void> {
    return this.request(`/v1/checks/${id}`, { method: "DELETE" });
  }

  async getCheck(id: string): Promise<CheckResult | null> {
    try {
      return await this.request<CheckResult>(`/v1/checks/${id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  }

  recentChecks(limit = 5): Promise<CheckSummary[]> {
    return this.request(`/v1/checks?limit=${limit}`);
  }

  async getFeedback(): Promise<Feedback | null> {
    return null; // backend endpoint arrives in Phase 4
  }

  async submitFeedback(): Promise<void> {
    throw new ApiError(
      501,
      "Saving feedback arrives with the next backend update.",
    );
  }
}
