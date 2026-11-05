/**
 * Mock API for the clickable prototype. No backend, sign-in or keys.
 * State lives in this browser's localStorage, so each tester gets their own profile and history.
 */
import { fmtMoney, hostOf, joinList, toCm } from "@/lib/format";
import { DEFAULT_SHOP, shopForUrl } from "@/lib/shops";
import {
  ApiError,
  type ApiClient,
  type Brand,
  type Catalog,
  type CheckResult,
  type CheckSummary,
  type CheckView,
  type Feedback,
  type Profile,
  type ProfileIn,
  type ProgressEvent,
  type OptionOut,
  type ProfileMeasurement,
  type StepId,
} from "../types";
import catalog from "./catalog.json";
import { buildDemoCheck, demoProductForUrl, type DemoProduct } from "./demo";
import { runScenario, type Scenario } from "./engine";
import {
  BRANDS,
  KNOWN_WITHOUT_SAMPLE,
  MOCK_STORES,
  SCENARIOS,
} from "./scenarios";

const KEYS = {
  profile: "bl:v2:profile",
  oldProfile: "bl:profile",
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
  result: CheckView | null;
  shopId?: string;
  demoProfile?: Profile;
};

type StepPlan = {
  result: CheckView | null;
  details: Record<StepId, string>;
  failure?: { atStep: StepId; message: string };
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

function displayValue(
  measurements: ProfileMeasurement[],
  dimension: ProfileMeasurement["dimension"],
): number | null {
  return measurements.find((m) => m.dimension === dimension)?.value ?? null;
}

/** A profile saved before fit modes existed means Personal Fit with body measurements. */
function fromOldProfile(old: Record<string, unknown>): Profile {
  const measurements = (["waist", "inseam", "hips"] as const).flatMap(
    (dimension): ProfileMeasurement[] =>
      typeof old[dimension] === "number"
        ? [{ dimension, value: old[dimension], basis: "body", note: null }]
        : [],
  );
  return {
    ...(old as unknown as Profile),
    fit_mode: "personal_fit",
    size_system: null,
    quick_sizes: {},
    measurements,
  };
}

function isProfile(value: unknown): value is Profile {
  const p = value as Partial<Profile> | null;
  return (
    !!p &&
    (p.unit === "in" || p.unit === "cm") &&
    (p.fit_mode === "quick_fit" || p.fit_mode === "personal_fit") &&
    typeof p.quick_sizes === "object" &&
    Array.isArray(p.measurements) &&
    Array.isArray(p.brands)
  );
}

function storedProfile(): Profile | null {
  const current = read<unknown>(KEYS.profile, null);
  if (current !== null) return isProfile(current) ? current : null;
  const old = read<Record<string, unknown> | null>(KEYS.oldProfile, null);
  if (!old) return null;
  const converted = fromOldProfile(old);
  return isProfile(converted) ? converted : null;
}

/** The older {unit, waist, inseam, hips} body, as the backend reads it. */
function oldBodyMeasurements(p: ProfileIn): ProfileMeasurement[] | undefined {
  if (p.fit_mode) {
    return p.measurements?.map((m) => ({
      dimension: m.dimension,
      value: m.value,
      basis: m.basis ?? "body",
      note: m.note ?? null,
    }));
  }
  return fromOldProfile({ waist: p.waist, inseam: p.inseam, hips: p.hips })
    .measurements;
}

function checkMeasurementsCm(profile: Profile): Record<string, number> {
  if (profile.fit_mode !== "personal_fit") return {};
  return Object.fromEntries(
    profile.measurements
      .filter((m) => m.basis === "body")
      .map((m) => [m.dimension, toCm(m.value, profile.unit)]),
  );
}

function hasFitData(profile: Profile | null): profile is Profile {
  return (
    !!profile &&
    (Object.keys(profile.quick_sizes).length > 0 ||
      profile.measurements.length > 0)
  );
}

/** What a link points at. A link the prototype has no data for is rejected here. */
function checkTarget(url: string): {
  store?: string;
  demoProduct?: DemoProduct;
} {
  const host = hostOf(url);
  if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(host))
    throw new ApiError(422, "That doesn't look like a product link.");
  const matches = (d: string) => host === d || host.endsWith(`.${d}`);
  const demoProduct = demoProductForUrl(url);
  const store = Object.keys(MOCK_STORES).find(matches);
  if (demoProduct || store) return { store, demoProduct };
  if (shopForUrl(url)?.id === DEFAULT_SHOP.id)
    throw new ApiError(
      422,
      "This page has no sample data in the prototype. Try one of the sample products.",
    );
  if (KNOWN_WITHOUT_SAMPLE.some(matches))
    throw new ApiError(
      422,
      "This store has no sample data in the prototype yet. Try one of the sample links.",
    );
  throw new ApiError(422, "We don't support this store yet.");
}

const NEW_PROFILE = {
  unit: "cm",
  size_system: null,
  quick_sizes: {},
  measurements: [],
  brands: [],
} satisfies Partial<Profile>;

function assertUsable(
  mode: Profile["fit_mode"],
  quickSizes: Profile["quick_sizes"],
  measurements: ProfileMeasurement[],
): void {
  if (mode === "quick_fit" && !Object.keys(quickSizes).length)
    throw new ApiError(422, "Pick a size for at least one category.");
  if (mode === "personal_fit" && !measurements.length)
    throw new ApiError(422, "Add at least one measurement.");
}

function mergedProfile(p: ProfileIn, stored: Profile | null): Profile {
  const base = stored ?? NEW_PROFILE;
  const mode = p.fit_mode ?? "personal_fit";
  const measurements = oldBodyMeasurements(p) ?? base.measurements;
  const quick_sizes = p.quick_sizes ?? base.quick_sizes;
  assertUsable(mode, quick_sizes, measurements);
  return {
    unit: p.unit ?? base.unit,
    fit_mode: mode,
    size_system: p.size_system ?? base.size_system,
    quick_sizes,
    measurements,
    waist: displayValue(measurements, "waist"),
    inseam: displayValue(measurements, "inseam"),
    hips: displayValue(measurements, "hips"),
    brands: brandsFor(p, base.brands),
    updated_at: new Date().toISOString(),
  };
}

/** Like the backend: the older body always replaced brands; the current one keeps them if left out. */
function brandsFor(p: ProfileIn, saved: Brand[]): Brand[] {
  const ids = p.fit_mode ? p.brand_ids : (p.brand_ids ?? []);
  if (!ids) return saved;
  const wanted = new Set(ids);
  return BRANDS.filter((b) => wanted.has(b.id));
}

function priceOf(result: CheckView): {
  total_cents: number | null;
  currency: string | null;
} {
  if (result.demo)
    return {
      total_cents: result.demo.price_cents,
      currency: result.demo.currency,
    };
  const first = result.options[0];
  return {
    total_cents: first?.total_cents ?? null,
    currency: first?.price_check.currency ?? null,
  };
}

/** A failing sample (e.g. "store blocks us") never reaches the verdict, like the real pipeline. */
function scenarioPlan(check: StoredCheck): StepPlan {
  const scenario = SCENARIOS[check.scenario];
  const result = scenario.failure
    ? null
    : runScenario(scenario, check.profile.cm, check.profile.unit, {
        id: check.id,
        url: check.url,
        createdAt: check.createdAt,
      });
  return {
    result,
    failure: scenario.failure,
    details: scenarioDetails(scenario, result?.options ?? []),
  };
}

function scenarioDetails(
  scenario: Scenario,
  options: OptionOut[],
): Record<StepId, string> {
  const best = options.length
    ? Math.min(...options.map((o) => o.total_cents))
    : 0;
  const n = options.length;
  const compared =
    options[0]?.fit_check.rows
      .filter((r) => r.garment_cm != null)
      .map((r) => r.dimension) ?? [];
  return {
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
}

/** A demo product's result, with no verdict: fit, EUR price and the demo chart. */
function demoPlan(
  check: StoredCheck,
  product: DemoProduct,
  profile: Profile,
): StepPlan {
  const demo = buildDemoCheck(product, profile);
  return {
    details: {
      product: `${product.name}, ${demo.shop_name} (demo shop)`,
      prices: `${fmtMoney(demo.price_cents, demo.currency)} before shipping`,
      fit: "Compared with the demo size chart",
      seller: "Not enough data for a demo shop",
    },
    result: {
      id: check.id,
      status: "done",
      current_step: null,
      input_url: check.url,
      created_at: check.createdAt,
      completed_at: new Date().toISOString(),
      error: null,
      unit: profile.unit,
      product: {
        name: product.name,
        brand: null,
        category: product.product_type,
        attributes: {},
        image_url: null,
      },
      selected_size: demo.fit.size_label,
      verdict: null,
      headline: null,
      explanation: null,
      why_not: null,
      options: [],
      demo,
    },
  };
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
    return storedProfile();
  }

  async getMeasurements(): Promise<Catalog> {
    return catalog as Catalog;
  }

  async saveProfile(p: ProfileIn): Promise<void> {
    await delay(250);
    write(KEYS.profile, mergedProfile(p, storedProfile()));
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

  private startRun(check: StoredCheck): { id: string } {
    this.saveCheck(check);
    this.runs.set(check.id, {
      events: [],
      listeners: new Set(),
      cancelled: false,
    });
    void this.execute(check.id);
    return { id: check.id };
  }

  async createCheck(
    url: string,
    options: { shopId?: string } = {},
  ): Promise<{ id: string }> {
    await delay(200);
    const target = checkTarget(url);
    const profile = storedProfile();
    if (!hasFitData(profile)) {
      throw new ApiError(409, "Save your measurements first.");
    }
    return this.startRun({
      id: crypto.randomUUID(),
      url,
      scenario: target.store ? MOCK_STORES[target.store] : "",
      createdAt: new Date().toISOString(),
      status: "running",
      error: null,
      profile: { unit: profile.unit, cm: checkMeasurementsCm(profile) },
      result: null,
      shopId: options.shopId ?? shopForUrl(url)?.id,
      demoProfile: target.demoProduct ? profile : undefined,
    });
  }

  private emit(id: string, event: ProgressEvent): void {
    const run = this.runs.get(id);
    if (!run) return;
    run.events.push(event);
    for (const listener of run.listeners) listener(event);
  }

  private async execute(id: string): Promise<void> {
    try {
      await this.runSteps(id);
    } catch (err) {
      // Never leave the loading dialog spinning: report any unexpected error as a failed check.
      console.error("Mock check failed", err);
      const message = "Something went wrong on our side. Please try again.";
      const stored = this.checks()[id];
      if (stored)
        this.saveCheck({ ...stored, status: "failed", error: message });
      this.emit(id, { type: "failed", message });
    }
  }

  private async runSteps(id: string): Promise<void> {
    const check = this.checks()[id];
    const run = this.runs.get(id)!;
    const demoProduct = demoProductForUrl(check.url);
    const plan =
      check.demoProfile && demoProduct
        ? demoPlan(check, demoProduct, check.demoProfile)
        : scenarioPlan(check);

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
      if (plan.failure?.atStep === step) {
        this.saveCheck({
          ...this.checks()[id],
          status: "failed",
          error: plan.failure.message,
        });
        this.emit(id, { type: "failed", message: plan.failure.message });
        return;
      }
      this.emit(id, {
        type: "step",
        step,
        status: "done",
        index: i + 1,
        total: 4,
        label: STEP_LABEL[step],
        detail: plan.details[step],
      });
    }
    this.saveCheck({ ...this.checks()[id], status: "done", result: plan.result });
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

  async getCheck(id: string): Promise<CheckView | null> {
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
        ...priceOf(c.result!),
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
