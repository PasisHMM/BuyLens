import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ProfileIn } from "../types";
import { MockApiClient } from "./client";
import { BRANDS } from "./brands";

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

function useStorage(initial: Record<string, string> = {}) {
  vi.stubGlobal("window", { localStorage: memoryStorage(initial) });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function settle<T>(promise: Promise<T>): Promise<T> {
  await vi.runAllTimersAsync();
  return promise;
}

describe("MockApiClient profile storage", () => {
  it("has no profile on first visit", async () => {
    useStorage();
    expect(await settle(new MockApiClient().getProfile())).toBeNull();
  });

  it("treats corrupted stored data as no profile instead of crashing", async () => {
    useStorage({ "bl:profile": "{not json" });
    expect(await settle(new MockApiClient().getProfile())).toBeNull();
  });

  it("returns a saved profile with the selected brands", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(
      api.saveProfile({ unit: "in", waist: 26, inseam: 30, brand_ids: [] }),
    );
    expect(await settle(api.getProfile())).toMatchObject({
      unit: "in",
      waist: 26,
      inseam: 30,
      hips: null,
      brands: [],
    });
  });
});

/** Attach the rejection check before advancing timers, so the error is never unhandled. */
async function expectRejection(promise: Promise<unknown>, error: object) {
  const assertion = expect(promise).rejects.toMatchObject(error);
  await vi.runAllTimersAsync();
  await assertion;
}

describe("MockApiClient createCheck", () => {
  it("rejects a link that is not a URL", async () => {
    useStorage();
    await expectRejection(new MockApiClient().createCheck("hello"), {
      status: 422,
    });
  });

  it("asks for measurements before the first check", async () => {
    useStorage();
    await expectRejection(
      new MockApiClient().createCheck(DEMO_SWEATER),
      { status: 409, message: "Save your measurements first." },
    );
  });

  it("starts a Merchandizable check for a Quick Fit profile with one size", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(
      api.saveProfile({ fit_mode: "quick_fit", quick_sizes: { bottoms: "S" } }),
    );
    const { id } = await settle(
      api.createCheck(DEMO_TROUSERS, { shopId: "merchandizable" }),
    );
    await vi.runAllTimersAsync();
    const result = await settle(api.getCheck(id));
    expect(result?.status).toBe("done");
    expect(result?.demo?.shop_name).toBe("Merchandizable");
    expect(result?.matches[0].fit_check.outcome).toBe("match");
    expect(result?.selected_size).toBe("S");
  });

  it("lists a finished demo check with its EUR price and outcome", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(
      api.saveProfile({ fit_mode: "quick_fit", quick_sizes: { tops: "S" } }),
    );
    await settle(api.createCheck(DEMO_SWEATER));
    await vi.runAllTimersAsync();
    expect((await settle(api.recentChecks(1)))[0]).toMatchObject({
      product_name: "Demo Relaxed Sweater",
      total_cents: 4900,
      currency: "EUR",
      fit_outcome: "uncertain",
    });
  });

  it("lists a hidden check as a mismatch, with no price to recommend", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(
      api.saveProfile({ fit_mode: "quick_fit", quick_sizes: { bottoms: "XL" } }),
    );
    await settle(api.createCheck(DEMO_PETITE));
    await vi.runAllTimersAsync();
    expect((await settle(api.recentChecks(1)))[0]).toMatchObject({
      fit_outcome: "mismatch",
      total_cents: null,
      selected_size: null,
    });
  });

  it("runs sample measurements without a saved profile, and saves nothing", async () => {
    useStorage();
    const api = new MockApiClient();
    const { id } = await settle(
      api.createCheck(DEMO_TROUSERS, { sampleId: "inside-size-s" }),
    );
    await vi.runAllTimersAsync();
    const result = await settle(api.getCheck(id));
    expect(result?.fit_mode_used).toBe("personal_fit");
    expect(result?.matches[0].fit_check.size_label).toBe("S");
    expect(await settle(api.getProfile())).toBeNull();
  });

  it("ignores an unknown sample", async () => {
    useStorage();
    await expectRejection(
      new MockApiClient().createCheck(DEMO_TROUSERS, { sampleId: "nope" }),
      { status: 409 },
    );
  });

  it.each([
    ["https://merchandizable.example/p/unknown", "no sample data"],
    ["https://www.levi.com/p/501", "Levi's is coming soon."],
    ["https://elsewhere.test/p/1", "We don't support this store yet."],
  ])("rejects %s", async (url, message) => {
    useStorage();
    await expectRejection(new MockApiClient().createCheck(url), {
      status: 422,
      message: expect.stringContaining(message),
    });
  });

  it("can be cancelled while running, and not afterwards", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(
      api.saveProfile({ fit_mode: "quick_fit", quick_sizes: { tops: "S" } }),
    );
    const started = api.createCheck(DEMO_SWEATER);
    await vi.advanceTimersByTimeAsync(300); // past the request, before the run finishes
    const { id } = await started;
    await api.cancelCheck(id);
    await vi.runAllTimersAsync();
    expect((await settle(api.getCheck(id)))?.status).toBe("cancelled");
    await expectRejection(api.cancelCheck(id), { status: 409 });
  });

  it("streams each step, then completes", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(
      api.saveProfile({ fit_mode: "quick_fit", quick_sizes: { tops: "S" } }),
    );
    const { id } = await settle(api.createCheck(DEMO_SWEATER));
    const events: string[] = [];
    api.subscribe(id, (e) => events.push(`${e.type}:${e.step ?? ""}:${e.status ?? ""}`));
    await vi.runAllTimersAsync();
    expect(events).toContain("step:fit:done");
    expect(events[events.length - 1]).toBe("complete::");
  });
});

const DEMO_SWEATER = "https://merchandizable.example/p/demo-relaxed-sweater";
const DEMO_TROUSERS = "https://merchandizable.example/p/demo-wide-leg-trousers";
const DEMO_PETITE = "https://merchandizable.example/p/demo-petite-trousers";
const QUICK = {
  fit_mode: "quick_fit",
  size_system: "eu",
  quick_sizes: { tops: "S", bottoms: "M" },
} as const;
const PERSONAL: ProfileIn = {
  fit_mode: "personal_fit",
  unit: "cm",
  measurements: [
    { dimension: "waist", value: 66, basis: "body" },
    { dimension: "hips", value: 98, basis: "garment", note: "My jeans" },
  ],
};

describe("MockApiClient fit modes", () => {
  it("keeps Tops and Bottoms sizes separate", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(api.saveProfile(QUICK));
    expect(await settle(api.getProfile())).toMatchObject({
      fit_mode: "quick_fit",
      size_system: "eu",
      quick_sizes: { tops: "S", bottoms: "M" },
      measurements: [],
      unit: "cm",
    });
  });

  it("switching modes in either direction deletes nothing", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(api.saveProfile(QUICK));
    await settle(api.saveProfile(PERSONAL));
    await settle(api.saveProfile({ fit_mode: "quick_fit" }));
    const quick = await settle(api.getProfile());
    expect(quick?.fit_mode).toBe("quick_fit");
    expect(quick?.quick_sizes).toEqual({ tops: "S", bottoms: "M" });
    expect(quick?.measurements).toEqual([
      { dimension: "waist", value: 66, basis: "body", note: null },
      { dimension: "hips", value: 98, basis: "garment", note: "My jeans" },
    ]);
    await settle(api.saveProfile({ fit_mode: "personal_fit" }));
    expect((await settle(api.getProfile()))?.quick_sizes).toEqual({
      tops: "S",
      bottoms: "M",
    });
  });

  it("keeps the older waist, inseam and hips fields filled for older screens", async () => {
    useStorage();
    const api = new MockApiClient();
    await settle(api.saveProfile(PERSONAL));
    expect(await settle(api.getProfile())).toMatchObject({
      waist: 66,
      hips: 98,
      inseam: null,
    });
  });

  it("a section left out keeps saved brands", async () => {
    useStorage();
    const api = new MockApiClient();
    const brand = BRANDS[0];
    await settle(
      api.saveProfile({
        unit: "in",
        waist: 26,
        inseam: 30,
        brand_ids: [brand.id],
      }),
    );
    await settle(api.saveProfile(QUICK));
    expect((await settle(api.getProfile()))?.brands).toEqual([brand]);
  });

  it.each([
    [{ fit_mode: "quick_fit" as const }, "Pick a size"],
    [{ fit_mode: "personal_fit" as const }, "at least one measurement"],
  ])("rejects a mode with nothing to use: %j", async (body, message) => {
    useStorage();
    const assertion = expect(new MockApiClient().saveProfile(body)).rejects.toThrow(
      message,
    );
    await vi.runAllTimersAsync();
    await assertion;
  });

  it("reads a profile saved before fit modes as Personal Fit with the same values", async () => {
    useStorage({
      "bl:profile": JSON.stringify({
        unit: "in",
        waist: 26,
        inseam: 30,
        hips: null,
        brands: [],
        updated_at: "2026-10-01T00:00:00Z",
      }),
    });
    expect(await settle(new MockApiClient().getProfile())).toMatchObject({
      fit_mode: "personal_fit",
      unit: "in",
      waist: 26,
      inseam: 30,
      quick_sizes: {},
      measurements: [
        { dimension: "waist", value: 26, basis: "body", note: null },
        { dimension: "inseam", value: 30, basis: "body", note: null },
      ],
    });
  });

  it("treats a stored value of the wrong shape as no profile", async () => {
    useStorage({ "bl:v2:profile": JSON.stringify({ unit: 5 }) });
    expect(await settle(new MockApiClient().getProfile())).toBeNull();
  });
});

describe("MockApiClient catalog", () => {
  it("returns the catalog generated from Python", async () => {
    useStorage();
    const catalog = await settle(new MockApiClient().getMeasurements());
    expect(catalog.quick_sizes).toEqual(["XS", "S", "M", "L", "XL"]);
    expect(catalog.dimensions.find((d) => d.id === "waist")).toMatchObject({
      min_cm: 45,
      max_cm: 200,
    });
  });
});
