"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useApp } from "@/app/providers";
import {
  Button,
  ButtonLink,
  Callout,
  Card,
  ProductImage,
} from "@/components/ui/primitives";
import type { CheckView, Feedback, OptionOut, Unit } from "@/lib/api";
import { DIMENSION_NOUN, fmtMoney } from "@/lib/format";
import { FitCheckCard, PriceCheckCard, SellerRiskCard } from "./cards";
import { DemoSizeChart } from "./DemoSizeChart";
import { FeedbackDialog, feedbackSummary } from "./FeedbackDialog";
import { ViewAtRetailer } from "./ViewAtRetailer";

const MODE_LABEL = { quick_fit: "Quick Fit", personal_fit: "Personal Fit" };

function checkedAgo(iso: string | null): string {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 2) return "Checked just now";
  if (minutes < 60) return `Checked ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24
    ? `Checked ${hours} h ago`
    : `Checked ${new Date(iso).toLocaleDateString("en-US")}`;
}

/** The measurement feedback asks about: one we couldn't compare, else one that wasn't inside. */
function feedbackDimension(option: OptionOut): string | null {
  const rows = option.fit_check.rows ?? [];
  const row =
    rows.find((r) => r.status === "missing") ??
    rows.find((r) => r.status !== "inside") ??
    null;
  return row ? (DIMENSION_NOUN[row.dimension] ?? row.dimension) : null;
}

function headerEyebrow({ product, demo }: CheckView): string {
  if (demo) return `${demo.shop_name} · demo shop`;
  return [product?.brand, product?.category].filter(Boolean).join(" · ");
}

function headerFacts({ product, demo, fit_mode_used: mode }: CheckView): string {
  const facts: (string | null | undefined)[] = [mode && MODE_LABEL[mode]];
  if (demo) facts.unshift(product?.category);
  if (demo?.sample_label) facts.push(`Sample: ${demo.sample_label}`);
  if (demo) facts.push(`Listed sizes: ${demo.sold_sizes.join(", ")}`);
  return facts.filter(Boolean).join(" · ");
}

function ProductHeader({ result }: { result: CheckView }) {
  const { product } = result;
  return (
    <div className="mt-7 flex gap-4 sm:gap-6">
      <ProductImage name={product?.name ?? "Product"} />
      <div className="min-w-0">
        <p className="eyebrow text-muted">{headerEyebrow(result)}</p>
        <h1 className="mt-2 font-serif text-[26px] leading-tight sm:mt-3 sm:text-[40px]">
          {product?.name}
        </h1>
        <p className="mt-2 text-sm text-muted">{headerFacts(result)}</p>
      </div>
    </div>
  );
}

function OptionSection({
  option,
  unit,
  brand,
}: {
  option: OptionOut;
  unit: Unit;
  brand: string | null;
}) {
  return (
    <article className="mt-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="text-sm">
          <span className="font-semibold">
            {option.seller.name} ·{" "}
            <span className="num">
              {fmtMoney(option.total_cents, option.price_check.currency)}
            </span>{" "}
            total
          </span>
          <span className="mt-1 block text-xs text-muted">
            {option.summary}
          </span>
        </p>
        <ViewAtRetailer
          offer={{
            listingId: option.listing_id,
            retailerId: option.seller.domain,
            retailerName: option.seller.name,
            url: option.url,
          }}
        />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <FitCheckCard fit={option.fit_check} unit={unit} />
        <PriceCheckCard price={option.price_check} />
        <SellerRiskCard risk={option.seller_risk} brand={brand} />
      </div>
    </article>
  );
}

function OptionGroup({
  title,
  hint,
  options,
  unit,
  brand,
}: {
  title: string;
  hint: string;
  options: OptionOut[];
  unit: Unit;
  brand: string | null;
}) {
  if (!options.length) return null;
  return (
    <section className="mt-8">
      <h2 className="text-xl sm:text-2xl">{title}</h2>
      <p className="mt-1 text-xs text-muted">{hint}</p>
      {options.map((o) => (
        <OptionSection key={o.rank} option={o} unit={unit} brand={brand} />
      ))}
    </section>
  );
}

/** Mismatches are out of the list above. This note says why, and offers no way to buy them. */
function HiddenMismatches({
  count,
  reasons = [],
}: CheckView["hidden_mismatches"]) {
  if (!count) return null;
  const options = count === 1 ? "1 option" : `${count} options`;
  return (
    <details className="mt-8 rounded-xl bg-subtle px-5 py-4 text-sm">
      <summary className="cursor-pointer">
        {options} hidden due to critical measurement mismatches{" "}
        <span className="underline underline-offset-4">View</span>
      </summary>
      <ul className="mt-3 space-y-2 text-muted">
        {reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </details>
  );
}

function FeedbackSection({
  feedback,
  dimension,
  onOpen,
}: {
  feedback: Feedback | null;
  dimension: string | null;
  onOpen: () => void;
}) {
  if (feedback)
    return (
      <section className="mt-8 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <p className="text-sm text-muted">
          {feedbackSummary(feedback, dimension)} Saved for future checks.
        </p>
        <ButtonLink href="/" variant="secondary">
          Check another product
        </ButtonLink>
      </section>
    );
  return (
    <section className="mt-8">
      <Button variant="secondary" onClick={onOpen}>
        Did you buy this item?
      </Button>
    </section>
  );
}

function isFinished(result: CheckView | null): result is CheckView & {
  product: NonNullable<CheckView["product"]>;
} {
  return result !== null && result.status === "done" && !!result.product;
}

export function CheckResultView({ id }: { id: string }) {
  const { api, toast } = useApp();
  const [result, setResult] = useState<CheckView | null | undefined>(undefined);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  useEffect(() => {
    void api.getCheck(id).then(setResult);
    void api.getFeedback(id).then(setFeedback);
  }, [api, id]);

  if (result === undefined) return <ResultSkeleton />;
  if (!isFinished(result)) return <ResultUnavailable result={result} />;

  const { product, unit, matches, uncertain, hidden_mismatches, demo } = result;
  const visible = [...matches, ...uncertain];
  const first = visible[0];

  async function saveFeedback(f: Feedback) {
    await api.submitFeedback(id, f);
    setFeedback(f);
    setFeedbackOpen(false);
    toast.show("Saved! Thanks for telling us.");
  }

  return (
    <div className="mx-auto max-w-[1312px] px-4 py-6 sm:px-8 sm:py-9 lg:px-16">
      <div className="flex items-center justify-between text-sm text-muted">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 hover:text-ink"
        >
          <ArrowLeft className="size-4" aria-hidden /> Check another product
        </Link>
        <span>{checkedAgo(result.completed_at)}</span>
      </div>

      <ProductHeader result={result} />

      {!first && (
        <div className="mt-8">
          <Callout tone="negative" title="No options to recommend">
            Every option has a critical measurement mismatch.
          </Callout>
        </div>
      )}

      <OptionGroup
        title="Matches"
        hint="One size clearly fits, with nothing known against it."
        options={matches}
        unit={unit}
        brand={product.brand}
      />
      <OptionGroup
        title="Check before buying"
        hint="Between sizes, an additional concern, or not enough evidence."
        options={uncertain}
        unit={unit}
        brand={product.brand}
      />
      <HiddenMismatches {...hidden_mismatches} />

      {first && (
        <FeedbackSection
          feedback={feedback}
          dimension={feedbackDimension(first)}
          onOpen={() => setFeedbackOpen(true)}
        />
      )}

      {demo && (
        <Card className="mt-8 p-6">
          <DemoSizeChart chart={demo.chart} />
        </Card>
      )}

      {/* Mounted only while open, so every opening starts blank. */}
      {feedbackOpen && first && (
        <FeedbackDialog
          open
          onOpenChange={setFeedbackOpen}
          optionRank={first.rank}
          dimension={feedbackDimension(first)}
          subtitle={`${product.name} · ${first.seller.name} · ${fmtMoney(first.total_cents, first.price_check.currency)}`}
          onSave={saveFeedback}
        />
      )}
    </div>
  );
}

export function ResultSkeleton() {
  return (
    <div
      className="mx-auto max-w-[1312px] animate-pulse px-4 py-9 sm:px-8 lg:px-16"
      aria-busy
      aria-label="Loading result"
    >
      <div className="h-4 w-40 rounded bg-subtle" />
      <div className="mt-8 flex gap-6">
        <div className="size-28 rounded-lg bg-subtle" />
        <div className="flex-1 space-y-3">
          <div className="h-3 w-24 rounded bg-subtle" />
          <div className="h-9 w-2/3 rounded bg-subtle" />
        </div>
      </div>
      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-80 rounded-xl bg-subtle" />
        ))}
      </div>
    </div>
  );
}

function ResultUnavailable({ result }: { result: CheckView | null }) {
  const message =
    result === null
      ? "We couldn’t find this check. It may have been made in another browser."
      : result.status === "failed"
        ? (result.error ?? "This check didn’t finish.")
        : result.status === "cancelled"
          ? "This check was cancelled."
          : "This check is still running.";
  return (
    <div className="mx-auto max-w-[640px] px-4 py-20 text-center">
      <h1 className="font-serif text-4xl">No result here.</h1>
      <p className="mt-4 text-muted">{message}</p>
      <ButtonLink href="/" className="mt-8">
        Check a product
      </ButtonLink>
    </div>
  );
}
