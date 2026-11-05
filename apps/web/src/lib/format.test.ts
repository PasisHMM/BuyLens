import { describe, expect, it } from "vitest";

import {
  fmtLength,
  fmtLengthWithUnit,
  fmtMoney,
  fromCm,
  hostOf,
  joinList,
  profilePill,
  toCm,
} from "./format";

describe("unit conversion", () => {
  it("converts inches to cm, rounded to one decimal", () => {
    expect(toCm(30, "in")).toBe(76.2);
    expect(toCm(26.5, "in")).toBe(67.3);
  });

  it("leaves cm unchanged", () => {
    expect(toCm(76.2, "cm")).toBe(76.2);
    expect(fromCm(76.2, "cm")).toBe(76.2);
  });

  it("round-trips a typed inch value", () => {
    expect(fromCm(toCm(30, "in"), "in")).toBe(30);
  });
});

describe("lengths", () => {
  it("shows a dash for missing values", () => {
    expect(fmtLength(null, "cm")).toBe("—");
    expect(fmtLengthWithUnit(undefined, "in")).toBe("—");
  });

  it("drops .0 and keeps one decimal otherwise", () => {
    expect(fmtLength(76.2, "in")).toBe("30");
    expect(fmtLength(67.3, "cm")).toBe("67.3");
  });

  it("labels the unit", () => {
    expect(fmtLengthWithUnit(30, "in")).toBe("30″");
    expect(fmtLengthWithUnit(76.5, "cm")).toBe("76.5 cm");
  });
});

describe("fmtMoney", () => {
  it("formats cents in the given currency", () => {
    expect(fmtMoney(9750)).toBe("$97.50");
    expect(fmtMoney(20000, "EUR")).toBe("€200.00");
  });

  it("shows a dash for unknown amounts but formats zero", () => {
    expect(fmtMoney(null)).toBe("—");
    expect(fmtMoney(0)).toBe("$0.00");
  });
});

describe("joinList", () => {
  it("joins with commas and a final 'and'", () => {
    expect(joinList([])).toBe("");
    expect(joinList(["waist"])).toBe("waist");
    expect(joinList(["waist", "hip"])).toBe("waist and hip");
    expect(joinList(["waist", "hip", "inseam"])).toBe("waist, hip and inseam");
  });
});

describe("profilePill", () => {
  it("asks for a fit when there is no profile", () => {
    expect(profilePill(null)).toBe("Add your fit");
  });

  it("names the mode and each category's size", () => {
    expect(
      profilePill({
        fit_mode: "quick_fit",
        quick_sizes: { tops: "S", bottoms: "M" },
      }),
    ).toBe("Quick Fit · Tops S · Bottoms M");
    expect(
      profilePill({ fit_mode: "quick_fit", quick_sizes: { bottoms: "L" } }),
    ).toBe("Quick Fit · Bottoms L");
  });

  it("shows only the mode for Personal Fit", () => {
    expect(profilePill({ fit_mode: "personal_fit", quick_sizes: {} })).toBe(
      "Personal Fit",
    );
  });
});

describe("hostOf", () => {
  it("extracts the host without www, with or without a scheme", () => {
    expect(hostOf("https://www.levi.com/US/en_US/p/501")).toBe("levi.com");
    expect(hostOf("madewell.com/jeans")).toBe("madewell.com");
  });

  it("returns the input when it is not a URL", () => {
    expect(hostOf("not a url")).toBe("not a url");
  });
});
