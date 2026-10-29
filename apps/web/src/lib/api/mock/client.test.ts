import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MockApiClient } from "./client";

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
      new MockApiClient().createCheck("https://www.levi.com/p/501"),
      { status: 409, message: "Save your measurements first." },
    );
  });
});
