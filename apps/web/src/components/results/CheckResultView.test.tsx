// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  type CheckView,
  type OptionOut,
  type Profile,
} from "@/lib/api";
import { buildDemoResult, DEMO_CHART, DEMO_PRODUCTS } from "@/lib/api/mock/demo";
import { CheckResultView } from "./CheckResultView";
import { DemoSizeChart } from "./DemoSizeChart";

const app = vi.hoisted(() => ({
  api: {
    getCheck: vi.fn(),
    getFeedback: vi.fn(),
    submitFeedback: vi.fn(),
  },
  toast: { show: vi.fn() },
}));
vi.mock("@/app/providers", () => ({ useApp: () => app }));

function profile(over: Partial<Profile> = {}): Profile {
  return {
    unit: "cm",
    fit_mode: "quick_fit",
    size_system: "eu",
    quick_sizes: { tops: "M", bottoms: "M" },
    measurements: [],
    waist: null,
    inseam: null,
    hips: null,
    brands: [],
    updated_at: "2026-11-05T00:00:00Z",
    ...over,
  };
}

function demo(
  productId: string,
  over: Partial<Profile> = {},
  sampleId?: string,
): CheckView {
  const product = DEMO_PRODUCTS.find((p) => p.id === productId)!;
  return buildDemoResult(product, profile(over), {
    id: "run-1",
    url: product.input_url,
    createdAt: "2026-11-05T00:00:00Z",
    sampleId,
  });
}

async function show(result: CheckView | null) {
  app.api.getCheck.mockResolvedValue(result);
  const view = render(<CheckResultView id="run-1" />);
  await screen.findAllByText(/Check (another product|a product)/);
  return view;
}

beforeEach(() => {
  app.api.getCheck.mockReset();
  app.api.getFeedback.mockReset().mockResolvedValue(null);
  app.api.submitFeedback.mockReset().mockResolvedValue(undefined);
  app.toast.show.mockReset();
});

afterEach(cleanup);

describe("CheckResultView groups", () => {
  it("shows a match with its fit, EUR price and seller findings", async () => {
    const { container } = await show(demo("demo-wide-leg-trousers"));
    expect(screen.getByRole("heading", { name: "Matches" })).toBeTruthy();
    expect(screen.getByText("MATCH")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Check before buying" })).toBeNull();
    expect(container.textContent).toContain("Approximate fit based on size M");
    expect(container.textContent).toContain("€59.00");
    expect(container.textContent).toContain("Shipping cost unverified");
    expect(container.textContent).toContain("Not enough data");
    expect(container.textContent).toContain("Merchandizable · demo shop");
  });

  it("shows uncertain options separately, marked as needing attention", async () => {
    await show(demo("demo-relaxed-sweater"));
    expect(screen.getByRole("heading", { name: "Check before buying" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Matches" })).toBeNull();
    expect(screen.getByText("UNCERTAIN")).toBeTruthy();
    expect(screen.getByText("The size chart doesn't list shoulders.")).toBeTruthy();
  });

  it("keeps a mismatch out of the visible results, with no way to buy it", async () => {
    const { container } = await show(
      demo("demo-petite-trousers", { quick_sizes: { bottoms: "L" } }),
    );
    expect(screen.queryByRole("heading", { name: "Matches" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Check before buying" })).toBeNull();
    expect(screen.queryByText("MISMATCH")).toBeNull();
    expect(screen.queryByText(/View product at retailer/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Did you buy/ })).toBeNull();
    expect(container.textContent).toContain("No options to recommend");
    expect(container.textContent).toContain(
      "1 option hidden due to critical measurement mismatches",
    );
    expect(container.textContent).toContain("Waist for size L is 82.5–93 cm");
  });

  it("shows a hidden count beside the options that stay visible", async () => {
    const result = demo("demo-wide-leg-trousers");
    result.hidden_mismatches = { count: 2, reasons: ["Shop: Waist 100 cm"] };
    const { container } = await show(result);
    expect(screen.getByText("MATCH")).toBeTruthy();
    expect(container.textContent).toContain("2 options hidden");
    expect(container.textContent).not.toContain("No options to recommend");
  });

  it("shows no verdict or market comparison anywhere", async () => {
    const { container } = await show(demo("demo-wide-leg-trousers"));
    expect(container.textContent).not.toMatch(/\b(BUY|CONSIDER|SKIP)\b/);
    expect(container.textContent).not.toMatch(/market|average|%/i);
  });

  it("names the sample measurements behind a Personal Fit demo", async () => {
    const { container } = await show(
      demo("demo-wide-leg-trousers", {}, "inside-size-s"),
    );
    expect(container.textContent).toContain("Personal Fit");
    expect(container.textContent).toContain("Sample: Inside size S");
    const table = container.querySelector("table")!;
    expect(within(table).getAllByText("70").length).toBeGreaterThan(0);
  });
});

describe("CheckResultView seller and timing", () => {
  function withSeller(risk: Partial<OptionOut["seller_risk"]>, age_ms = 0): CheckView {
    const result = demo("demo-wide-leg-trousers");
    result.completed_at = new Date(Date.now() - age_ms).toISOString();
    result.matches[0].seller_risk = { ...result.matches[0].seller_risk, ...risk };
    return result;
  }

  it("shows a rated official seller with its verified returns and review quotes", async () => {
    const { container } = await show(
      withSeller({
        is_official: true,
        trust_rating: 4.8,
        level: "low",
        review_rating: 4.5,
        review_count: 1200,
        review_highlights: ["Soft denim"],
        return_policy: { verified: true, title: "30-day free returns", details: "Unworn." },
      }),
    );
    for (const text of [
      "Official brand store",
      "4.8 / 5",
      "Low risk",
      "4.5 / 5",
      "1,200 verified product reviews",
      "Soft denim",
      "30-day free returns",
    ])
      expect(container.textContent).toContain(text);
  });

  it.each([
    ["medium", "Medium risk"],
    ["high", "High risk"],
  ] as const)("shows %s seller risk", async (level, label) => {
    await show(withSeller({ level, review_highlights: ["Seams split"] }));
    expect(screen.getByText(label)).toBeTruthy();
  });

  it.each([
    [10 * 60_000, "Checked 10 min ago"],
    [3 * 3_600_000, "Checked 3 h ago"],
  ])("says how long ago a check ran (%i ms)", async (age, text) => {
    await show(withSeller({}, age));
    expect(screen.getByText(text)).toBeTruthy();
  });
});

describe("CheckResultView links", () => {
  it("links the real page only", async () => {
    await show(demo("levis-baggy-jeans"));
    expect(
      screen
        .getByRole("link", { name: /View product at retailer/ })
        .getAttribute("href"),
    ).toBe("https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans");
  });

  it("has no retailer link for a product with no real page", async () => {
    await show(demo("demo-relaxed-sweater"));
    expect(
      screen.queryByRole("link", { name: /View product at retailer/ }),
    ).toBeNull();
    expect(screen.getByText(/no product page/i)).toBeTruthy();
  });
});

describe("CheckResultView other states", () => {
  it("says when a check can't be found", async () => {
    await show(null);
    expect(screen.getByText(/couldn’t find this check/)).toBeTruthy();
  });

  it.each([
    ["failed", "The store blocked our check."],
    ["cancelled", "This check was cancelled."],
    ["running", "This check is still running."],
  ] as const)("explains a %s check", async (status, message) => {
    await show({
      ...demo("demo-wide-leg-trousers"),
      status,
      product: null,
      error: status === "failed" ? message : null,
    });
    expect(screen.getByText(message)).toBeTruthy();
  });

  it("saves feedback about the first visible option", async () => {
    app.api.submitFeedback.mockRejectedValue(new ApiError(501, "Later."));
    await show(demo("demo-wide-leg-trousers"));
    fireEvent.click(screen.getByRole("button", { name: /Did you buy/ }));
    expect(await screen.findByRole("dialog")).toBeTruthy();
  });

  it("shows saved feedback instead of the question", async () => {
    app.api.getFeedback.mockResolvedValue({
      purchased: true,
      option_rank: 1,
      fit: "fits_well",
      fit_dimension: null,
    });
    await show(demo("demo-wide-leg-trousers"));
    expect(await screen.findByText(/Saved for future checks/)).toBeTruthy();
  });
});

describe("DemoSizeChart", () => {
  it("is labelled as demo data and shows every size with its ranges", () => {
    const { container } = render(<DemoSizeChart chart={DEMO_CHART} />);
    expect(screen.getByText("Merchandizable — Demo Size Chart")).toBeTruthy();
    expect(container.textContent).toContain("not independently verified");
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows).toHaveLength(10);
    expect(rows[4].textContent).toBe("M40–4212–1490–9874–82.597.5–103.5");
    expect(rows[9].textContent).toBe("4XL60–6232–34143–155131.5–145.5143–155");
  });

  it("shows no shoulder or inseam column", () => {
    render(<DemoSizeChart chart={DEMO_CHART} />);
    expect(
      screen.getAllByRole("columnheader").map((h) => h.textContent),
    ).toEqual(["Size", "EUR", "UK", "Chest (cm)", "Waist (cm)", "Hips (cm)"]);
  });

  it("marks modes without data as unavailable", () => {
    const { container } = render(<DemoSizeChart chart={DEMO_CHART} />);
    expect(container.textContent).toContain("NORMAL");
    expect(container.textContent).toContain("UMSTANDSMODE: not available");
    expect(container.textContent).toContain("KLEINE GRÖSSEN: not available");
  });
});
