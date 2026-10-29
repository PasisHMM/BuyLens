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
  it("asks for measurements when waist is missing", () => {
    expect(profilePill(null, 30)).toBe("Add your fit");
  });

  it("shows waist alone or waist and length", () => {
    expect(profilePill(26, null)).toBe("W26");
    expect(profilePill(26.5, 30)).toBe("W26.5/L30");
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
