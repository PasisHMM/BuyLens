import type { Unit } from "./api/types";

export const CM_PER_IN = 2.54;

export function toCm(value: number, unit: Unit): number {
  return Math.round((unit === "in" ? value * CM_PER_IN : value) * 10) / 10;
}

export function fromCm(cm: number, unit: Unit): number {
  return Math.round((unit === "in" ? cm / CM_PER_IN : cm) * 10) / 10;
}

/** 26 → "26", 26.5 → "26.5" */
export function fmtNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** Length in the user's unit, e.g. `26` or `66` (no unit label; tables say the unit once). */
export function fmtLength(cm: number | null | undefined, unit: Unit): string {
  return cm == null ? "—" : fmtNumber(fromCm(cm, unit));
}

/** `26"` or `66 cm` */
export function fmtLengthWithUnit(
  value: number | null | undefined,
  unit: Unit,
): string {
  if (value == null) return "—";
  return unit === "in" ? `${fmtNumber(value)}″` : `${fmtNumber(value)} cm`;
}

export function fmtMoney(
  cents: number | null | undefined,
  currency = "USD",
): string {
  if (cents == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(
    cents / 100,
  );
}

export const DIMENSION_LABEL: Record<string, string> = {
  waist: "Waist",
  inseam: "Inseam",
  hips: "Hips",
};
export const DIMENSION_NOUN: Record<string, string> = {
  waist: "waist",
  inseam: "inseam",
  hips: "hip",
};

export function joinList(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** "W26/L30" for the header pill, from a profile in its own unit. */
export function profilePill(
  waist: number | null | undefined,
  inseam: number | null | undefined,
): string {
  if (waist == null) return "Add your fit";
  return inseam == null
    ? `W${fmtNumber(waist)}`
    : `W${fmtNumber(waist)}/L${fmtNumber(inseam)}`;
}

export function hostOf(url: string): string {
  try {
    return new URL(
      url.includes("://") ? url : `https://${url}`,
    ).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
