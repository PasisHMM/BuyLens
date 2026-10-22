"use client";

import { ArrowLeft, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useApp } from "@/app/providers";
import {
  Button,
  ButtonLink,
  cx,
  ProductImage,
  VERDICT_STYLE,
  VerdictBadge,
} from "@/components/ui/primitives";
import type { CheckResult, Feedback, OptionOut, Verdict } from "@/lib/api";
import { DIMENSION_NOUN, fmtMoney } from "@/lib/format";
import { FitCheckCard, PriceCheckCard, SellerRiskCard } from "./cards";
import { FeedbackDialog, feedbackSummary } from "./FeedbackDialog";

const VERDICTS: Verdict[] = ["BUY", "CONSIDER", "SKIP"];

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

function shortSeller(option: OptionOut, brand: string | null): string {
  return option.seller_risk.is_official && brand
    ? brand
    : option.seller.name.split(":")[0];
}

/** The dimension feedback asks about: the one we couldn't confirm, else one that looked off. */
function feedbackDimension(option: OptionOut): string | null {
  const row =
    option.fit_check.rows.find((r) => r.match === "missing") ??
    option.fit_check.rows.find((r) => r.match !== "ok") ??
    null;
  return row ? row.dimension : null;
}

function decisionHint(
  result: CheckResult,
  option: OptionOut,
  seller: string,
): string {
  const missing = option.fit_check.rows
    .filter((r) => r.match === "missing")
    .map((r) => DIMENSION_NOUN[r.dimension]);
  const freeReturns =
    option.seller_risk.return_policy.verified &&
    option.seller_risk.return_policy.free;
  if (result.verdict === "SKIP")
    return "We’d pass on this one. Check another product or compare the options above.";
  if (result.verdict === "BUY")
    return freeReturns
      ? "Everything checks out, and returns are free if it doesn’t work out."
      : "Everything checks out.";
  if (missing.length)
    return `Ask ${seller} for the ${missing.join(" and ")} measurement${freeReturns ? ", or use the free return window" : ""}.`;
  return "Look over the trade-offs above before you order.";
}

export function CheckResultView({ id }: { id: string }) {
  const { api, toast } = useApp();
  const [result, setResult] = useState<CheckResult | null | undefined>(
    undefined,
  );
  const [selected, setSelected] = useState(1);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  useEffect(() => {
    void api.getCheck(id).then(setResult);
    void api.getFeedback(id).then(setFeedback);
  }, [api, id]);

  if (result === undefined) return <ResultSkeleton />;
  if (
    result === null ||
    result.status !== "done" ||
    !result.verdict ||
    !result.product
  ) {
    return <ResultUnavailable result={result} />;
  }

  const product = result.product;
  const verdict = result.verdict;
  const options = result.options;
  const option = options.find((o) => o.rank === selected) ?? options[0];
  const others = options.filter((o) => o.rank !== option.rank);
  const seller = shortSeller(option, product.brand);
  const attrs = product.attributes as Record<string, unknown>;
  const facts = [
    attrs.wash as string | undefined,
    result.selected_size ?? undefined,
    attrs.stretch === false
      ? "Non-stretch"
      : attrs.stretch === true
        ? "Stretch"
        : undefined,
  ].filter(Boolean);
  const vs = VERDICT_STYLE[verdict];
  const dimension = feedbackDimension(
    options.find((o) => o.rank === (feedback?.option_rank ?? selected)) ??
      option,
  );
  const dimensionNoun = dimension
    ? dimension === "hips"
      ? "hips"
      : DIMENSION_NOUN[dimension]
    : null;

  async function saveFeedback(f: Feedback) {
    await api.submitFeedback(id, f);
    setFeedback(f);
    setFeedbackOpen(false);
    toast.show("Saved! Future verdicts updated.");
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

      {/* Product header */}
      <div className="mt-7 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex gap-4 sm:gap-6">
          <ProductImage name={product.name} />
          <div className="min-w-0">
            <p className="eyebrow text-muted">
              {[product.brand, product.category].filter(Boolean).join(" · ")}
            </p>
            <h1 className="mt-2 font-serif text-[26px] leading-tight sm:mt-3 sm:text-[40px]">
              {product.name}
            </h1>
            <p className="mt-2 text-sm text-muted">{facts.join(" · ")}</p>
            {typeof attrs.source === "string" && (
              <p className="mt-2 hidden text-xs text-muted sm:block">
                {attrs.source}
              </p>
            )}
          </div>
        </div>
        <div className="lg:text-right">
          <p className="eyebrow hidden font-normal text-muted lg:block">
            Our verdict scale
          </p>
          <div className="mt-2 flex gap-2" aria-label="Verdict scale">
            {VERDICTS.map((v) => (
              <VerdictBadge
                key={v}
                verdict={v}
                className={v === verdict ? "ring-1 ring-current" : ""}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Verdict banner */}
      <section
        className={cx(
          "mt-6 rounded-[var(--radius-card)] px-6 py-6 sm:px-7 sm:py-7 lg:flex lg:gap-14",
          vs.bg,
        )}
      >
        <div className="shrink-0">
          <p className={cx("eyebrow font-normal", vs.text)}>Your verdict</p>
          <p
            className={cx(
              "mt-1.5 text-[40px] leading-none font-light tracking-wide",
              vs.text,
            )}
          >
            {verdict}
          </p>
        </div>
        <div className="mt-5 lg:mt-1">
          <h2 className="text-lg sm:text-xl">{result.headline}</h2>
          <p className="mt-2 text-sm leading-relaxed">{result.explanation}</p>
        </div>
      </section>

      {/* Options */}
      <section className="mt-8">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <h2 className="text-xl sm:text-2xl">
            Your{" "}
            {options.length === 1
              ? "best option"
              : `${options.length} best options`}
          </h2>
          <p className="text-xs text-muted">
            Ranked by overall value, not just lowest price.
          </p>
        </div>

        {options.length > 1 && (
          <div
            role="tablist"
            aria-label="Options"
            className="mt-4 grid gap-1 rounded-xl bg-subtle p-1"
            style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}
          >
            {options.map((o) => (
              <button
                key={o.rank}
                role="tab"
                type="button"
                aria-selected={o.rank === option.rank}
                onClick={() => setSelected(o.rank)}
                className={cx(
                  "h-11 rounded-lg text-sm transition-colors",
                  o.rank === option.rank
                    ? "border border-line bg-frame font-semibold"
                    : "text-muted hover:text-ink",
                )}
              >
                Option {o.rank}
                {o.rank === 1 && " (Best)"}
              </button>
            ))}
          </div>
        )}

        <p className="mt-4 text-sm sm:flex sm:gap-6">
          <span className="font-semibold">
            {option.seller.name} ·{" "}
            <span className="num">
              {fmtMoney(option.total_cents, option.price_check.currency)}
            </span>{" "}
            total
          </span>
          <span className="mt-1 block text-xs text-muted sm:mt-0 sm:self-center">
            {option.summary}
          </span>
        </p>

        <div role="tabpanel" className="mt-6 grid gap-4 lg:grid-cols-3">
          <PriceCheckCard price={option.price_check} />
          <FitCheckCard fit={option.fit_check} unit={result.unit} />
          <SellerRiskCard risk={option.seller_risk} brand={product.brand} />
        </div>

        {others.length > 0 && (
          <div className="mt-6 flex flex-col gap-2 rounded-xl bg-subtle px-5 py-4 text-sm lg:flex-row lg:items-center lg:gap-6">
            <span className="eyebrow font-normal text-muted">
              Also compared
            </span>
            {others.map((o) => (
              <button
                key={o.rank}
                type="button"
                onClick={() => setSelected(o.rank)}
                className="text-left hover:underline lg:flex-1"
              >
                Option {o.rank} · {o.seller.name.split(":")[0]} ·{" "}
                <span className="num">
                  {fmtMoney(o.total_cents, o.price_check.currency)}
                </span>{" "}
                total · {o.summary.replace(/\.$/, "")}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Decision */}
      <section className="mt-8 flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          {feedback ? (
            <>
              <p className="text-[15px]">
                Thanks. Your experience makes the next check better.
              </p>
              <p className="mt-1 text-sm text-muted">
                {feedbackSummary(feedback, dimensionNoun)} Saved for future
                checks.
              </p>
            </>
          ) : (
            <>
              <p className="text-[15px]">Make the call with confidence.</p>
              <p className="mt-1 text-sm text-muted">
                {decisionHint(result, option, seller)}
              </p>
            </>
          )}
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          {feedback ? (
            <ButtonLink href="/" variant="secondary">
              Check another product
            </ButtonLink>
          ) : (
            <Button variant="secondary" onClick={() => setFeedbackOpen(true)}>
              Did you buy this item?
            </Button>
          )}
          <ButtonLink href={option.url} external>
            View at {seller} <ArrowUpRight className="size-4" aria-hidden />
          </ButtonLink>
        </div>
      </section>

      {result.why_not && (result.why_not.buy || result.why_not.skip) && (
        <p className="mt-6 text-[11px] leading-relaxed text-muted">
          {result.why_not.buy && <>Why not BUY? {result.why_not.buy} </>}
          {result.why_not.skip && <>Why not SKIP? {result.why_not.skip} </>}
          Recommendations aren’t fit guarantees.
        </p>
      )}

      {/* Mounted only while open, so every opening starts blank. */}
      {feedbackOpen && (
        <FeedbackDialog
          open
          onOpenChange={setFeedbackOpen}
          optionRank={option.rank}
          dimension={dimensionNoun}
          subtitle={`${product.brand ? `${product.brand} ` : ""}${product.name}${result.selected_size ? ` ${result.selected_size}` : ""} · ${option.seller.name} · ${fmtMoney(option.total_cents, option.price_check.currency)}`}
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
      <div className="mt-6 h-32 rounded-xl bg-subtle" />
      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-80 rounded-xl bg-subtle" />
        ))}
      </div>
    </div>
  );
}

function ResultUnavailable({ result }: { result: CheckResult | null }) {
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
      <h1 className="font-serif text-4xl">No verdict here.</h1>
      <p className="mt-4 text-muted">{message}</p>
      <ButtonLink href="/" className="mt-8">
        Check a product
      </ButtonLink>
    </div>
  );
}
