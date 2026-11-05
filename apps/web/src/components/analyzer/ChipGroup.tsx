import { cx } from "@/components/ui/primitives";

export type Chip = {
  value: string;
  label: string;
  /** Read by screen readers after the label, such as "(coming soon)". */
  hint?: string;
  disabled?: boolean;
};

/** One choice from a row of chips. Native radios give arrow keys, and skip disabled chips for free. */
export function ChipGroup({
  legend,
  name,
  chips,
  value,
  onChange,
}: {
  legend: string;
  name: string;
  chips: Chip[];
  value: string | null;
  onChange: (value: string) => void;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-2 text-xs text-muted">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => {
          const checked = chip.value === value;
          return (
            <label
              key={chip.value}
              className={cx(
                "inline-flex min-h-9 items-center rounded-full border px-3.5 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ink",
                chip.disabled
                  ? "cursor-not-allowed border-line bg-subtle text-faint"
                  : checked
                    ? "cursor-pointer border-ink bg-btn-on text-white"
                    : "cursor-pointer border-line bg-frame text-ink hover:border-ink/40",
              )}
            >
              <input
                type="radio"
                className="sr-only"
                name={name}
                value={chip.value}
                checked={checked}
                disabled={chip.disabled}
                tabIndex={chip.disabled ? -1 : undefined}
                onChange={() => onChange(chip.value)}
              />
              {chip.label}
              {chip.hint && " "}
              {chip.hint && <span className="sr-only">{chip.hint}</span>}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
