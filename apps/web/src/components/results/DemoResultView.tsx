import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Callout, Card, ProductImage } from "@/components/ui/primitives";
import type { CheckView, DemoCheck } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { DemoSizeChart } from "./DemoSizeChart";
import { ViewAtRetailer } from "./ViewAtRetailer";

const OUTCOME_TONE: Record<string, "buy" | "consider" | "skip"> = {
  match: "buy",
  uncertain: "consider",
  mismatch: "skip",
};
const MODE_LABEL = { quick_fit: "Quick Fit", personal_fit: "Personal Fit" };

/** A demo shop check: Fit, Price and Seller Reliability findings, with no verdict. */
export function DemoResultView({ result }: { result: CheckView }) {
  const demo = result.demo as DemoCheck;
  const { fit } = demo;
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-6 sm:px-8 sm:py-9">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"
      >
        <ArrowLeft className="size-4" aria-hidden /> Check another product
      </Link>

      <div className="mt-7 flex gap-4 sm:gap-6">
        <ProductImage name={result.product?.name ?? "Product"} />
        <div className="min-w-0">
          <p className="eyebrow text-muted">{demo.shop_name} · demo shop</p>
          <h1 className="mt-2 font-serif text-[26px] leading-tight sm:text-[40px]">
            {result.product?.name}
          </h1>
          <p className="mt-2 text-sm text-muted">
            {demo.product_type} · Listed sizes: {demo.sold_sizes.join(", ")}
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="p-6">
          <h2 className="text-xl">Fit</h2>
          <p className="mt-2 text-xs text-muted">
            {MODE_LABEL[fit.mode]} against the demo chart
          </p>
          <div className="mt-5">
            <Callout
              tone={OUTCOME_TONE[fit.outcome]}
              title={fit.outcome.toUpperCase()}
            />
          </div>
          <ul className="mt-4 space-y-2 text-sm text-muted">
            {fit.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </Card>

        <Card className="p-6">
          <h2 className="text-xl">Price</h2>
          <p className="mt-2 text-xs text-muted">Sample price</p>
          <p className="num mt-5 text-2xl">
            {fmtMoney(demo.price_cents, demo.currency)}
          </p>
          <p className="mt-4 text-sm text-muted">Shipping cost unverified</p>
        </Card>

        <Card className="p-6">
          <h2 className="text-xl">Seller Reliability</h2>
          <p className="mt-2 text-xs text-muted">{demo.shop_name}</p>
          <p className="mt-5 text-[15px]">Not enough data</p>
          <p className="mt-4 text-sm text-muted">
            A demo shop has no reviews to assess.
          </p>
        </Card>
      </div>

      <div className="mt-6 flex flex-col sm:items-end">
        <ViewAtRetailer offer={demo.offer} />
      </div>

      <Card className="mt-6 p-6">
        <DemoSizeChart chart={demo.chart} />
      </Card>
    </div>
  );
}
