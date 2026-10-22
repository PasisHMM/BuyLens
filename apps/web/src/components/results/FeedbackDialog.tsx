"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Check, X } from "lucide-react";
import { useState } from "react";

import { Button, cx } from "@/components/ui/primitives";
import type { Feedback, FitOutcome, HeldBackReason } from "@/lib/api";

const REASONS: { id: HeldBackReason; label: string }[] = [
  { id: "price", label: "Price" },
  { id: "fit_concern", label: "Fit concern" },
  { id: "seller_risk", label: "Seller risk" },
];

export function fitOptions(
  dimension: string | null,
): { id: FitOutcome; label: string }[] {
  return [
    {
      id: "too_tight",
      label: dimension ? `Too tight at ${dimension}` : "Too tight",
    },
    { id: "fits_well", label: "Fits well" },
    { id: "too_loose", label: "Too loose" },
  ];
}

export function feedbackSummary(f: Feedback, dimension: string | null): string {
  if (f.purchased)
    return `Your fit feedback: ${fitOptions(dimension).find((o) => o.id === f.fit)!.label}.`;
  const labels = REASONS.filter((r) => f.reasons.includes(r.id)).map(
    (r) => r.label,
  );
  return labels.length
    ? `What held you back: ${labels.join(", ")}.`
    : "You didn't buy this one.";
}

export function FeedbackDialog({
  open,
  onOpenChange,
  subtitle,
  optionRank,
  dimension,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subtitle: string;
  optionRank: number;
  /** The dimension to ask about ("hips"), usually the one we couldn't confirm. */
  dimension: string | null;
  onSave: (feedback: Feedback) => Promise<void>;
}) {
  const [purchased, setPurchased] = useState<boolean | null>(null);
  const [fit, setFit] = useState<FitOutcome | null>(null);
  const [reasons, setReasons] = useState<HeldBackReason[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = purchased === true ? fit !== null : purchased === false;

  async function save() {
    if (!ready) return;
    setSaving(true);
    setError(null);
    try {
      await onSave(
        purchased
          ? {
              purchased: true,
              option_rank: optionRank,
              fit: fit!,
              fit_dimension: fit === "too_tight" ? dimension : null,
            }
          : { purchased: false, option_rank: optionRank, reasons },
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "We couldn't save your feedback.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[#19181d]/35" />
        <Dialog.Content className="fixed top-[8vh] left-1/2 z-50 max-h-[88vh] w-[calc(100%-32px)] max-w-[520px] -translate-x-1/2 overflow-auto rounded-2xl bg-bg p-6 shadow-2xl sm:top-[16vh] sm:p-9">
          <div className="flex items-start justify-between">
            <p className="eyebrow text-muted">A better next verdict</p>
            <Dialog.Close
              className="-mt-1 rounded p-1 text-muted hover:text-ink"
              aria-label="Close"
            >
              <X className="size-5" />
            </Dialog.Close>
          </div>
          <Dialog.Title className="mt-5 font-serif text-[32px] leading-tight sm:text-[36px]">
            Did you buy this item?
          </Dialog.Title>
          <Dialog.Description className="mt-2 text-sm text-muted">
            {subtitle}
          </Dialog.Description>

          <div
            className="mt-7 grid grid-cols-2 gap-3"
            role="radiogroup"
            aria-label="Did you buy this item?"
          >
            {[true, false].map((value) => (
              <button
                key={String(value)}
                type="button"
                role="radio"
                aria-checked={purchased === value}
                onClick={() => setPurchased(value)}
                className={cx(
                  "h-12 rounded-lg border text-[15px] transition-colors",
                  purchased === value
                    ? "border-btn-on bg-btn-on text-white"
                    : "border-line bg-frame hover:border-ink/40",
                )}
              >
                {value ? "Yes" : "No"}
              </button>
            ))}
          </div>

          {purchased === true && (
            <fieldset className="mt-7">
              <legend className="text-[15px]">How did it fit?</legend>
              <p className="mt-1.5 text-xs text-muted">
                Choose the closest fit.
              </p>
              <div
                className="mt-4 space-y-2.5"
                role="radiogroup"
                aria-label="How did it fit?"
              >
                {fitOptions(dimension).map((o) => (
                  <Choice
                    key={o.id}
                    kind="radio"
                    checked={fit === o.id}
                    onClick={() => setFit(o.id)}
                    label={o.label}
                  />
                ))}
              </div>
            </fieldset>
          )}

          {purchased === false && (
            <fieldset className="mt-7">
              <legend className="text-[15px]">What held you back?</legend>
              <p className="mt-1.5 text-xs text-muted">
                Select all that apply.
              </p>
              <div className="mt-4 space-y-2.5">
                {REASONS.map((r) => (
                  <Choice
                    key={r.id}
                    kind="checkbox"
                    checked={reasons.includes(r.id)}
                    onClick={() =>
                      setReasons((cur) =>
                        cur.includes(r.id)
                          ? cur.filter((x) => x !== r.id)
                          : [...cur, r.id],
                      )
                    }
                    label={r.label}
                  />
                ))}
              </div>
            </fieldset>
          )}

          {error && (
            <p role="alert" className="mt-5 text-sm text-skip">
              {error}
            </p>
          )}
          <Button
            className="mt-7 w-full"
            onClick={save}
            disabled={!ready || saving}
          >
            {saving ? "Saving…" : "Save feedback"}
          </Button>
          <p className="mt-4 text-center text-xs text-muted">
            Only used to improve your future verdicts. Not posted as a public
            review.
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Choice({
  kind,
  checked,
  onClick,
  label,
}: {
  kind: "radio" | "checkbox";
  checked: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role={kind}
      aria-checked={checked}
      onClick={onClick}
      className={cx(
        "flex h-12 w-full items-center gap-3 rounded-lg border px-4 text-left text-sm transition-colors",
        checked
          ? "border-ink bg-subtle"
          : "border-line bg-frame hover:border-ink/40",
      )}
    >
      {kind === "radio" ? (
        <span
          className={cx(
            "flex size-[18px] items-center justify-center rounded-full border",
            checked ? "border-ink" : "border-faint",
          )}
        >
          {checked && <span className="size-2.5 rounded-full bg-ink" />}
        </span>
      ) : (
        <span
          className={cx(
            "flex size-[18px] items-center justify-center rounded border",
            checked ? "border-ink bg-ink text-white" : "border-faint",
          )}
        >
          {checked && <Check className="size-3" strokeWidth={3} />}
        </span>
      )}
      {label}
    </button>
  );
}
