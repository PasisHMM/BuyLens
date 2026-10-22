/**
 * Prototype-only port of the backend's deterministic rules (fitting.py, pricing.py, seller_risk.py,
 * rules.py, narrate.py template copy), so sample checks react to whatever measurements a tester
 * enters. The real verdicts come from the API in live mode.
 */
import { DIMENSION_NOUN, capitalize, fmtNumber, joinList } from "@/lib/format";
import type {
  CheckResult,
  FitCheck,
  FitRow,
  OptionOut,
  PriceCheck,
  SellerRisk,
  Verdict,
} from "../types";

const IN = 2.54;
type Basis = "body" | "garment";
type Dim = "waist" | "inseam" | "hips";
const DIMS: Dim[] = ["waist", "inseam", "hips"];

const RANGES: Record<Basis, Record<Dim, [number, number]>> = {
  garment: {
    waist: [0, 1.5 * IN],
    hips: [0.5 * IN, 3 * IN],
    inseam: [-0.5 * IN, 0.5 * IN],
  },
  body: {
    waist: [-0.5 * IN, 1 * IN],
    hips: [-0.5 * IN, 1.5 * IN],
    inseam: [-0.5 * IN, 0.5 * IN],
  },
};
const STRETCH_BONUS = 1 * IN;

export type ChartRow = { label: string; waist?: number; hips?: number }; // inches
export type ScenarioOption = {
  seller: { name: string; domain: string };
  url: string;
  isOfficial: boolean;
  listingCents: number;
  shippingCents: number | null;
  trust: number | null;
  reviewRating: number | null;
  reviewCount: number | null;
  returns: SellerRisk["return_policy"];
  highlights: string[];
  redFlags: string[];
  summary?: string;
};
export type Scenario = {
  key: string;
  product: CheckResult["product"] & {};
  source: string; // "levi.com · Women's original straight fit"
  chart: { basis: Basis; rows: ChartRow[]; lengths: number[] }; // lengths = garment inseam options (in)
  stretch: boolean;
  fabric: string;
  marketAvgCents: number | null;
  comparableCount: number;
  options: ScenarioOption[];
  failure?: { atStep: "product" | "prices"; message: string };
};

type Measurements = Partial<Record<Dim, number>>; // cm

function range(dim: Dim, basis: Basis, stretch: boolean): [number, number] {
  const [lo, hi] = RANGES[basis][dim];
  return [
    stretch && basis === "garment" && dim !== "inseam"
      ? lo - STRETCH_BONUS
      : lo,
    hi,
  ];
}

type SizeRow = {
  label: string;
  display: string;
  measures: Partial<Record<Dim, { cm: number; basis: Basis }>>;
};

function expandRows(s: Scenario): SizeRow[] {
  const rows: SizeRow[] = [];
  for (const row of s.chart.rows) {
    const base: SizeRow["measures"] = {};
    if (row.waist != null)
      base.waist = { cm: round1(row.waist * IN), basis: s.chart.basis };
    if (row.hips != null)
      base.hips = { cm: round1(row.hips * IN), basis: s.chart.basis };
    if (s.chart.lengths.length === 0)
      rows.push({ label: row.label, display: `W${row.label}`, measures: base });
    for (const length of s.chart.lengths) {
      rows.push({
        label: `${row.label}x${length}`,
        display: `W${row.label} / L${length}`,
        measures: {
          ...base,
          inseam: { cm: round1(length * IN), basis: "garment" },
        },
      });
    }
  }
  return rows;
}

function round1(x: number): number {
  return Math.round(x * 10) / 10;
}

function chooseSize(s: Scenario, user: Measurements): SizeRow | null {
  let best: [number, SizeRow] | null = null;
  for (const row of expandRows(s)) {
    let cost = 0;
    for (const dim of DIMS) {
      const m = row.measures[dim];
      const u = user[dim];
      if (!m || u == null) continue;
      const [lo, hi] = range(dim, m.basis, s.stretch);
      const room = m.cm - u;
      cost +=
        Math.max(lo - room, room - hi, 0) * 10 + Math.abs(room - (lo + hi) / 2);
    }
    if (!best || cost < best[0]) best = [cost, row];
  }
  return best?.[1] ?? null;
}

function fmtIn(cm: number): string {
  return `${fmtNumber(round1(cm / IN))}″`;
}

function evaluateFit(
  s: Scenario,
  size: SizeRow | null,
  user: Measurements,
): FitCheck {
  const rows: FitRow[] = [];
  const alerts: string[] = [];
  const notes: string[] = [];
  for (const dim of DIMS) {
    const u = user[dim];
    if (u == null) continue;
    const m = size?.measures[dim];
    if (!m) {
      rows.push({
        dimension: dim,
        user_cm: u,
        garment_cm: null,
        basis: null,
        match: "missing",
        room_cm: null,
      });
      alerts.push(`${capitalize(DIMENSION_NOUN[dim])} measurement unavailable`);
      continue;
    }
    const [lo, hi] = range(dim, m.basis, s.stretch);
    const room = round1(m.cm - u);
    const match: FitRow["match"] =
      room < lo
        ? dim === "inseam"
          ? "short"
          : "tight"
        : room > hi
          ? dim === "inseam"
            ? "long"
            : "loose"
          : "ok";
    rows.push({
      dimension: dim,
      user_cm: u,
      garment_cm: m.cm,
      basis: m.basis,
      match,
      room_cm: room,
    });
    if (dim === "inseam")
      notes.push(match === "ok" ? "inseam matches" : `inseam runs ${match}`);
    else if (match === "ok")
      notes.push(
        m.basis === "garment"
          ? `${dim} allows ${fmtIn(room)} ease`
          : `${dim} matches the size chart`,
      );
    else notes.push(`${dim} likely ${match}`);
  }
  notes.push(s.fabric, s.stretch ? "stretch fabric" : "no stretch");
  const missing = rows
    .filter((r) => r.match === "missing")
    .map((r) => r.dimension);
  const confidence: FitCheck["confidence"] =
    missing.length === 0
      ? "high"
      : missing.length === 1 && missing[0] === "inseam"
        ? "medium"
        : "limited";
  const sentence = notes.join("; ");
  return {
    size_label: size?.display ?? "—",
    rows,
    confidence,
    alerts,
    notes: `${capitalize(sentence)}.`,
  };
}

function evaluatePrice(s: Scenario, o: ScenarioOption): PriceCheck {
  const avg = s.marketAvgCents;
  const delta = avg != null ? o.listingCents - avg : null;
  return {
    currency: "USD",
    listing_cents: o.listingCents,
    shipping_cents: o.shippingCents,
    total_cents: o.listingCents + (o.shippingCents ?? 0),
    total_is_estimate: o.shippingCents == null,
    market_avg_cents: avg,
    delta_cents: delta,
    delta_pct: delta != null && avg ? round1((delta / avg) * 100) : null,
    comparable_count: s.comparableCount,
  };
}

function evaluateRisk(o: ScenarioOption): SellerRisk {
  const p = o.returns;
  const poorReviews =
    o.reviewRating != null &&
    o.reviewRating < 3.5 &&
    (o.reviewCount ?? 0) >= 20;
  let level: SellerRisk["level"] = "medium";
  if ((o.trust != null && o.trust < 3) || poorReviews || o.redFlags.length >= 2)
    level = "high";
  else if (
    (o.isOfficial || (o.trust ?? 0) >= 4.3) &&
    p.verified &&
    (p.window_days ?? 0) >= 14 &&
    !o.redFlags.length
  )
    level = "low";
  return {
    seller_name: o.seller.name,
    is_official: o.isOfficial,
    trust_rating: o.trust,
    level,
    review_rating: o.reviewRating,
    review_count: o.reviewCount,
    return_policy: p,
    review_highlights: [...o.highlights, ...o.redFlags],
    fit_signal: "unknown",
  };
}

function score(price: PriceCheck, fit: FitCheck, risk: SellerRisk): number {
  const priceS = Math.max(0, Math.min(1, 0.5 - (price.delta_pct ?? 0) / 40));
  const measured = fit.rows.filter((r) => r.match !== "missing");
  const okRatio = measured.length
    ? measured.filter((r) => r.match === "ok").length / measured.length
    : 0.5;
  const fitS = { high: 1, medium: 0.7, limited: 0.5 }[fit.confidence] * okRatio;
  const p = risk.return_policy;
  const returns = p.verified && p.free ? 1 : p.verified ? 0.8 : 0.7;
  const riskS = { low: 1, medium: 0.6, high: 0.1 }[risk.level] * returns;
  return 0.35 * priceS + 0.4 * fitS + 0.25 * riskS;
}

type Decision = { verdict: Verdict; reasons: string[]; missing: string[] };

function decide(o: OptionOut): Decision {
  const { fit_check: fit, price_check: price, seller_risk: risk } = o;
  const missing = fit.rows
    .filter((r) => r.match === "missing")
    .map((r) => r.dimension);
  const hard: string[] = [];
  if (fit.rows.some((r) => !["ok", "missing"].includes(r.match)))
    hard.push("FIT_MISMATCH");
  if (risk.level === "high") hard.push("SELLER_HIGH_RISK");
  if (price.delta_pct != null && price.delta_pct > 25) hard.push("OVERPRICED");
  if (hard.length) return { verdict: "SKIP", reasons: hard, missing };
  const soft: string[] = [];
  if (missing.length || !fit.rows.length) soft.push("FIT_DATA_MISSING");
  else if (fit.confidence !== "high") soft.push("FIT_UNCERTAIN");
  if (price.delta_pct != null && price.delta_pct > 5) soft.push("ABOVE_MARKET");
  if (
    risk.level === "medium" ||
    !(risk.return_policy.verified && risk.return_policy.free)
  )
    soft.push("RETURN_RISK");
  return { verdict: soft.length ? "CONSIDER" : "BUY", reasons: soft, missing };
}

function reasonSentence(code: string, o: OptionOut, d: Decision): string {
  const fit = o.fit_check;
  if (code === "FIT_MISMATCH") {
    const bad = fit.rows.find((r) => !["ok", "missing"].includes(r.match))!;
    return `It's likely ${bad.match} at the ${bad.dimension}.`;
  }
  if (code === "FIT_DATA_MISSING") {
    const dims = joinList(d.missing.map((m) => DIMENSION_NOUN[m] ?? m));
    return `The seller doesn't list ${/^[aeiou]/.test(dims) ? "an" : "a"} ${dims} measurement, so we won't call it a sure fit without one.`;
  }
  if (code === "FIT_UNCERTAIN")
    return "Size data is incomplete or reviews disagree on the fit.";
  if (code === "OVERPRICED" || code === "ABOVE_MARKET")
    return `It's ${Math.round(o.price_check.delta_pct ?? 0)}% above the market average.`;
  if (code === "SELLER_HIGH_RISK")
    return "The seller's reviews or track record raise concerns.";
  if (code === "RETURN_RISK")
    return o.seller_risk.return_policy.verified
      ? "Returns aren't free here."
      : "We haven't verified this store's return policy yet.";
  return "";
}

function headline(o: OptionOut, d: Decision): string {
  const goodPrice =
    o.price_check.delta_pct != null && o.price_check.delta_pct <= 0;
  if (d.verdict === "BUY") return "Fits your numbers at a fair price.";
  if (d.verdict === "SKIP") {
    if (d.reasons.includes("FIT_MISMATCH")) {
      const bad = o.fit_check.rows.find(
        (r) => !["ok", "missing"].includes(r.match),
      )!;
      return `Likely ${bad.match} at the ${bad.dimension}. Skip this one.`;
    }
    return d.reasons.includes("OVERPRICED")
      ? "Costs well above the usual price."
      : "Risky seller. Skip this one.";
  }
  const prefix = goodPrice ? "Good price. " : "";
  if (
    d.reasons.includes("FIT_DATA_MISSING") &&
    d.missing.length &&
    d.missing.length < o.fit_check.rows.length
  )
    return `${prefix}Check the ${joinList(d.missing)} before you buy.`;
  if (
    d.reasons.includes("FIT_DATA_MISSING") ||
    d.reasons.includes("FIT_UNCERTAIN")
  )
    return `${prefix}Double-check the size before you buy.`;
  if (d.reasons.includes("ABOVE_MARKET"))
    return "Looks right, but costs more than usual.";
  return `${prefix}Looks right. Check the return policy.`;
}

function explanation(o: OptionOut, d: Decision): string {
  const good = o.fit_check.rows
    .filter((r) => r.match === "ok")
    .map((r) => r.dimension);
  const positives: string[] = [];
  if (good.length)
    positives.push(
      `the ${joinList(good)} ${good.length === 1 ? "looks" : "look"} right`,
    );
  if (o.seller_risk.level === "low")
    positives.push(
      o.seller_risk.is_official
        ? "the official store is low risk"
        : "the seller is low risk",
    );
  if (o.price_check.delta_pct != null && o.price_check.delta_pct <= 0)
    positives.push("the price is below the market average");
  const negatives = d.reasons
    .map((c) => reasonSentence(c, o, d))
    .filter(Boolean);
  let text = positives.length ? `${capitalize(joinList(positives))}.` : "";
  if (negatives.length) {
    const first = negatives[0];
    text = text
      ? `${text} But ${first.charAt(0).toLowerCase()}${first.slice(1)}`
      : first;
    if (negatives[1]) text += ` ${negatives[1]}`;
  }
  return text || "Here's what we found.";
}

function whyNot(
  o: OptionOut,
  d: Decision,
): { buy: string | null; skip: string | null } {
  const buy =
    d.verdict !== "BUY" && d.reasons.length
      ? reasonSentence(d.reasons[0], o, d)
      : null;
  let skip: string | null = null;
  if (d.verdict !== "SKIP") {
    const passing: string[] = [];
    const pct = o.price_check.delta_pct;
    if (pct == null || pct <= 5)
      passing.push(
        pct != null
          ? "the price is competitive"
          : "nothing in the price stands out",
      );
    const p = o.seller_risk.return_policy;
    if (p.verified && p.free) passing.push("returns are free");
    if (!o.fit_check.rows.some((r) => !["ok", "missing"].includes(r.match)))
      passing.push("no measurement rules it out");
    if (passing.length) skip = `${capitalize(joinList(passing))}.`;
  }
  return { buy, skip };
}

function genericSummary(o: OptionOut, all: OptionOut[]): string {
  const cheapest = Math.min(...all.map((x) => x.total_cents));
  const parts: string[] = [];
  if (o.rank === 1) parts.push("Best overall value");
  if (o.total_cents === cheapest && all.length > 1)
    parts.push("lowest total cost");
  if (o.seller_risk.is_official) parts.push("official brand store");
  const p = o.seller_risk.return_policy;
  if (p.verified && p.free) parts.push("free returns");
  return `${capitalize(parts.join(", ") || "Also available")}.`;
}

export function runScenario(
  s: Scenario,
  user: Measurements,
  unit: "in" | "cm",
  meta: { id: string; url: string; createdAt: string },
): CheckResult {
  const size = chooseSize(s, user);
  const fit = evaluateFit(s, size, user);
  const scored = s.options.map((o) => {
    const price = evaluatePrice(s, o);
    const risk = evaluateRisk(o);
    const option: OptionOut = {
      rank: 0,
      seller: o.seller,
      url: o.url,
      total_cents: price.total_cents,
      summary: o.summary ?? "",
      price_check: price,
      fit_check: fit,
      seller_risk: risk,
    };
    return { option, score: score(price, fit, risk) };
  });
  const options = scored
    .sort(
      (a, b) =>
        b.score - a.score || a.option.total_cents - b.option.total_cents,
    )
    .slice(0, 3)
    .map(({ option }, i) => ({ ...option, rank: i + 1 }));
  for (const o of options) o.summary = o.summary || genericSummary(o, options);

  const d = decide(options[0]);
  const why = whyNot(options[0], d);
  return {
    id: meta.id,
    status: "done",
    current_step: null,
    input_url: meta.url,
    created_at: meta.createdAt,
    completed_at: new Date().toISOString(),
    error: null,
    unit,
    product: {
      ...s.product,
      attributes: { ...s.product.attributes, source: s.source },
    },
    selected_size: size?.display ?? null,
    verdict: d.verdict,
    headline: headline(options[0], d),
    explanation: explanation(options[0], d),
    why_not: why,
    options,
  };
}
