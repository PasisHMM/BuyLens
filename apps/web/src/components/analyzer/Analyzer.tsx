"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useApp } from "@/app/providers";
import { OutcomeBadge, ProductImage } from "@/components/ui/primitives";
import type { CheckSummary } from "@/lib/api";
import { fmtMoney, hostOf } from "@/lib/format";
import { CheckForm } from "./CheckForm";
import { ProgressDialog } from "./ProgressDialog";

const VALUE_PROPS = [
  {
    n: "01",
    title: "The real price",
    body: "Listing + shipping, side by side in euros.",
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

function readableLink(url: string): string {
  try {
    const { pathname } = new URL(url.includes("://") ? url : `https://${url}`);
    const page = pathname.split("/").filter(Boolean).pop();
    return page ? `${hostOf(url)} / ${page}` : hostOf(url);
  } catch {
    return url;
  }
}

function RecentCheck({ recent }: { recent: CheckSummary }) {
  return (
    <Link
      href={`/checks/${recent.id}`}
      className="mt-12 flex items-center gap-4 rounded-xl bg-subtle p-4 hover:bg-[#e9e6e1] sm:mt-14"
    >
      <ProductImage name={recent.product_name ?? "Product"} size="sm" />
      <div className="min-w-0 flex-1">
        <p className="eyebrow font-normal text-muted">A recent check</p>
        <p className="mt-1 truncate text-[15px]">{recent.product_name}</p>
        <p className="num mt-1 text-sm text-muted">
          {recent.currency ? fmtMoney(recent.total_cents, recent.currency) : "Hidden"}
          {recent.selected_size && ` · ${recent.selected_size}`}
        </p>
      </div>
      {recent.fit_outcome && (
        <span className="hidden sm:block">
          <OutcomeBadge outcome={recent.fit_outcome} />
        </span>
      )}
    </Link>
  );
}

export function Analyzer() {
  const router = useRouter();
  const { api, profileLoaded } = useApp();
  const [runId, setRunId] = useState<string | null>(null);
  const [startedUrl, setStartedUrl] = useState("");
  const [recent, setRecent] = useState<CheckSummary | null>(null);

  useEffect(() => {
    void api.recentChecks(1).then((r) => setRecent(r[0] ?? null));
  }, [api, runId]);

  const onStarted = useCallback((id: string, url: string) => {
    setStartedUrl(url);
    setRunId(id);
  }, []);
  const onComplete = useCallback(
    (id: string) => {
      // Close the dialog first: Next keeps this page alive in the background, and a still-open
      // dialog would replay "complete" and navigate back here when the user returns.
      setRunId(null);
      router.push(`/checks/${id}`);
    },
    [router],
  );
  const onClose = useCallback(() => setRunId(null), []);
  const onCancel = useCallback(() => {
    if (runId) void api.cancelCheck(runId).catch(() => undefined);
    setRunId(null);
  }, [api, runId]);

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

      {/* Mounted once the saved profile is known, so the form starts from it. */}
      {profileLoaded ? (
        <CheckForm onStarted={onStarted} />
      ) : (
        <div className="mt-7 min-h-[320px]" aria-busy />
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

      {recent && <RecentCheck recent={recent} />}

      <ProgressDialog
        key={runId ?? "idle"}
        runId={runId}
        linkLabel={readableLink(startedUrl)}
        onCancel={onCancel}
        onComplete={onComplete}
        onClose={onClose}
      />
    </div>
  );
}
