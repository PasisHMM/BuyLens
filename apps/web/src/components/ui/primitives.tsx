import { ImageIcon } from "lucide-react";
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import type { Verdict } from "@/lib/api";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

type ButtonVariant = "primary" | "secondary";
const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-btn-on text-white hover:bg-black disabled:bg-faint",
  secondary:
    "border border-line bg-frame text-ink hover:border-ink/40 disabled:text-faint",
};

export function Button({
  variant = "primary",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: ButtonVariant }) {
  return (
    <button
      type="button"
      {...props}
      className={cx(
        "inline-flex h-12 items-center justify-center gap-2 rounded-lg px-6 text-[15px] font-medium transition-colors disabled:cursor-not-allowed",
        BUTTON[variant],
        className,
      )}
    />
  );
}

export function ButtonLink({
  variant = "primary",
  className,
  external,
  ...props
}: ComponentProps<typeof Link> & {
  variant?: ButtonVariant;
  external?: boolean;
}) {
  return (
    <Link
      {...props}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className={cx(
        "inline-flex h-12 items-center justify-center gap-2 rounded-lg px-6 text-[15px] font-medium transition-colors",
        BUTTON[variant],
        className,
      )}
    />
  );
}

export const VERDICT_STYLE: Record<
  Verdict,
  { text: string; bg: string; label: string }
> = {
  BUY: { text: "text-buy", bg: "bg-buy-bg", label: "Buy" },
  CONSIDER: { text: "text-consider", bg: "bg-consider-bg", label: "Consider" },
  SKIP: { text: "text-skip", bg: "bg-skip-bg", label: "Skip" },
};

export function VerdictBadge({
  verdict,
  className,
}: {
  verdict: Verdict;
  className?: string;
}) {
  const s = VERDICT_STYLE[verdict];
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium",
        s.bg,
        s.text,
        className,
      )}
    >
      {s.label}
    </span>
  );
}

export function Card({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "rounded-[var(--radius-card)] border border-line bg-frame",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Callout({
  tone,
  title,
  children,
}: {
  tone: "buy" | "consider" | "skip";
  title: string;
  children?: ReactNode;
}) {
  const style = {
    buy: "bg-buy-bg text-buy",
    consider: "bg-consider-bg text-consider",
    skip: "bg-skip-bg text-skip",
  }[tone];
  return (
    <div className={cx("rounded-lg px-4 py-3", style)}>
      <p className="text-sm font-semibold">{title}</p>
      {children && <p className="mt-1 text-xs opacity-90">{children}</p>}
    </div>
  );
}

/** Placeholder until real product images are wired in. */
export function ProductImage({
  name,
  size = "md",
}: {
  name: string;
  size?: "sm" | "md";
}) {
  const dims = size === "sm" ? "size-16 sm:size-[64px]" : "size-24 sm:size-28";
  return (
    <div
      role="img"
      aria-label={`${name} (image placeholder)`}
      className={cx(
        dims,
        "flex shrink-0 items-center justify-center rounded-lg bg-[#ece7df] text-[#b9b0a3]",
      )}
    >
      <ImageIcon
        className={size === "sm" ? "size-5" : "size-7"}
        strokeWidth={1.5}
        aria-hidden
      />
    </div>
  );
}

export function Eyebrow({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <p className={cx("eyebrow text-muted", className)}>{children}</p>;
}
