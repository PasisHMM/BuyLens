"use client";

import { Ruler, ScanEye } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useApp } from "@/app/providers";
import { profilePill } from "@/lib/format";

/** Static part of the header: the prerendered fallback while the route-aware header loads. */
export function HeaderShell({ children }: { children?: React.ReactNode }) {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex h-[72px] max-w-[1312px] items-center justify-between gap-4 px-4 sm:h-[88px] sm:px-8 lg:px-16">
        {children ?? <Logo />}
      </div>
    </header>
  );
}

function Logo({ sample = false }: { sample?: boolean }) {
  return (
    <Link
      href="/"
      className="flex items-center gap-3"
      aria-label="Buy Lens home"
    >
      <ScanEye className="size-7 sm:size-8" strokeWidth={1.5} aria-hidden />
      <span className="text-[22px] tracking-tight sm:text-2xl">buy lens</span>
      {sample && (
        <span className="hidden rounded-full bg-subtle px-2 py-0.5 text-[11px] font-medium text-muted sm:inline">
          Sample data
        </span>
      )}
    </Link>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const { profile, profileLoaded, api } = useApp();
  const onPreferences = pathname === "/preferences";

  return (
    <HeaderShell>
      <Logo sample={api.mode === "mock"} />

      {onPreferences ? (
        <span className="text-sm text-muted">Your preferences</span>
      ) : (
        <div className="flex items-center gap-8">
          <span className="hidden text-sm text-muted md:inline">
            A second opinion. Before you buy.
          </span>
          {profileLoaded && (
            <Link
              href="/preferences"
              className="inline-flex h-9 items-center gap-2 rounded-full border border-line bg-frame px-4 text-sm font-semibold"
              aria-label={
                profile ? "Edit your measurements" : "Add your measurements"
              }
            >
              <Ruler
                className="size-4 -rotate-45"
                strokeWidth={1.75}
                aria-hidden
              />
              <span className="num">
                {profilePill(profile?.waist, profile?.inseam)}
              </span>
            </Link>
          )}
        </div>
      )}
    </HeaderShell>
  );
}
