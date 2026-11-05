// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CheckView, Profile } from "@/lib/api";
import { buildDemoCheck, DEMO_PRODUCTS } from "@/lib/api/mock/demo";
import { DemoResultView } from "./DemoResultView";
import { DemoSizeChart } from "./DemoSizeChart";

const QUICK = {
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
} as Profile;

function result(productId: string, profile = QUICK): CheckView {
  const product = DEMO_PRODUCTS.find((p) => p.id === productId)!;
  const demo = buildDemoCheck(product, profile);
  return {
    id: "run-1",
    status: "done",
    current_step: null,
    input_url: product.input_url,
    created_at: "2026-11-05T00:00:00Z",
    completed_at: "2026-11-05T00:00:00Z",
    error: null,
    unit: "cm",
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
  };
}

afterEach(cleanup);

describe("DemoResultView", () => {
  it("shows a fit outcome and no verdict or market comparison", () => {
    const { container } = render(
      <DemoResultView result={result("demo-relaxed-sweater")} />,
    );
    expect(screen.getByText("MATCH")).toBeTruthy();
    expect(container.textContent).toContain("Approximate fit based on size M");
    expect(container.textContent).not.toMatch(/\b(BUY|CONSIDER|SKIP)\b/);
    expect(container.textContent).not.toMatch(/market|average|%/i);
  });

  it("shows UNCERTAIN when a product's sizes don't match the chart's labels", () => {
    render(<DemoResultView result={result("levis-baggy-jeans")} />);
    expect(screen.getByText("UNCERTAIN")).toBeTruthy();
  });

  it("shows EUR prices and doesn't invent shipping or seller data", () => {
    const { container } = render(
      <DemoResultView result={result("levis-baggy-jeans")} />,
    );
    expect(container.textContent).toContain("€55.00");
    expect(container.textContent).toContain("Shipping cost unverified");
    expect(container.textContent).toContain("Not enough data");
  });

  it("names the shop as a demo", () => {
    const { container } = render(
      <DemoResultView result={result("levis-baggy-jeans")} />,
    );
    expect(container.textContent).toContain("Merchandizable · demo shop");
  });

  it("links the real page only", () => {
    render(<DemoResultView result={result("levis-baggy-jeans")} />);
    expect(
      screen
        .getByRole("link", { name: /View product at retailer/ })
        .getAttribute("href"),
    ).toBe("https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans");
  });

  it("has no retailer link for a product with no real page", () => {
    render(<DemoResultView result={result("demo-relaxed-sweater")} />);
    expect(
      screen.queryByRole("link", { name: /View product at retailer/ }),
    ).toBeNull();
    expect(screen.getByText(/no product page/i)).toBeTruthy();
  });
});

describe("DemoSizeChart", () => {
  it("is labelled as demo data and shows every size with its ranges", () => {
    const { container } = render(
      <DemoSizeChart chart={result("levis-baggy-jeans").demo!.chart} />,
    );
    expect(screen.getByText("Merchandizable — Demo Size Chart")).toBeTruthy();
    expect(container.textContent).toContain("not independently verified");
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows).toHaveLength(10);
    expect(rows[4].textContent).toBe("M40–4212–1490–9874–82.597.5–103.5");
    expect(rows[9].textContent).toBe("4XL60–6232–34143–155131.5–145.5143–155");
  });

  it("shows no shoulder or inseam column", () => {
    render(<DemoSizeChart chart={result("levis-baggy-jeans").demo!.chart} />);
    const headers = screen
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers).toEqual([
      "Size",
      "EUR",
      "UK",
      "Chest (cm)",
      "Waist (cm)",
      "Hips (cm)",
    ]);
  });

  it("marks modes without data as unavailable", () => {
    const { container } = render(
      <DemoSizeChart chart={result("levis-baggy-jeans").demo!.chart} />,
    );
    expect(container.textContent).toContain("NORMAL");
    expect(container.textContent).toContain("UMSTANDSMODE: not available");
    expect(container.textContent).toContain("KLEINE GRÖSSEN: not available");
  });
});
