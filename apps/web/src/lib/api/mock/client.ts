/**
 * Mock API for the clickable prototype. No backend, sign-in or keys.
 * State lives in this browser's localStorage, so each tester gets their own profile and history.
 */
import { fmtMoney, hostOf, joinList, toCm } from "@/lib/format";
import {
  ApiError,
  type ApiClient,
  type CheckResult,
  type CheckSummary,
  type Feedback,
  type Profile,
  type ProfileIn,
  type ProgressEvent,
  type StepId,
} from "../types";
import { runScenario } from "./engine";
import {
  BRANDS,
  KNOWN_WITHOUT_SAMPLE,
  MOCK_STORES,
  SCENARIOS,
} from "./scenarios";

const KEYS = {
  profile: "bl:profile",
  checks: "bl:checks",
  feedback: "bl:feedback",
} as const;
const STEPS: StepId[] = ["product", "prices", "fit", "seller"];
const STEP_LABEL: Record<StepId, string> = {
  product: "Finding product details",
  prices: "Comparing prices",
  fit: "Comparing your measurements",
  seller: "Reviewing seller risk",
};
const STEP_MS: Record<StepId, number> = {
  product: 1300,
  prices: 1600,
  fit: 1100,
  seller: 1400,
};
const MAX_STORED_CHECKS = 20;

type StoredCheck = {
  id: string;
  url: string;
  scenario: string;
  createdAt: string;
  status: CheckResult["status"];
  error: string | null;
  profile: { unit: "in" | "cm"; cm: Record<string, number> };
  result: CheckResult | null;
};

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Private mode or storage full: the prototype still works for this page view.
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** In-flight runs (this tab only): replayable events + subscribers + cancel flag. */
type Run = {
  events: ProgressEvent[];
  listeners: Set<(e: ProgressEvent) => void>;
  cancelled: boolean;
};

export class MockApiClient implements ApiClient {
  mode = "mock" as const;
  private runs = new Map<string, Run>();

  async getProfile(): Promise<Profile | null> {
    await delay(80);
    return read<Profile | null>(KEYS.profile, null);
  }

  async saveProfile(p: ProfileIn): Promise<void> {
    await delay(250);
    const ids = new Set(p.brand_ids ?? []);
    const profile: Profile = {
      unit: p.unit,
      waist: p.waist,
      inseam: p.inseam,
      hips: p.hips ?? null,
      brands: BRANDS.filter((b) => ids.has(b.id)),
      updated_at: new Date().toISOString(),
    };
    write(KEYS.profile, profile);
  }

  async searchBrands(query?: string, limit = 20) {
    const q = query?.trim().toLowerCase();
    return BRANDS.filter((b) => !q || b.name.toLowerCase().includes(q)).slice(
      0,
      limit,
    );
  }

  private checks(): Record<string, StoredCheck> {
    return read<Record<string, StoredCheck>>(KEYS.checks, {});
  }

  private saveCheck(check: StoredCheck): void {
    const all = { ...this.checks(), [check.id]: check };
    const ids = Object.values(all)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .map((c) => c.id);
    for (const old of ids.slice(MAX_STORED_CHECKS)) delete all[old];
    write(KEYS.checks, all);
  }

  async createCheck(url: string): Promise<{ id: string }> {
    await delay(200);
    const host = hostOf(url);
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(host))
      throw new ApiError(422, "That doesn't look like a product link.");
    const store = Object.keys(MOCK_STORES).find(
      (d) => host === d || host.endsWith(`.${d}`),
    );
    if (!store) {
      if (
        KNOWN_WITHOUT_SAMPLE.some((d) => host === d || host.endsWith(`.${d}`))
      )
        throw new ApiError(
          422,
          "This store has no sample data in the prototype yet. Try one of the sample links.",
        );
      throw new ApiError(422, "We don't support this store yet.");
    }
    const profile = read<Profile | null>(KEYS.profile, null);
    if (!profile || profile.waist == null || profile.inseam == null) {
      throw new ApiError(409, "Save your measurements first.");
    }
    const cm: Record<string, number> = {
      waist: toCm(profile.waist, profile.unit),
      inseam: toCm(profile.inseam, profile.unit),
    };
    if (profile.hips != null) cm.hips = toCm(profile.hips, profile.unit);

    const id = crypto.randomUUID();
    this.saveCheck({
      id,
      url,
      scenario: MOCK_STORES[store],
      createdAt: new Date().toISOString(),
      status: "running",
      error: null,
      profile: { unit: profile.unit, cm },
      result: null,
    });
    this.runs.set(id, { events: [], listeners: new Set(), cancelled: false });
    void this.execute(id);
    return { id };
  }

  private emit(id: string, event: ProgressEvent): void {
    const run = this.runs.get(id);
    if (!run) return;
    run.events.push(event);
    for (const listener of run.listeners) listener(event);
  }

  private async execute(id: string): Promise<void> {
    const check = this.checks()[id];
    const scenario = SCENARIOS[check.scenario];
    const run = this.runs.get(id)!;
    const result = runScenario(scenario, check.profile.cm, check.profile.unit, {
      id,
      url: check.url,
      createdAt: check.createdAt,
    });
    const best = result.options.length
      ? Math.min(...result.options.map((o) => o.total_cents))
      : 0;
    const n = result.options.length;
    const compared =
      result.options[0]?.fit_check.rows
        .filter((r) => r.garment_cm != null)
        .map((r) => r.dimension) ?? [];
    const details: Record<StepId, string> = {
      product: [
        scenario.product.name,
        String(scenario.product.attributes.wash ?? "").toLowerCase(),
      ]
        .filter(Boolean)
        .join(", "),
      prices: `${fmtMoney(best)} total across ${n} seller${n === 1 ? "" : "s"}`,
      fit: compared.length
        ? `${joinList(compared).replace(/^./, (c) => c.toUpperCase())} compared`
        : "No comparable size data",
      seller: "Reviews and return policy checked",
    };

    for (const [i, step] of STEPS.entries()) {
      if (run.cancelled) return;
      this.emit(id, {
        type: "step",
        step,
        status: "active",
        index: i + 1,
        total: 4,
        label: STEP_LABEL[step],
      });
      await delay(STEP_MS[step]);
      if (run.cancelled) return;
      if (scenario.failure?.atStep === step) {
        this.saveCheck({
          ...this.checks()[id],
          status: "failed",
          error: scenario.failure.message,
        });
        this.emit(id, { type: "failed", message: scenario.failure.message });
        return;
      }
      this.emit(id, {
        type: "step",
        step,
        status: "done",
        index: i + 1,
        total: 4,
        label: STEP_LABEL[step],
        detail: details[step],
      });
    }
    this.saveCheck({ ...this.checks()[id], status: "done", result });
    this.emit(id, { type: "complete" });
  }

  subscribe(id: string, onEvent: (event: ProgressEvent) => void): () => void {
    const run = this.runs.get(id);
    if (!run) {
      // Not running in this tab (finished earlier, or the page was reloaded mid-run).
      const stored = this.checks()[id];
      const status = stored?.status;
      setTimeout(() => {
        if (status === "done") onEvent({ type: "complete" });
        else if (status === "cancelled")
          onEvent({ type: "cancelled", message: "Check cancelled." });
        else
          onEvent({
            type: "failed",
            message:
              stored?.error ?? "This check was interrupted. Please try again.",
          });
      }, 0);
      return () => {};
    }
    for (const event of run.events) setTimeout(() => onEvent(event), 0);
    run.listeners.add(onEvent);
    return () => run.listeners.delete(onEvent);
  }

  async cancelCheck(id: string): Promise<void> {
    const run = this.runs.get(id);
    const stored = this.checks()[id];
    if (!stored || !["queued", "running"].includes(stored.status))
      throw new ApiError(409, "This check has already finished.");
    if (run) run.cancelled = true;
    this.saveCheck({ ...stored, status: "cancelled" });
    this.emit(id, { type: "cancelled", message: "Check cancelled." });
  }

  async getCheck(id: string): Promise<CheckResult | null> {
    await delay(120);
    const stored = this.checks()[id];
    if (!stored) return null;
    if (stored.result) return stored.result;
    return {
      id,
      status: stored.status,
      current_step: null,
      input_url: stored.url,
      created_at: stored.createdAt,
      completed_at: null,
      error: stored.error,
      unit: stored.profile.unit,
      product: null,
      selected_size: null,
      verdict: null,
      headline: null,
      explanation: null,
      why_not: null,
      options: [],
    };
  }

  async recentChecks(limit = 5): Promise<CheckSummary[]> {
    return Object.values(this.checks())
      .filter((c) => c.status === "done" && c.result)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, limit)
      .map((c) => ({
        id: c.id,
        status: c.status,
        created_at: c.createdAt,
        product_name: c.result!.product?.name ?? null,
        image_url: c.result!.product?.image_url ?? null,
        verdict: c.result!.verdict,
        selected_size: c.result!.selected_size,
        total_cents: c.result!.options[0]?.total_cents ?? null,
        currency: c.result!.options[0]?.price_check.currency ?? null,
      }));
  }

  async getFeedback(id: string): Promise<Feedback | null> {
    return read<Record<string, Feedback>>(KEYS.feedback, {})[id] ?? null;
  }

  async submitFeedback(id: string, feedback: Feedback): Promise<void> {
    await delay(300);
    write(KEYS.feedback, {
      ...read<Record<string, Feedback>>(KEYS.feedback, {}),
      [id]: feedback,
    });
  }
}
