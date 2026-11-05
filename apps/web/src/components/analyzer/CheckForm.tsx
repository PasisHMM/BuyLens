"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useApp } from "@/app/providers";
import { DemoSizeChart } from "@/components/results/DemoSizeChart";
import { Button, cx } from "@/components/ui/primitives";
import {
  errorMessage,
  type ApiClient,
  type FitMode,
  type Profile,
  type ProfileIn,
  type QuickSize,
} from "@/lib/api";
import catalog from "@/lib/api/mock/catalog.json";
import {
  DEMO_CHART,
  DEMO_PRODUCTS,
  PERSONAL_SAMPLES,
} from "@/lib/api/mock/demo";
import { capitalize, fmtLengthWithUnit } from "@/lib/format";
import {
  activeShop,
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

const OWN = "own";
const SAMPLE_CHIPS = [
  { value: OWN, label: "My measurements" },
  ...PERSONAL_SAMPLES.map((s) => ({ value: s.id, label: s.label })),
];

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

function fitError(
  mode: FitMode,
  sizes: Sizes,
  profile: Profile | null,
  sample: string,
): string | null {
  if (mode === "quick_fit")
    return Object.keys(sizes).length ? null : "Pick your Tops or Bottoms size.";
  return sample === OWN && !profile?.measurements.length
    ? "Add your measurements first, or use Quick Fit."
    : null;
}

/** What stops this form from being submitted, in the order a person would fix it. */
function formError(
  api: ApiClient,
  url: string,
  shop: Shop,
  fit: string | null,
): string | null {
  if (!url) return "Paste a product link first.";
  const linkProblem = api.mode === "mock" ? shopError(url, shop) : null;
  return linkProblem ?? fit;
}

function ShopChoice({
  shop,
  onSelect,
}: {
  shop: Shop;
  onSelect: (id: string) => void;
}) {
  return (
    <div>
      <ChipGroup
        legend="Shop"
        name="shop"
        chips={SHOP_CHIPS}
        value={shop.id}
        onChange={onSelect}
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
  );
}

function LinkField({
  url,
  invalid,
  onChange,
}: {
  url: string;
  invalid: boolean;
  onChange: (url: string) => void;
}) {
  return (
    <>
      <label htmlFor="product-url" className="sr-only">
        Product link
      </label>
      <div
        className={cx(
          "flex h-12 w-full items-center gap-3 rounded-lg border bg-frame px-4 focus-within:border-ink sm:h-14",
          invalid ? "border-negative" : "border-line",
        )}
      >
        <ArrowUpRight className="size-4 shrink-0 text-muted" aria-hidden />
        <input
          id="product-url"
          type="url"
          inputMode="url"
          autoComplete="off"
          value={url}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Paste product link…"
          aria-invalid={invalid}
          aria-describedby="product-url-help"
          className="w-full bg-transparent text-[15px] outline-none placeholder:text-muted focus-visible:outline-none"
        />
      </div>
    </>
  );
}

function SampleLinks({ onPick }: { onPick: (url: string) => void }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
      <span>Try a sample:</span>
      {DEMO_PRODUCTS.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onPick(p.input_url)}
          className="rounded-full border border-line bg-frame px-3 py-1 text-ink hover:border-ink/40"
        >
          {p.name}
        </button>
      ))}
    </div>
  );
}

function LinkSection({
  url,
  invalid,
  showSamples,
  onChange,
  onPickSample,
}: {
  url: string;
  invalid: boolean;
  showSamples: boolean;
  onChange: (url: string) => void;
  onPickSample: (url: string) => void;
}) {
  return (
    <div>
      <LinkField url={url} invalid={invalid} onChange={onChange} />
      {showSamples && <SampleLinks onPick={onPickSample} />}
    </div>
  );
}

function SizeChoice({
  sizes,
  onChange,
}: {
  sizes: Sizes;
  onChange: (sizes: Sizes) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {SIZE_ROWS.map(({ category, legend }) => (
        <ChipGroup
          key={category}
          legend={legend}
          name={`size-${category}`}
          chips={SIZE_CHIPS}
          value={sizes[category] ?? null}
          onChange={(v) => onChange({ ...sizes, [category]: v as QuickSize })}
        />
      ))}
    </div>
  );
}

function PersonalSummary({ profile }: { profile: Profile | null }) {
  const saved = Boolean(profile?.measurements.length);
  return (
    <p className="flex items-baseline justify-between gap-4 rounded-lg bg-subtle px-4 py-3 text-sm">
      <span className="num">
        {saved ? measurementsSummary(profile!) : "No measurements saved yet."}
      </span>
      <Link
        href="/preferences"
        className="shrink-0 underline underline-offset-4 hover:text-muted"
      >
        {saved ? "Edit" : "Add"}
      </Link>
    </p>
  );
}

function SampleChoice({
  sample,
  onChange,
}: {
  sample: string;
  onChange: (sample: string) => void;
}) {
  return (
    <ChipGroup
      legend="Measurements to compare"
      name="personal-sample"
      chips={SAMPLE_CHIPS}
      value={sample}
      onChange={onChange}
    />
  );
}

function PersonalChoice({
  showSamples,
  sample,
  profile,
  onSample,
}: {
  showSamples: boolean;
  sample: string;
  profile: Profile | null;
  onSample: (sample: string) => void;
}) {
  return (
    <div className="space-y-3">
      {showSamples && <SampleChoice sample={sample} onChange={onSample} />}
      <PersonalSummary profile={profile} />
    </div>
  );
}

function chosenSample(mode: FitMode, sample: string): string | undefined {
  return mode === "personal_fit" && sample !== OWN ? sample : undefined;
}

function checkOptions(
  api: ApiClient,
  shop: Shop,
  sampleId: string | undefined,
): { shopId?: string; sampleId?: string } {
  if (api.mode !== "mock") return {};
  return sampleId ? { shopId: shop.id, sampleId } : { shopId: shop.id };
}

function initialSizes(profile: Profile | null): Sizes {
  const { tops, bottoms } = profile?.quick_sizes ?? {};
  return { ...(tops && { tops }), ...(bottoms && { bottoms }) };
}

const HELP = {
  mock: "Prototype with sample data. No sign-in needed.",
  live: "Works with most fashion retailers. No sign-in to the store needed.",
};

function SubmitRow({
  submitting,
  error,
  help,
}: {
  submitting: boolean;
  error: string | null;
  help: string;
}) {
  return (
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
        className={cx("mt-3 text-xs", error ? "text-negative" : "text-muted")}
      >
        {error ?? help}
      </p>
    </div>
  );
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
  const [sizes, setSizes] = useState<Sizes>(() => initialSizes(profile));
  const [sample, setSample] = useState(OWN);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isMock = api.mode === "mock";

  function selectShop(id: string) {
    const next = activeShop(id);
    if (!next) return;
    setShop(next);
    writeSelectedShop(next.id);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const link = url.trim();
    const problem = formError(
      api,
      link,
      shop,
      fitError(mode, sizes, profile, sample),
    );
    setError(problem);
    if (problem) return;
    setSubmitting(true);
    try {
      const sampleId = chosenSample(mode, sample);
      // Sample measurements only try the comparison: they never replace what someone saved.
      if (!sampleId) {
        await api.saveProfile(profileBody(mode, sizes));
        await reloadProfile();
      }
      const { id } = await api.createCheck(
        link,
        checkOptions(api, shop, sampleId),
      );
      onStarted(id, link);
      setUrl("");
    } catch (err) {
      setError(errorMessage(err, "Something went wrong. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-7 space-y-5" noValidate>
      {isMock && <ShopChoice shop={shop} onSelect={selectShop} />}

      <LinkSection
        url={url}
        invalid={Boolean(error)}
        showSamples={isMock}
        onChange={setUrl}
        onPickSample={(sample) => {
          setUrl(sample);
          setError(null);
        }}
      />

      <ChipGroup
        legend="Fit mode"
        name="fit-mode"
        chips={MODES}
        value={mode}
        onChange={(v) => setMode(v as FitMode)}
      />

      {mode === "quick_fit" ? (
        <SizeChoice sizes={sizes} onChange={setSizes} />
      ) : (
        <PersonalChoice
          showSamples={isMock}
          sample={sample}
          profile={profile}
          onSample={setSample}
        />
      )}

      <SubmitRow submitting={submitting} error={error} help={HELP[api.mode]} />
    </form>
  );
}
