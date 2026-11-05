import { BadgeEuro, Ruler, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { Card, cx, OutcomeBadge } from "@/components/ui/primitives";
import type { FitCheck, FitRow, PriceCheck, SellerRisk, Unit } from "@/lib/api";
import { DIMENSION_LABEL, fmtLength, fmtMoney } from "@/lib/format";

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
  return (
    <CardShell
      icon={<BadgeEuro className="size-5" strokeWidth={1.5} aria-hidden />}
      title="Price"
      subtitle="The full cost. No checkout surprises."
    >
      <Row label="Listing price" value={fmtMoney(price.listing_cents, c)} />
      <Row
        label="Shipping"
        value={
          price.shipping_cents == null
            ? "Shipping cost unverified"
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
    </CardShell>
  );
}

const MODE_LABEL = {
  quick_fit: "Quick Fit · approximate",
  personal_fit: "Personal Fit",
};

function chartRange(row: FitRow, unit: Unit): string {
  const { chart_min_cm: low, chart_max_cm: high } = row;
  if (low == null || high == null) return "Not listed";
  return low === high
    ? fmtLength(low, unit)
    : `${fmtLength(low, unit)}–${fmtLength(high, unit)}`;
}

function FitRows({ rows, unit }: { rows: FitRow[]; unit: Unit }) {
  return (
    <table className="num mt-4 w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-[11px] tracking-wide text-muted uppercase">
          <th className="pb-2 font-normal">Measure</th>
          <th className="pb-2 text-right font-normal">You</th>
          <th className="pb-2 text-right font-normal">Size chart</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.dimension} className="border-b border-line last:border-0">
            <td className="py-2.5">
              {DIMENSION_LABEL[r.dimension] ?? r.dimension}
              {r.role === "secondary" && (
                <span className="text-xs text-muted"> · additional</span>
              )}
            </td>
            <td className="py-2.5 text-right">{fmtLength(r.user_cm, unit)}</td>
            <td
              className={cx(
                "py-2.5 text-right",
                r.status === "outside" && "text-negative",
              )}
            >
              {chartRange(r, unit)}
              <span className="sr-only"> ({r.status})</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function FitCheckCard({ fit, unit }: { fit: FitCheck; unit: Unit }) {
  const {
    mode = "personal_fit",
    outcome = "uncertain",
    reasons = [],
    rows = [],
  } = fit;
  const size = fit.size_label ? ` · Size ${fit.size_label}` : "";
  return (
    <CardShell
      icon={
        <Ruler className="size-5 -rotate-45" strokeWidth={1.5} aria-hidden />
      }
      title="Fit"
      subtitle={`${MODE_LABEL[mode]}${size} · ${unit === "in" ? "inches" : "cm"}`}
    >
      <div>
        <OutcomeBadge outcome={outcome} />
      </div>
      <ul className="mt-4 space-y-2 text-sm text-muted">
        {reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      {rows.length > 0 && <FitRows rows={rows} unit={unit} />}
    </CardShell>
  );
}

const RISK_STYLE = {
  low: { label: "Low risk", cls: "bg-positive-bg text-positive" },
  medium: { label: "Medium risk", cls: "bg-caution-bg text-caution" },
  high: { label: "High risk", cls: "bg-negative-bg text-negative" },
} as const;

function TrustRating({ risk }: { risk: SellerRisk }) {
  const style = risk.level ? RISK_STYLE[risk.level] : null;
  return (
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
          style ? style.cls : "bg-subtle text-muted",
        )}
      >
        {style ? style.label : "Not enough data"}
      </span>
    </div>
  );
}

function ProductReviews({ risk }: { risk: SellerRisk }) {
  const flags = risk.review_highlights;
  return (
    <>
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
              className={
                risk.level === "high" ? "text-negative" : "text-muted"
              }
            >
              “{f}”
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function SellerRiskCard({
  risk,
  brand,
}: {
  risk: SellerRisk;
  brand: string | null;
}) {
  const policy = risk.return_policy;
  return (
    <CardShell
      icon={<ShieldCheck className="size-5" strokeWidth={1.5} aria-hidden />}
      title="Seller Reliability"
      subtitle={
        risk.is_official
          ? `${brand ?? risk.seller_name} · Official brand store`
          : risk.seller_name
      }
    >
      <TrustRating risk={risk} />
      <ProductReviews risk={risk} />
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
    </CardShell>
  );
}
