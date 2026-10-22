import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy & methodology · Buy Lens" };

const RULES: [string, string][] = [
  [
    "SKIP",
    "A measurement falls outside the range we expect, the seller looks high-risk, or the price is more than 25% above the market average.",
  ],
  [
    "CONSIDER",
    "A measurement you saved isn’t published, size data is partial, the price is over 5% above average, or returns aren’t free or verified.",
  ],
  ["BUY", "Every check passes."],
];

export default function MethodologyPage() {
  return (
    <article className="mx-auto max-w-[720px] px-4 py-12 sm:px-8 sm:py-20">
      <p className="eyebrow text-muted">Privacy &amp; methodology</p>
      <h1 className="mt-5 font-serif text-[40px] leading-tight sm:text-[52px]">
        How we decide.
      </h1>
      <p className="mt-6 leading-relaxed text-muted">
        Verdicts come from fixed rules, not from an AI guess. AI only reads
        product pages and reviews, and writes the explanation. It never changes
        the verdict. Recommendations aren’t fit guarantees.
      </p>
      <dl className="mt-10 divide-y divide-line border-y border-line">
        {RULES.map(([verdict, text]) => (
          <div
            key={verdict}
            className="grid gap-2 py-5 sm:grid-cols-[120px_1fr]"
          >
            <dt className="text-sm font-semibold">{verdict}</dt>
            <dd className="text-sm leading-relaxed text-muted">{text}</dd>
          </div>
        ))}
      </dl>
      <h2 className="mt-12 text-xl">Your data</h2>
      <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-relaxed text-muted">
        <li>
          Your measurements are used only to personalize your product checks. We
          never sell them.
        </li>
        <li>
          Feedback improves your future verdicts. It is never posted as a public
          review.
        </li>
        <li>
          We only check stores on our supported list and respect each store’s
          robots.txt.
        </li>
      </ul>
    </article>
  );
}
