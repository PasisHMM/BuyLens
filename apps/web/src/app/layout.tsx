import type { Metadata } from "next";
import { Inter, Lora } from "next/font/google";
import { Suspense } from "react";

import { SiteFooter } from "@/components/layout/SiteFooter";
import { HeaderShell, SiteHeader } from "@/components/layout/SiteHeader";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const lora = Lora({ subsets: ["latin"], variable: "--font-lora" });

export const metadata: Metadata = {
  title: "Buy Lens: a second opinion before you buy",
  description:
    "Paste a clothing link and get a BUY, CONSIDER or SKIP verdict based on your exact measurements.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${lora.variable}`}>
      <body className="flex min-h-dvh flex-col bg-bg text-ink">
        <Providers>
          <Suspense fallback={<HeaderShell />}>
            <SiteHeader />
          </Suspense>
          <main className="flex-1">{children}</main>
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
