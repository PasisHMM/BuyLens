"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { useApp } from "@/app/providers";
import { Button, Card, cx } from "@/components/ui/primitives";
import {
  errorMessage,
  type Basis,
  type Brand,
  type Catalog,
  type MeasurementIn,
  type Profile,
  type Unit,
} from "@/lib/api";
import { fmtNumber, fromCm, toCm } from "@/lib/format";
import { BrandChips } from "./BrandChips";
import { RulerIllustration } from "./RulerIllustration";

type Dim = MeasurementIn["dimension"];
type Field = { id: Dim; label: string; help: string; min: number; max: number };
type Entry = { value: string; basis: Basis; note: string };
type Entries = Partial<Record<Dim, Entry>>;
const EMPTY: Entry = { value: "", basis: "body", note: "" };

const HOW_TO: Partial<Record<Dim, string>> = {
  chest: "Around the fullest part of your chest.",
  waist: "Around your natural waist.",
  hips: "Around the fullest part of your hips.",
  shoulders: "Across your back, shoulder to shoulder.",
  inseam: "From inner leg to ankle.",
};

function fieldsFrom(catalog: Catalog): Field[] {
  // Only measurements a fit rule uses are asked for.
  return catalog.dimensions.flatMap((d) => {
    const critical = catalog.categories.filter((c) => c.critical.includes(d.id));
    const secondary = catalog.categories.filter((c) =>
      c.secondary.includes(d.id),
    );
    if (!critical.length && !secondary.length) return [];
    const uses = [
      critical.length &&
        `Critical for ${critical.map((c) => c.label).join(", ")}.`,
      secondary.length &&
        `Secondary for ${secondary.map((c) => c.label).join(", ")}.`,
    ].filter(Boolean);
    return [
      {
        id: d.id,
        label: d.label,
        help: [HOW_TO[d.id], ...uses].filter(Boolean).join(" "),
        min: d.min_cm,
        max: d.max_cm,
      },
    ];
  });
}

function initialEntries(profile: Profile | null): Entries {
  return Object.fromEntries(
    (profile?.measurements ?? []).map((m) => [
      m.dimension,
      { value: fmtNumber(m.value), basis: m.basis, note: m.note ?? "" },
    ]),
  );
}

function initialForm(profile: Profile | null) {
  return {
    unit: profile?.unit ?? ("cm" as Unit),
    entries: initialEntries(profile),
    brands: profile?.brands ?? [],
  };
}

function parse(raw: string): number | null {
  const n = Number(raw.replace(",", "."));
  return raw.trim() && Number.isFinite(n) ? n : null;
}

function validate(
  fields: Field[],
  entries: Entries,
  unit: Unit,
): Partial<Record<Dim, string>> {
  const errors: Partial<Record<Dim, string>> = {};
  for (const { id, label, min, max } of fields) {
    const raw = entries[id]?.value ?? "";
    if (!raw.trim()) continue;
    const n = parse(raw);
    if (n == null || n <= 0) {
      errors[id] = "Use a number, like 66 or 66.5.";
      continue;
    }
    const cm = toCm(n, unit);
    if (cm < min || cm > max)
      errors[id] = `${label.split(" /")[0]} looks off. Check the unit (IN / cm).`;
  }
  return errors;
}

function toMeasurements(fields: Field[], entries: Entries): MeasurementIn[] {
  return fields.flatMap(({ id }) => {
    const entry = entries[id];
    const value = entry ? parse(entry.value) : null;
    if (!entry || value == null) return [];
    const note = entry.basis === "garment" ? entry.note.trim() : "";
    return [{ dimension: id, value, basis: entry.basis, note: note || null }];
  });
}

function convertEntries(entries: Entries, next: Unit): Entries {
  return Object.fromEntries(
    Object.entries(entries).map(([dim, entry]) => {
      const n = parse(entry.value);
      const value =
        n == null
          ? entry.value
          : fmtNumber(next === "cm" ? toCm(n, "in") : fromCm(n, "in"));
      return [dim, { ...entry, value }];
    }),
  );
}

function Intro({ waist, unit }: { waist: string | undefined; unit: Unit }) {
  return (
    <section>
      <p className="eyebrow text-muted">A little about you</p>
      <h1 className="mt-4 font-serif text-[40px] leading-[1.1] tracking-tight sm:mt-8 sm:text-[60px]">
        Better buys start with your fit.
      </h1>
      <p className="mt-5 max-w-[420px] text-base leading-relaxed text-muted sm:mt-8">
        Sizes vary. Your measurements don’t. Add the ones you know; anything
        missing makes a result uncertain, never wrong.
      </p>
      <div className="hidden lg:block">
        <RulerIllustration value={parse(waist ?? "")} unit={unit} />
        <p className="mt-6 max-w-[420px] text-xs leading-relaxed text-muted">
          Private by design. Your profile is used only to personalize your
          product checks.
        </p>
      </div>
    </section>
  );
}

function FieldGrid({
  fields,
  unit,
  entries,
  errors,
  onChange,
}: {
  fields: Field[];
  unit: Unit;
  entries: Entries;
  errors: Partial<Record<Dim, string>>;
  onChange: (dim: Dim, change: Partial<Entry>) => void;
}) {
  return (
    <div className="mt-7 grid gap-x-4 gap-y-6 sm:grid-cols-2">
      {fields.map((f) => (
        <MeasurementField
          key={f.id}
          field={f}
          unit={unit}
          entry={entries[f.id] ?? EMPTY}
          error={errors[f.id]}
          onChange={(change) => onChange(f.id, change)}
        />
      ))}
    </div>
  );
}

function SaveRow({ saving, error }: { saving: boolean; error: string | null }) {
  return (
    <>
      {error && (
        <p role="alert" className="mt-6 text-sm text-skip">
          {error}
        </p>
      )}
      <Button type="submit" className="mt-8 w-full" disabled={saving}>
        {saving ? "Saving…" : "Save & Continue"}
      </Button>
      <p className="mt-4 text-center text-xs text-muted">
        You can update these anytime.
      </p>
    </>
  );
}

function UnitSwitch({
  unit,
  onChange,
}: {
  unit: Unit;
  onChange: (unit: Unit) => void;
}) {
  return (
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
            onClick={() => onChange(u)}
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
  );
}

export function MeasurementsForm() {
  const { api, profile, profileLoaded } = useApp();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api.getMeasurements().then(setCatalog, () => setFailed(true));
  }, [api]);

  if (failed)
    return (
      <p role="alert" className="mx-auto max-w-[640px] px-4 py-20 text-center">
        We couldn’t load the measurement list. Please reload the page.
      </p>
    );
  if (!profileLoaded || !catalog)
    return <div className="min-h-[70vh]" aria-busy />;
  return (
    <Form
      key={profile?.updated_at ?? "new"}
      profile={profile}
      fields={fieldsFrom(catalog)}
    />
  );
}

function Form({ profile, fields }: { profile: Profile | null; fields: Field[] }) {
  const router = useRouter();
  const { api, reloadProfile } = useApp();
  const start = initialForm(profile);
  const [unit, setUnit] = useState<Unit>(start.unit);
  const [entries, setEntries] = useState<Entries>(start.entries);
  const [brands, setBrands] = useState<Brand[]>(start.brands);
  const [errors, setErrors] = useState<Partial<Record<Dim, string>>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const formId = useId();

  function switchUnit(next: Unit) {
    if (next === unit) return;
    setEntries((current) => convertEntries(current, next));
    setUnit(next);
    setErrors({});
  }

  function update(dim: Dim, change: Partial<Entry>) {
    setEntries((cur) => ({
      ...cur,
      [dim]: { ...(cur[dim] ?? EMPTY), ...change },
    }));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const found = validate(fields, entries, unit);
    setErrors(found);
    if (Object.keys(found).length) return;
    const measurements = toMeasurements(fields, entries);
    if (!measurements.length) {
      setSaveError("Add at least one measurement.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      // Quick Fit sizes aren't part of this request, so they stay saved.
      await api.saveProfile({
        fit_mode: "personal_fit",
        unit,
        measurements,
        brand_ids: brands.map((b) => b.id),
      });
      await reloadProfile();
      router.push("/");
    } catch (err) {
      setSaveError(errorMessage(err, "We couldn't save. Please try again."));
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-[1248px] gap-10 px-4 py-10 sm:px-8 lg:grid-cols-[1fr_minmax(0,640px)] lg:gap-16 lg:py-20">
      <Intro waist={entries.waist?.value} unit={unit} />

      <form id={formId} onSubmit={save} noValidate>
        <Card className="border-0 bg-transparent p-0 lg:border lg:bg-frame lg:p-8">
          <div className="flex items-center justify-between">
            <h2 className="text-xl">Your measurements</h2>
            <UnitSwitch unit={unit} onChange={switchUnit} />
          </div>

          <FieldGrid
            fields={fields}
            unit={unit}
            entries={entries}
            errors={errors}
            onChange={update}
          />

          <h3 className="mt-9 text-lg">Brands you like</h3>
          <p className="mt-1.5 text-sm text-muted">
            Optional. A preference, not a filter.
          </p>
          <div className="mt-4">
            <BrandChips selected={brands} onChange={setBrands} />
          </div>

          <SaveRow saving={saving} error={saveError} />
        </Card>
      </form>
    </div>
  );
}

function MeasurementField({
  field,
  unit,
  entry,
  error,
  onChange,
}: {
  field: Field;
  unit: Unit;
  entry: Entry;
  error?: string;
  onChange: (change: Partial<Entry>) => void;
}) {
  const id = useId();
  const name = field.label.split(" /")[0];
  return (
    <div>
      <label htmlFor={id} className="text-sm">
        {field.label}
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
          value={entry.value}
          onChange={(e) => onChange({ value: e.target.value })}
          aria-invalid={Boolean(error)}
          aria-describedby={`${id}-help`}
          className="num w-full bg-transparent text-2xl outline-none focus-visible:outline-none"
        />
        <span className="text-xs text-muted">{unit}</span>
      </div>
      <p
        id={`${id}-help`}
        className={cx("mt-2 text-xs", error ? "text-skip" : "text-muted")}
      >
        {error ?? field.help}
      </p>
      <div
        role="radiogroup"
        aria-label={`${name} is measured on`}
        className="mt-2 flex gap-3 text-xs"
      >
        {(["body", "garment"] as Basis[]).map((basis) => (
          <button
            key={basis}
            type="button"
            role="radio"
            aria-checked={entry.basis === basis}
            aria-label={`${name}: ${basis === "body" ? "Body" : "Garment"}`}
            onClick={() => onChange({ basis })}
            className={cx(
              "underline-offset-4",
              entry.basis === basis
                ? "font-semibold text-ink underline"
                : "text-muted hover:text-ink",
            )}
          >
            {basis === "body" ? "Body" : "Garment"}
          </button>
        ))}
      </div>
      {entry.basis === "garment" && (
        <input
          aria-label={`${name} garment note`}
          value={entry.note}
          maxLength={200}
          placeholder="Which garment? e.g. My blue jeans"
          onChange={(e) => onChange({ note: e.target.value })}
          className="mt-2 h-9 w-full rounded-lg border border-line bg-frame px-3 text-xs outline-none focus:border-ink"
        />
      )}
    </div>
  );
}
