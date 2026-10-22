"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { useApp } from "@/app/providers";
import { Button, Card, cx } from "@/components/ui/primitives";
import { ApiError, type Brand, type Profile, type Unit } from "@/lib/api";
import { fmtNumber, fromCm, toCm } from "@/lib/format";
import { BrandChips } from "./BrandChips";
import { RulerIllustration } from "./RulerIllustration";

type Dim = "waist" | "inseam" | "hips";
const PLAUSIBLE_CM: Record<Dim, [number, number]> = {
  waist: [45, 200],
  inseam: [40, 120],
  hips: [60, 200],
};
const FIELDS: {
  dim: Dim;
  label: string;
  help: string;
  placeholder: Record<Unit, string>;
  optional?: boolean;
}[] = [
  {
    dim: "waist",
    label: "Waist",
    help: "Around your natural waist",
    placeholder: { in: "26", cm: "66" },
  },
  {
    dim: "inseam",
    label: "Inseam",
    help: "From inner leg to ankle",
    placeholder: { in: "30", cm: "76" },
  },
  {
    dim: "hips",
    label: "Hips · optional",
    help: "Around the fullest part of your hips. Helps us flag a close fit.",
    placeholder: { in: "36", cm: "91" },
    optional: true,
  },
];

type Values = Record<Dim, string>;

function initial(profile: Profile | null): { unit: Unit; values: Values } {
  const v = (n: number | null | undefined) => (n == null ? "" : fmtNumber(n));
  return {
    unit: profile?.unit ?? "in",
    values: {
      waist: v(profile?.waist),
      inseam: v(profile?.inseam),
      hips: v(profile?.hips),
    },
  };
}

function parse(raw: string): number | null {
  const n = Number(raw.replace(",", "."));
  return raw.trim() && Number.isFinite(n) ? n : null;
}

function validate(values: Values, unit: Unit): Partial<Record<Dim, string>> {
  const errors: Partial<Record<Dim, string>> = {};
  for (const { dim, label, optional } of FIELDS) {
    const raw = values[dim];
    const name = label.split(" ·")[0];
    if (!raw.trim()) {
      if (!optional) errors[dim] = `Add your ${name.toLowerCase()}.`;
      continue;
    }
    const n = parse(raw);
    if (n == null || n <= 0) {
      errors[dim] = "Use a number, like 26 or 26.5.";
      continue;
    }
    const [lo, hi] = PLAUSIBLE_CM[dim];
    const cm = toCm(n, unit);
    if (cm < lo || cm > hi)
      errors[dim] = `${name} looks off. Check the unit (IN / cm).`;
  }
  return errors;
}

export function MeasurementsForm() {
  const { profile, profileLoaded } = useApp();
  if (!profileLoaded) return <div className="min-h-[70vh]" aria-busy />;
  return <Form key={profile?.updated_at ?? "new"} profile={profile} />;
}

function Form({ profile }: { profile: Profile | null }) {
  const router = useRouter();
  const { api, reloadProfile } = useApp();
  const [unit, setUnit] = useState<Unit>(() => initial(profile).unit);
  const [values, setValues] = useState<Values>(() => initial(profile).values);
  const [brands, setBrands] = useState<Brand[]>(profile?.brands ?? []);
  const [errors, setErrors] = useState<Partial<Record<Dim, string>>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const formId = useId();

  function switchUnit(next: Unit) {
    if (next === unit) return;
    setValues((current) => {
      const out = { ...current };
      for (const dim of Object.keys(out) as Dim[]) {
        const n = parse(out[dim]);
        if (n != null)
          out[dim] = fmtNumber(next === "cm" ? toCm(n, "in") : fromCm(n, "in"));
      }
      return out;
    });
    setUnit(next);
    setErrors({});
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const found = validate(values, unit);
    setErrors(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    setSaveError(null);
    try {
      await api.saveProfile({
        unit,
        waist: parse(values.waist)!,
        inseam: parse(values.inseam)!,
        hips: parse(values.hips),
        brand_ids: brands.map((b) => b.id),
      });
      await reloadProfile();
      router.push("/");
    } catch (err) {
      setSaveError(
        err instanceof ApiError
          ? err.message
          : "We couldn't save. Please try again.",
      );
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-[1248px] gap-10 px-4 py-10 sm:px-8 lg:grid-cols-[1fr_minmax(0,640px)] lg:gap-16 lg:py-20">
      <section>
        <p className="eyebrow text-muted">A little about you</p>
        <h1 className="mt-4 font-serif text-[40px] leading-[1.1] tracking-tight sm:mt-8 sm:text-[60px]">
          Better buys start with your fit.
        </h1>
        <p className="mt-5 max-w-[420px] text-base leading-relaxed text-muted sm:mt-8">
          Sizes vary. Your measurements don’t. Give us a starting point for
          advice that actually fits you.
        </p>
        <div className="hidden lg:block">
          <RulerIllustration value={parse(values.waist)} unit={unit} />
          <p className="mt-6 max-w-[420px] text-xs leading-relaxed text-muted">
            Private by design. Your profile is used only to personalize your
            product checks.
          </p>
        </div>
      </section>

      <form id={formId} onSubmit={save} noValidate>
        <Card className="border-0 bg-transparent p-0 lg:border lg:bg-frame lg:p-8">
          <div className="flex items-center justify-between">
            <h2 className="text-xl">Your measurements</h2>
            <div
              role="radiogroup"
              aria-label="Unit"
              className="flex items-center rounded-md bg-subtle px-1 py-0.5 text-xs"
            >
              {(["in", "cm"] as Unit[]).map((u, i) => (
                <span key={u} className="flex items-center">
                  {i > 0 && <span className="px-0.5 text-faint">/</span>}
                  <button
                    type="button"
                    role="radio"
                    aria-checked={unit === u}
                    onClick={() => switchUnit(u)}
                    className={cx(
                      "rounded px-1.5 py-1",
                      unit === u ? "font-semibold text-ink" : "text-muted",
                    )}
                  >
                    {u === "in" ? "IN" : "cm"}
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div className="mt-7 grid grid-cols-2 gap-x-4 gap-y-6">
            {FIELDS.map((f) => (
              <MeasurementField
                key={f.dim}
                className={f.dim === "hips" ? "col-span-2" : ""}
                label={f.label}
                help={f.help}
                unit={unit}
                placeholder={f.placeholder[unit]}
                value={values[f.dim]}
                error={errors[f.dim]}
                onChange={(v) => setValues((cur) => ({ ...cur, [f.dim]: v }))}
              />
            ))}
          </div>

          <h3 className="mt-9 text-lg">Brands you like</h3>
          <p className="mt-1.5 text-sm text-muted">
            Optional. A preference, not a filter.
          </p>
          <div className="mt-4">
            <BrandChips selected={brands} onChange={setBrands} />
          </div>

          {saveError && (
            <p role="alert" className="mt-6 text-sm text-skip">
              {saveError}
            </p>
          )}
          <Button type="submit" className="mt-8 w-full" disabled={saving}>
            {saving ? "Saving…" : "Save & Continue"}
          </Button>
          <p className="mt-4 text-center text-xs text-muted">
            You can update these anytime.
          </p>
        </Card>
      </form>
    </div>
  );
}

function MeasurementField({
  label,
  help,
  unit,
  value,
  placeholder,
  error,
  onChange,
  className,
}: {
  label: string;
  help: string;
  unit: Unit;
  value: string;
  placeholder: string;
  error?: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="text-sm">
        {label}
      </label>
      <div
        className={cx(
          "mt-2 flex h-[60px] items-center rounded-lg border bg-frame px-4 focus-within:border-ink",
          error ? "border-skip" : "border-line",
        )}
      >
        <input
          id={id}
          inputMode="decimal"
          autoComplete="off"
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={`${id}-help`}
          className="num w-full bg-transparent text-2xl outline-none placeholder:text-faint focus-visible:outline-none"
        />
        <span className="text-xs text-muted">{unit}</span>
      </div>
      <p
        id={`${id}-help`}
        className={cx("mt-2 text-xs", error ? "text-skip" : "text-muted")}
      >
        {error ?? help}
      </p>
    </div>
  );
}
