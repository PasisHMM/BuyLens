import { cx } from "@/components/ui/primitives";
import type { DemoChart, DemoChartRange } from "@/lib/api";
import { fmtNumber } from "@/lib/format";

function range({ min_cm, max_cm }: DemoChartRange): string {
  return `${fmtNumber(min_cm)}–${fmtNumber(max_cm)}`;
}

/** Reference only: showing this chart doesn't make any fit result verified. */
export function DemoSizeChart({
  chart,
  className,
}: {
  chart: DemoChart;
  className?: string;
}) {
  return (
    <section className={cx("min-w-0", className)}>
      <h2 className="text-base font-semibold">{chart.title}</h2>
      <p className="mt-1 text-xs text-muted">{chart.disclaimer}</p>
      <p className="mt-1 text-xs text-muted">
        {chart.sizing_mode} sizing, body measurements.{" "}
        {chart.unavailable_modes.map((m) => `${m}: not available.`).join(" ")}
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="num w-full min-w-[480px] text-left text-xs">
          <thead>
            <tr className="border-b border-line text-muted">
              {["Size", "EUR", "UK", "Chest (cm)", "Waist (cm)", "Hips (cm)"].map(
                (h) => (
                  <th key={h} className="py-2 pr-3 font-normal">
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {chart.rows.map((r) => (
              <tr key={r.label} className="border-b border-line last:border-0">
                <td className="py-2 pr-3 font-semibold">{r.label}</td>
                <td className="py-2 pr-3">{r.eu}</td>
                <td className="py-2 pr-3">{r.uk}</td>
                <td className="py-2 pr-3">{range(r.chest)}</td>
                <td className="py-2 pr-3">{range(r.waist)}</td>
                <td className="py-2 pr-3">{range(r.hips)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
