"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useApp } from "@/app/providers";
import { DemoSizeChart } from "@/components/results/DemoSizeChart";
import { Button, cx } from "@/components/ui/primitives";
import {
  ApiError,
  type ApiClient,
  type FitMode,
  type Profile,
  type ProfileIn,
  type QuickSize,
} from "@/lib/api";
import catalog from "@/lib/api/mock/catalog.json";
import { DEMO_CHART, DEMO_PRODUCTS } from "@/lib/api/mock/demo";
import { capitalize, fmtLengthWithUnit } from "@/lib/format";
import {
  readSelectedShop,
  SHOPS,
  shopForUrl,
  writeSelectedShop,
  type Shop,
} from "@/lib/shops";
import { ChipGroup } from "./ChipGroup";

const MODES = [
  { value: "quick_fit", label: "Quick Fit" },
  { value: "personal_fit", label: "Personal Fit" },
];
// Quick Fit sizes come from the generated catalog; the categories shown are a homepage choice (§2.11).
const SIZE_CHIPS = catalog.quick_sizes.map((s) => ({ value: s, label: s }));
const SIZE_ROWS = [
  { category: "tops", legend: "Tops" },
  { category: "bottoms", legend: "Bottoms" },
] as const;
type Sizes = Partial<Record<"tops" | "bottoms", QuickSize>>;

const SHOP_CHIPS = SHOPS.map((s) =>
  s.status === "active"
    ? { value: s.id, label: s.name, hint: s.demo ? "(demo shop)" : undefined }
    : { value: s.id, label: s.name, hint: "(coming soon)", disabled: true },
);

/** The reason a link can't be analyzed in the prototype, before any backend action. */
function shopError(url: string, selected: Shop): string | null {
  const shop = shopForUrl(url);
  if (shop?.id === selected.id) return null;
  if (shop)
    return `${shop.name} is coming soon. This prototype analyzes ${selected.name} sample products.`;
  return `That link isn't from ${selected.name}. Try one of the sample products.`;
}

function measurementsSummary(profile: Profile): string {
  return profile.measurements
    .map(
      (m) =>
        `${capitalize(m.dimension)} ${fmtLengthWithUnit(m.value, profile.unit)}`,
    )
    .join(" · ");
}

function profileBody(mode: FitMode, sizes: Sizes): ProfileIn {
  // Personal Fit sends only the mode, so saved sizes and measurements stay as they are.
  return mode === "personal_fit"
    ? { fit_mode: mode }
    : { fit_mode: mode, size_system: "eu", quick_sizes: sizes };
}

/** What stops this form from being submitted, in the order a person would fix it. */
function formError(
  api: ApiClient,
  url: string,
  shop: Shop,
  mode: FitMode,
  sizes: Sizes,
  profile: Profile | null,
): string | null {
  if (!url) return "Paste a product link first.";
  if (api.mode === "mock") {
    const error = shopError(url, shop);
    if (error) return error;
  }
  if (mode === "quick_fit" && !Object.keys(sizes).length)
    return "Pick your Tops or Bottoms size.";
  if (mode === "personal_fit" && !profile?.measurements.length)
    return "Add your measurements first, or use Quick Fit.";
  return null;
}

export function CheckForm({
  onStarted,
}: {
  onStarted: (id: string, url: string) => void;
}) {
  const { api, profile, reloadProfile } = useApp();
  const [url, setUrl] = useState("");
  const [shop, setShop] = useState<Shop>(readSelectedShop);
  const [mode, setMode] = useState<FitMode>(profile?.fit_mode ?? "quick_fit");
  const [sizes, setSizes] = useState<Sizes>(() => {
    const { tops, bottoms } = profile?.quick_sizes ?? {};
    return { ...(tops && { tops }), ...(bottoms && { bottoms }) };
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isMock = api.mode === "mock";

  function selectShop(id: string) {
    const next = SHOPS.find((s) => s.id === id && s.status === "active");
    if (!next) return;
    setShop(next);
    writeSelectedShop(next.id);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const link = url.trim();
    const problem = formError(api, link, shop, mode, sizes, profile);
    setError(problem);
    if (problem) return;
    setSubmitting(true);
    try {
      await api.saveProfile(profileBody(mode, sizes));
      await reloadProfile();
      const { id } = await api.createCheck(
        link,
        isMock ? { shopId: shop.id } : {},
      );
      onStarted(id, link);
      setUrl("");
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

  return (
    <form onSubmit={submit} className="mt-7 space-y-5" noValidate>
      {isMock && (
        <div>
          <ChipGroup
            legend="Shop"
            name="shop"
            chips={SHOP_CHIPS}
            value={shop.id}
            onChange={selectShop}
          />
          <p className="mt-2 text-xs text-muted">
            {shop.name} is a fictional demonstration shop. Gray shops are coming
            soon.
          </p>
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer text-muted underline underline-offset-4 hover:text-ink">
              View the demo size chart
            </summary>
            <DemoSizeChart chart={DEMO_CHART} className="mt-3" />
          </details>
        </div>
      )}

      <div>
        <label htmlFor="product-url" className="sr-only">
          Product link
        </label>
        <div
          className={cx(
            "flex h-12 w-full items-center gap-3 rounded-lg border bg-frame px-4 focus-within:border-ink sm:h-14",
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
        {isMock && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>Try a sample:</span>
            {DEMO_PRODUCTS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setUrl(p.input_url);
                  setError(null);
                }}
                className="rounded-full border border-line bg-frame px-3 py-1 text-ink hover:border-ink/40"
              >
                {p.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <ChipGroup
        legend="Fit mode"
        name="fit-mode"
        chips={MODES}
        value={mode}
        onChange={(v) => setMode(v as FitMode)}
      />

      {mode === "quick_fit" ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {SIZE_ROWS.map(({ category, legend }) => (
            <ChipGroup
              key={category}
              legend={legend}
              name={`size-${category}`}
              chips={SIZE_CHIPS}
              value={sizes[category] ?? null}
              onChange={(v) =>
                setSizes((cur) => ({ ...cur, [category]: v as QuickSize }))
              }
            />
          ))}
        </div>
      ) : (
        <p className="flex items-baseline justify-between gap-4 rounded-lg bg-subtle px-4 py-3 text-sm">
          <span className="num">
            {profile?.measurements.length
              ? measurementsSummary(profile)
              : "No measurements saved yet."}
          </span>
          <Link
            href="/preferences"
            className="shrink-0 underline underline-offset-4 hover:text-muted"
          >
            {profile?.measurements.length ? "Edit" : "Add"}
          </Link>
        </p>
      )}

      <div>
        <Button
          type="submit"
          className="h-12 w-full sm:w-auto"
          disabled={submitting}
        >
          {submitting ? "Starting…" : "Analyze product"}
        </Button>
        <p
          id="product-url-help"
          role={error ? "alert" : undefined}
          className={cx("mt-3 text-xs", error ? "text-skip" : "text-muted")}
        >
          {error ??
            (isMock
              ? "Prototype with sample data. No sign-in needed."
              : "Works with most fashion retailers. No sign-in to the store needed.")}
        </p>
      </div>
    </form>
  );
}
