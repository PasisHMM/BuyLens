import { fmtNumber } from "@/lib/format";
import type { Unit } from "@/lib/api";

/** "26 inches. Not 'small'." Ruler from the design, centred on the user's waist. */
export function RulerIllustration({
  value,
  unit,
}: {
  value: number | null;
  unit: Unit;
}) {
  const center = value ?? (unit === "in" ? 26 : 66);
  const span = unit === "in" ? 2 : 5; // labels at center ± span
  const majors = unit === "in" ? 4 : 10;
  const minorsPerMajor = unit === "in" ? 4 : 1;
  const ticks = majors * minorsPerMajor;
  const width = 430;
  const step = width / ticks;
  const start = Math.round(center) - span;
  const label =
    unit === "in" ? `${fmtNumber(center)} inches.` : `${fmtNumber(center)} cm.`;

  return (
    <figure
      className="mt-12 max-w-[430px] sm:mt-20"
      aria-label={`${label} Not small.`}
    >
      <svg viewBox={`0 0 ${width + 2} 40`} className="h-10 w-full" aria-hidden>
        {Array.from({ length: ticks + 1 }, (_, i) => {
          const major = i % minorsPerMajor === 0;
          return (
            <line
              key={i}
              x1={1 + i * step}
              x2={1 + i * step}
              y1={major ? 4 : 22}
              y2={40}
              stroke="currentColor"
              strokeWidth={1}
              className={major ? "text-ink" : "text-ink/70"}
            />
          );
        })}
      </svg>
      <figcaption className="mt-3 flex items-baseline justify-between text-xs text-muted">
        <span className="num">{fmtNumber(start)}</span>
        <span className="text-sm font-semibold text-ink">
          {label} Not “small”.
        </span>
        <span className="num">{fmtNumber(start + span * 2)}</span>
      </figcaption>
    </figure>
  );
}
