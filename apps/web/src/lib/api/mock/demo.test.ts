import { describe, expect, it } from "vitest";

import type { CheckView, Profile } from "../types";
import {
  buildDemoResult,
  DEMO_CHART,
  DEMO_PRODUCTS,
  demoProductForUrl,
  PERSONAL_SAMPLES,
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

function result(
  id: string,
  over: Partial<Profile>,
  sampleId?: string,
): CheckView {
  return buildDemoResult(product(id), profile(over), {
    id: "run",
    url: product(id).input_url,
    createdAt: "2026-11-05T00:00:00Z",
    sampleId,
  });
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

describe("buildDemoResult: Quick Fit", () => {
  it("places a match in the matches group, using the product's own category size", () => {
    const r = result("demo-wide-leg-trousers", {
      quick_sizes: { tops: "XL", bottoms: "M" },
    });
    expect(r.matches).toHaveLength(1);
    expect(r.uncertain).toEqual([]);
    expect(r.hidden_mismatches.count).toBe(0);
    expect(r.matches[0].fit_check.size_label).toBe("M");
    expect(r.matches[0].fit_check.approximate).toBe(true);
    expect(r.selected_size).toBe("M");
    expect(r.fit_mode_used).toBe("quick_fit");
  });

  it("never borrows a size from another category", () => {
    const r = result("demo-wide-leg-trousers", { quick_sizes: { tops: "M" } });
    expect(r.uncertain[0].fit_check.reasons).toEqual(["Add your Bottoms size."]);
  });

  it("keeps tops uncertain because the chart has no shoulders", () => {
    const r = result("demo-relaxed-sweater", { quick_sizes: { tops: "M" } });
    expect(r.matches).toEqual([]);
    expect(r.uncertain[0].fit_check.reasons).toContain(
      "The size chart doesn't list shoulders.",
    );
  });

  it("does not map waist/length products onto letter sizes", () => {
    const r = result("levis-baggy-jeans", { quick_sizes: { bottoms: "M" } });
    expect(r.uncertain[0].fit_check.size_label).toBeNull();
  });

  it("hides a proven mismatch from the visible results and suggests no size", () => {
    const r = result("demo-petite-trousers", { quick_sizes: { bottoms: "L" } });
    expect(r.matches).toEqual([]);
    expect(r.uncertain).toEqual([]);
    expect(r.selected_size).toBeNull();
    expect(r.hidden_mismatches.count).toBe(1);
    expect(r.hidden_mismatches.reasons?.[0]).toContain("Waist for size L");
  });

  it("invents no number for the person", () => {
    const r = result("demo-wide-leg-trousers", {
      quick_sizes: { bottoms: "M" },
    });
    for (const row of r.matches[0].fit_check.rows ?? [])
      expect(row.user_cm).toBeNull();
  });
});

describe("buildDemoResult: Personal Fit", () => {
  const personal = {
    fit_mode: "personal_fit",
    measurements: [{ dimension: "chest", value: 88, basis: "body", note: null }],
  } as Partial<Profile>;

  it("is honest that the browser can't compare someone's own measurements", () => {
    const r = result("demo-relaxed-sweater", personal);
    const reasons = r.uncertain[0].fit_check.reasons ?? [];
    expect(r.fit_mode_used).toBe("personal_fit");
    expect(reasons.join(" ")).toContain("doesn't list shoulders");
    expect(reasons.join(" ")).toContain("Python");
    expect(reasons.join(" ")).not.toContain("Add your");
  });

  it("shows Python's results for sample measurements, in all three groups", () => {
    const [inside, onLine, above] = PERSONAL_SAMPLES.map((s) =>
      result("demo-wide-leg-trousers", personal, s.id),
    );
    expect(inside.matches[0].fit_check.size_label).toBe("S");
    expect(inside.demo?.sample_label).toBe("Inside size S");
    expect(onLine.uncertain[0].fit_check.size_label).toBe("S / M");
    expect(above.hidden_mismatches.count).toBe(1);
    expect(above.matches).toEqual([]);
    expect(above.uncertain).toEqual([]);
  });
});

describe("buildDemoResult: contract", () => {
  it("carries the offer's identifiers and EUR, with the real link only", () => {
    const jeans = result("levis-baggy-jeans", {}).uncertain[0];
    expect(jeans.listing_id).toBeTruthy();
    expect(jeans.seller.name).toBe("Merchandizable");
    expect(jeans.url).toBe(
      "https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans",
    );
    expect(jeans.price_check.currency).toBe("EUR");
    expect(jeans.total_cents).toBe(5500);
    expect(result("demo-relaxed-sweater", {}).uncertain[0].url).toBe("");
  });

  it("has no verdict or market field", () => {
    const text = JSON.stringify(result("levis-baggy-jeans", {}));
    for (const word of ["verdict", "market", "delta", "headline", "why_not"])
      expect(text).not.toContain(word);
  });
});
