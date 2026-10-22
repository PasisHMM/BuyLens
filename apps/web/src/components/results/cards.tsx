import { BadgeDollarSign, Ruler, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { Callout, Card, cx } from "@/components/ui/primitives";
import type { FitCheck, PriceCheck, SellerRisk, Unit } from "@/lib/api";
import {
  DIMENSION_LABEL,
  DIMENSION_NOUN,
  fmtLength,
  fmtMoney,
} from "@/lib/format";

function CardShell({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <Card className="flex flex-col p-6">
      <h3 className="flex items-center gap-3 text-xl">
        {icon}
        {title}
      </h3>
      <p className="mt-2 text-xs text-muted">{subtitle}</p>
      <div className="mt-6 flex flex-1 flex-col">{children}</div>
    </Card>
  );
}

function Row({
  label,
  value,
  big,
}: {
  label: string;
  value: string;
  big?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between py-2.5">
      <span className="text-sm text-muted">{label}</span>
      <span className={cx("num", big ? "text-2xl" : "text-sm")}>{value}</span>
    </div>
  );
}

export function PriceCheckCard({ price }: { price: PriceCheck }) {
  const c = price.currency;
  const below = price.delta_cents != null && price.delta_cents < 0;
  return (
    <CardShell
      icon={
        <BadgeDollarSign className="size-5" strokeWidth={1.5} aria-hidden />
      }
      title="Price Check"
      subtitle="The full cost. No checkout surprises."
    >
      <Row label="Listing price" value={fmtMoney(price.listing_cents, c)} />
      <Row
        label="Shipping"
        value={
          price.shipping_cents == null
            ? "Unknown"
            : fmtMoney(price.shipping_cents, c)
        }
      />
      <div className="my-1 border-t border-line" />
      <Row
        label={
          price.total_is_estimate ? "Total (before shipping)" : "Total cost"
        }
        value={fmtMoney(price.total_cents, c)}
        big
      />
      <Row
        label="Market average"
        value={
          price.market_avg_cents == null
            ? "Not enough data"
            : fmtMoney(price.market_avg_cents, c)
        }
      />
      <div className="mt-4">
        {price.delta_cents == null || price.delta_pct == null ? (
          <p className="rounded-lg bg-subtle px-4 py-3 text-xs text-muted">
            Fewer than 3 comparable listings, so there’s no market average yet.
          </p>
        ) : price.delta_cents === 0 ? (
          <Callout tone="consider" title="At the market average">
            {price.comparable_count} comparable listings
          </Callout>
        ) : (
          <Callout
            tone={below ? "buy" : "consider"}
            title={`${fmtMoney(Math.abs(price.delta_cents), c)} ${below ? "below" : "above"} average`}
          >
            {Math.abs(price.delta_pct).toFixed(1)}% {below ? "less" : "more"} ·{" "}
            {price.comparable_count} comparable listings
          </Callout>
        )}
      </div>
      <p className="mt-auto pt-5 text-[11px] leading-relaxed text-muted">
        {c}, before sales tax. Checked just now. Market average excludes
        shipping.
        {price.total_is_estimate &&
          " Shipping isn’t listed, so the total may be higher."}
      </p>
    </CardShell>
  );
}

export function FitCheckCard({ fit, unit }: { fit: FitCheck; unit: Unit }) {
  const missing = fit.rows.filter((r) => r.match === "missing");
  const misfit = fit.rows.filter((r) => !["ok", "missing"].includes(r.match));
  const otherAlerts = fit.alerts.filter(
    (a) => !a.endsWith("measurement unavailable"),
  );
  return (
    <CardShell
      icon={
        <Ruler className="size-5 -rotate-45" strokeWidth={1.5} aria-hidden />
      }
      title="Fit Check"
      subtitle={`${fit.size_label} · All measurements in ${unit === "in" ? "inches" : "cm"}`}
    >
      <table className="num w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-[11px] tracking-wide text-muted uppercase">
            <th className="pb-2 font-normal">Measure</th>
            <th className="pb-2 text-right font-normal">You</th>
            <th className="pb-2 text-right font-normal">Garment</th>
          </tr>
        </thead>
        <tbody>
          {fit.rows.map((r) => (
            <tr
              key={r.dimension}
              className="border-b border-line last:border-0"
            >
              <td className="py-3.5">
                {DIMENSION_LABEL[r.dimension] ?? r.dimension}
              </td>
              <td className="py-3.5 text-right text-base">
                {fmtLength(r.user_cm, unit)}
              </td>
              <td
                className={cx(
                  "py-3.5 text-right text-base",
                  !["ok", "missing"].includes(r.match) && "text-skip",
                )}
              >
                {fmtLength(r.garment_cm, unit)}
                <span className="sr-only"> ({r.match})</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-4 space-y-2">
        {misfit.map((r) => (
          <Callout
            key={r.dimension}
            tone="skip"
            title={`Likely ${r.match} at the ${DIMENSION_NOUN[r.dimension] ?? r.dimension}`}
          >
            Outside the range we’d expect for your{" "}
            {DIMENSION_NOUN[r.dimension] ?? r.dimension} in this size.
          </Callout>
        ))}
        {missing.map((r) => {
          const noun = DIMENSION_NOUN[r.dimension] ?? r.dimension;
          return (
            <Callout
              key={r.dimension}
              tone="consider"
              title={`${noun.charAt(0).toUpperCase()}${noun.slice(1)} measurement unavailable`}
            >
              We can’t confirm {noun} fit. Ask the seller before ordering.
            </Callout>
          );
        })}
        {otherAlerts.map((a) => (
          <Callout key={a} tone="consider" title={a} />
        ))}
      </div>
      <p className="mt-auto pt-5 text-[11px] leading-relaxed text-muted">
        {fit.notes} Fit confidence: {fit.confidence}.
      </p>
    </CardShell>
  );
}

const RISK_STYLE = {
  low: { label: "Low risk", cls: "bg-buy-bg text-buy" },
  medium: { label: "Medium risk", cls: "bg-consider-bg text-consider" },
  high: { label: "High risk", cls: "bg-skip-bg text-skip" },
} as const;

export function SellerRiskCard({
  risk,
  brand,
}: {
  risk: SellerRisk;
  brand: string | null;
}) {
  const policy = risk.return_policy;
  const style = RISK_STYLE[risk.level];
  const flags = risk.review_highlights;
  return (
    <CardShell
      icon={<ShieldCheck className="size-5" strokeWidth={1.5} aria-hidden />}
      title="Seller Risk"
      subtitle={
        risk.is_official
          ? `${brand ?? risk.seller_name} · Official brand store`
          : risk.seller_name
      }
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="num text-[32px] leading-none">
            {risk.trust_rating == null
              ? "—"
              : `${risk.trust_rating.toFixed(1)} / 5`}
          </p>
          <p className="mt-2 text-xs text-muted">
            {risk.trust_rating == null
              ? "Seller not rated yet"
              : "Seller trust rating"}
          </p>
        </div>
        <span
          className={cx(
            "rounded-full px-2.5 py-1 text-xs font-medium",
            style.cls,
          )}
        >
          {style.label}
        </span>
      </div>

      <div className="mt-7 flex items-baseline justify-between">
        <span className="text-sm text-muted">Product reviews</span>
        <span className="num text-sm">
          {risk.review_rating == null
            ? "—"
            : `${risk.review_rating.toFixed(1)} / 5`}
        </span>
      </div>
      {risk.review_count != null && (
        <p className="num mt-1.5 text-xs text-muted">
          {risk.review_count.toLocaleString("en-US")} verified product reviews
        </p>
      )}
      {flags.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs">
          {flags.map((f) => (
            <li
              key={f}
              className={risk.level === "high" ? "text-skip" : "text-muted"}
            >
              “{f}”
            </li>
          ))}
        </ul>
      )}

      <div className="my-5 border-t border-line" />
      <p className="text-[15px]">
        {policy.verified
          ? (policy.title ?? "Return policy")
          : "Return policy not verified yet"}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        {policy.verified
          ? policy.details
          : "Check the store’s return terms before you order."}
      </p>
      <p className="mt-auto pt-5 text-[11px] leading-relaxed text-muted">
        Based on store policies and verified reviews. Confirm the policy at
        checkout.
      </p>
    </CardShell>
  );
}
