"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useApp } from "@/app/providers";
import {
  Button,
  cx,
  ProductImage,
  VerdictBadge,
} from "@/components/ui/primitives";
import { ApiError, type CheckSummary } from "@/lib/api";
import { SAMPLE_LINKS } from "@/lib/api/mock/scenarios";
import { fmtLengthWithUnit, fmtMoney, hostOf } from "@/lib/format";
import { ProgressDialog } from "./ProgressDialog";

const VALUE_PROPS = [
  {
    n: "01",
    title: "The real price",
    body: "Listing + shipping, compared with the market.",
  },
  {
    n: "02",
    title: "The actual fit",
    body: "Numeric measurements, not a size label.",
  },
  {
    n: "03",
    title: "The fine print",
    body: "Seller reputation, reviews, and returns.",
  },
];

export function Analyzer() {
  const router = useRouter();
  const { api, profile, profileLoaded } = useApp();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [recent, setRecent] = useState<CheckSummary | null>(null);

  useEffect(() => {
    if (profileLoaded && !profile) router.replace("/preferences");
  }, [profileLoaded, profile, router]);

  useEffect(() => {
    void api.recentChecks(1).then((r) => setRecent(r[0] ?? null));
  }, [api, runId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) {
      setError("Paste a product link first.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const { id } = await api.createCheck(url.trim());
      setRunId(id);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const onComplete = useCallback(
    (id: string) => {
      // Close the dialog first: Next keeps this page alive in the background, and a still-open
      // dialog would replay "complete" and navigate back here when the user returns.
      setRunId(null);
      setUrl("");
      router.push(`/checks/${id}`);
    },
    [router],
  );
  const onClose = useCallback(() => setRunId(null), []);
  const onCancel = useCallback(() => {
    if (runId) void api.cancelCheck(runId).catch(() => undefined);
    setRunId(null);
  }, [api, runId]);

  const unit = profile?.unit ?? "in";
  const linkLabel = (() => {
    try {
      const u = new URL(url.includes("://") ? url : `https://${url}`);
      return `${hostOf(url)}${u.pathname.length > 1 ? ` / ${u.pathname.split("/").filter(Boolean).pop()}` : ""}`;
    } catch {
      return url;
    }
  })();

  return (
    <div className="mx-auto max-w-[992px] px-4 py-10 sm:px-8 sm:py-20">
      <p className="eyebrow text-muted">Less guesswork. Better buys.</p>
      <h1 className="mt-5 font-serif text-[44px] leading-[1.08] tracking-tight sm:mt-8 sm:text-[64px] sm:leading-[1.05]">
        Worth it? Let’s take a closer look.
      </h1>
      <p className="mt-5 text-base text-muted sm:mt-7">
        One link. A clear look at the price, your fit, and the seller — before
        you commit.
      </p>

      <form
        onSubmit={submit}
        className="mt-7 flex flex-col gap-2.5 sm:flex-row"
        noValidate
      >
        <label htmlFor="product-url" className="sr-only">
          Product link
        </label>
        <div
          className={cx(
            "flex h-12 w-full shrink-0 items-center gap-3 rounded-lg border bg-frame px-4 focus-within:border-ink sm:h-14 sm:flex-1",
            error ? "border-skip" : "border-line",
          )}
        >
          <ArrowUpRight className="size-4 shrink-0 text-muted" aria-hidden />
          <input
            id="product-url"
            type="url"
            inputMode="url"
            autoComplete="off"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Paste product link…"
            aria-invalid={Boolean(error)}
            aria-describedby="product-url-help"
            className="w-full bg-transparent text-[15px] outline-none placeholder:text-muted focus-visible:outline-none"
          />
        </div>
        <Button
          type="submit"
          className="h-12 sm:h-[50px] sm:self-center sm:px-6"
          disabled={submitting || !profile}
        >
          {submitting ? "Starting…" : "Check Product"}
        </Button>
      </form>
      <p
        id="product-url-help"
        role={error ? "alert" : undefined}
        className={cx("mt-4 text-xs", error ? "text-skip" : "text-muted")}
      >
        {error ??
          "Works with most fashion retailers. No sign-in to the store needed."}
      </p>

      {api.mode === "mock" && (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>Prototype · try a sample:</span>
          {SAMPLE_LINKS.map((s) => (
            <button
              key={s.url}
              type="button"
              onClick={() => {
                setUrl(s.url);
                setError(null);
              }}
              className="rounded-full border border-line bg-frame px-3 py-1 text-ink hover:border-ink/40"
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {profile && (
        <div className="mt-12 flex items-end justify-between border-y border-line py-5 sm:mt-14">
          <div>
            <p className="eyebrow font-normal text-muted">
              Checking against your profile
            </p>
            <p className="num mt-1.5 text-sm">
              Waist {fmtLengthWithUnit(profile.waist, unit)} · Inseam{" "}
              {fmtLengthWithUnit(profile.inseam, unit)}
              {profile.hips != null && (
                <> · Hips {fmtLengthWithUnit(profile.hips, unit)}</>
              )}
            </p>
          </div>
          <Link
            href="/preferences"
            className="text-sm underline underline-offset-4 hover:text-muted"
          >
            Edit
          </Link>
        </div>
      )}

      <div className="mt-12 grid gap-9 sm:mt-14 sm:grid-cols-3 sm:gap-8">
        {VALUE_PROPS.map((v) => (
          <div key={v.n}>
            <p className="font-serif text-3xl text-muted">{v.n}</p>
            <p className="mt-3 text-base font-semibold">{v.title}</p>
            <p className="mt-3 text-sm text-muted">{v.body}</p>
          </div>
        ))}
      </div>

      {recent && (
        <Link
          href={`/checks/${recent.id}`}
          className="mt-12 flex items-center gap-4 rounded-xl bg-subtle p-4 hover:bg-[#e9e6e1] sm:mt-14"
        >
          <ProductImage name={recent.product_name ?? "Product"} size="sm" />
          <div className="min-w-0 flex-1">
            <p className="eyebrow font-normal text-muted">A recent check</p>
            <p className="mt-1 truncate text-[15px]">{recent.product_name}</p>
            <p className="num mt-1 text-sm text-muted">
              {fmtMoney(recent.total_cents, recent.currency ?? "USD")}
              {recent.selected_size && ` · ${recent.selected_size}`}
            </p>
          </div>
          {recent.verdict && (
            <span className="hidden sm:block">
              <VerdictBadge verdict={recent.verdict} />
            </span>
          )}
        </Link>
      )}

      <ProgressDialog
        key={runId ?? "idle"}
        runId={runId}
        linkLabel={linkLabel}
        onCancel={onCancel}
        onComplete={onComplete}
        onClose={onClose}
      />
    </div>
  );
}
