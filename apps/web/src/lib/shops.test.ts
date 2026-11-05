import { afterEach, describe, expect, it, vi } from "vitest";

import { KNOWN_WITHOUT_SAMPLE, MOCK_STORES } from "./api/mock/scenarios";
import {
  DEFAULT_SHOP,
  readSelectedShop,
  SHOPS,
  shopForUrl,
  writeSelectedShop,
} from "./shops";

function useStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
    },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("SHOPS", () => {
  it("offers Merchandizable as the only active shop, and selects it by default", () => {
    expect(SHOPS.filter((s) => s.status === "active").map((s) => s.name)).toEqual(
      ["Merchandizable"],
    );
    expect(DEFAULT_SHOP.name).toBe("Merchandizable");
    expect(DEFAULT_SHOP.demo).toBe(true);
  });

  it("keeps every existing store, deferred instead of deleted", () => {
    const domains = SHOPS.flatMap((s) => s.domains);
    for (const domain of [...Object.keys(MOCK_STORES), ...KNOWN_WITHOUT_SAMPLE])
      expect(domains).toContain(domain);
    for (const shop of SHOPS.filter((s) => s.id !== "merchandizable"))
      expect(shop.status).toBe("coming_soon");
  });

  it("calls no store a demo except the demo shop", () => {
    expect(SHOPS.filter((s) => s.demo).map((s) => s.id)).toEqual([
      "merchandizable",
    ]);
  });
});

describe("shopForUrl", () => {
  it("finds the shop from a link's host, with or without www", () => {
    expect(shopForUrl("https://www.levi.com/p/501")?.id).toBe("levis");
    expect(
      shopForUrl("https://merchandizable.sumupstore.com/produkt/x")?.id,
    ).toBe("merchandizable");
    expect(shopForUrl("https://merchandizable.example/p/x")?.id).toBe(
      "merchandizable",
    );
  });

  it("does not match a look-alike host", () => {
    expect(shopForUrl("https://levi.com.evil.test/p")).toBeUndefined();
    expect(shopForUrl("https://notlevi.com/p")).toBeUndefined();
  });

  it("has no shop for something that isn't a link", () => {
    expect(shopForUrl("hello")).toBeUndefined();
  });
});

describe("selected shop", () => {
  it("defaults to Merchandizable", () => {
    useStorage();
    expect(readSelectedShop().id).toBe("merchandizable");
  });

  it("remembers the selection", () => {
    useStorage();
    writeSelectedShop("merchandizable");
    expect(readSelectedShop().id).toBe("merchandizable");
  });

  it.each(["levis", "nope", ""])(
    "never restores the unavailable shop %j",
    (stored) => {
      useStorage({ "bl:v2:shop": stored });
      expect(readSelectedShop().id).toBe("merchandizable");
    },
  );

  it("works when storage is unavailable, such as during server rendering", () => {
    expect(readSelectedShop().id).toBe("merchandizable");
    expect(() => writeSelectedShop("merchandizable")).not.toThrow();
  });
});
