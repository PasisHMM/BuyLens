import { describe, expect, it } from "vitest";

import type { Profile } from "../types";
import {
  buildDemoCheck,
  DEMO_CHART,
  DEMO_PRODUCTS,
  demoProductForUrl,
} from "./demo";

const EXPECTED = [
  ["XXS", "32", "4", [75, 78], [62, 64], [82, 86]],
  ["XS", "34", "6", [78, 82], [64, 66], [86, 90]],
  ["S", "36–38", "8–10", [82, 90], [66, 74], [90, 97.5]],
  ["M", "40–42", "12–14", [90, 98], [74, 82.5], [97.5, 103.5]],
  ["L", "44–46", "16–18", [98, 107], [82.5, 93], [103.5, 110.5]],
  ["XL", "48–50", "20–22", [107, 119], [93, 105], [110.5, 120.5]],
  ["XXL", "52–54", "24–26", [119, 131], [105, 117.5], [120.5, 131]],
  ["3XL", "56–58", "28–30", [131, 143], [117.5, 131.5], [131, 143]],
  ["4XL", "60–62", "32–34", [143, 155], [131.5, 145.5], [143, 155]],
];

function profile(over: Partial<Profile>): Profile {
  return {
    unit: "cm",
    fit_mode: "quick_fit",
    size_system: "eu",
    quick_sizes: {},
    measurements: [],
    waist: null,
    inseam: null,
    hips: null,
    brands: [],
    updated_at: "2026-11-05T00:00:00Z",
    ...over,
  };
}

function product(id: string) {
  return DEMO_PRODUCTS.find((p) => p.id === id)!;
}

describe("Merchandizable demo chart", () => {
  it("has all nine sizes with their exact ranges and separate EU and UK labels", () => {
    expect(
      DEMO_CHART.rows.map((r) => [
        r.label,
        r.eu,
        r.uk,
        [r.chest.min_cm, r.chest.max_cm],
        [r.waist.min_cm, r.waist.max_cm],
        [r.hips.min_cm, r.hips.max_cm],
      ]),
    ).toEqual(EXPECTED);
  });

  it("is labelled as unverified demo data", () => {
    expect(DEMO_CHART.title).toBe("Merchandizable — Demo Size Chart");
    expect(DEMO_CHART.disclaimer).toContain("not independently verified");
    expect(DEMO_CHART.basis).toBe("body");
  });

  it("invents no shoulders or inseam", () => {
    for (const row of DEMO_CHART.rows) {
      expect(row).not.toHaveProperty("shoulders");
      expect(row).not.toHaveProperty("inseam");
    }
  });

  it("offers only the normal mode; the other two have no data", () => {
    expect(DEMO_CHART.sizing_mode).toBe("NORMAL");
    expect(DEMO_CHART.unavailable_modes).toEqual([
      "UMSTANDSMODE",
      "KLEINE GRÖSSEN",
    ]);
    expect(JSON.stringify(DEMO_CHART.rows)).not.toContain("UMSTANDS");
  });
});

describe("demoProductForUrl", () => {
  it.each([
    "https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans",
    "https://www.merchandizable.sumupstore.com/produkt/levis-baggy-jeans/",
    "merchandizable.sumupstore.com/produkt/levis-baggy-jeans?utm_source=x",
  ])("finds the product from %s", (url) => {
    expect(demoProductForUrl(url)?.id).toBe("levis-baggy-jeans");
  });

  it("finds nothing for another page", () => {
    expect(
      demoProductForUrl("https://merchandizable.example/p/unknown"),
    ).toBeUndefined();
  });
});

describe("product destinations", () => {
  it("links only the real page; demo products have none", () => {
    expect(product("levis-baggy-jeans").product_url).toBe(
      "https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans",
    );
    expect(product("demo-relaxed-sweater").product_url).toBeNull();
    expect(product("demo-wide-leg-trousers").product_url).toBeNull();
  });
});

describe("buildDemoCheck", () => {
  it("reads the Python outcome for the size of the product's own category", () => {
    const check = buildDemoCheck(
      product("demo-relaxed-sweater"),
      profile({ quick_sizes: { tops: "M", bottoms: "XL" } }),
    );
    expect(check.fit.mode).toBe("quick_fit");
    expect(check.fit.outcome).toBe("match");
    expect(check.fit.size_label).toBe("M");
    expect(check.fit.reasons[0]).toContain("Approximate fit based on size M");
  });

  it("never borrows a size from another category", () => {
    const check = buildDemoCheck(
      product("demo-wide-leg-trousers"),
      profile({ quick_sizes: { tops: "M" } }),
    );
    expect(check.fit.outcome).toBe("uncertain");
    expect(check.fit.reasons).toEqual(["Add your Bottoms size."]);
  });

  it("does not map waist/length products onto letter sizes", () => {
    const check = buildDemoCheck(
      product("levis-baggy-jeans"),
      profile({ quick_sizes: { bottoms: "M" } }),
    );
    expect(check.fit.outcome).toBe("uncertain");
    expect(check.fit.size_label).toBeNull();
  });

  it("never shows MISMATCH for any Quick Fit size", () => {
    for (const p of DEMO_PRODUCTS)
      for (const outcome of Object.values(p.quick_fit))
        expect(outcome.outcome).not.toBe("mismatch");
  });

  it("is honest that Personal Fit isn't compared in the browser", () => {
    const check = buildDemoCheck(
      product("demo-relaxed-sweater"),
      profile({
        fit_mode: "personal_fit",
        measurements: [
          { dimension: "chest", value: 88, basis: "body", note: null },
        ],
      }),
    );
    expect(check.fit.mode).toBe("personal_fit");
    expect(check.fit.outcome).toBe("uncertain");
    expect(check.fit.reasons.join(" ")).toContain("doesn't list shoulders");
    expect(check.fit.reasons.join(" ")).toContain("Python");
    expect(check.fit.reasons.join(" ")).not.toContain("Add your");
  });

  it("carries the identifiers a displayed offer needs, and EUR", () => {
    const check = buildDemoCheck(
      product("levis-baggy-jeans"),
      profile({ quick_sizes: { bottoms: "M" } }),
    );
    expect(check.offer).toEqual({
      listingId: "levis-baggy-jeans",
      retailerId: "merchandizable",
      retailerName: "Merchandizable",
      url: "https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans",
    });
    expect(check.price_cents).toBe(5500);
    expect(check.currency).toBe("EUR");
    expect(check.shop_name).toBe("Merchandizable");
  });
});
