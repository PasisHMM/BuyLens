import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-[1312px] flex-col gap-3 px-4 py-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 sm:py-8 lg:px-16">
        <p className="sm:hidden">Independent advice. Never a guarantee.</p>
        <p className="hidden sm:block">
          Independent advice, not a guarantee. Prices and availability can
          change. We never sell your measurements.
        </p>
        <Link
          href="/methodology"
          className="inline-flex items-center gap-1 hover:text-ink"
        >
          Privacy &amp; methodology{" "}
          <ArrowUpRight className="size-3" aria-hidden />
        </Link>
      </div>
    </footer>
  );
}
