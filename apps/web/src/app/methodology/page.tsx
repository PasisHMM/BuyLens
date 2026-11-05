import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy & methodology · Buy Lens" };

const RULES: [string, string][] = [
  [
    "MATCH",
    "One size clearly fits: every critical measurement is inside its published range, and nothing known counts against it.",
  ],
  [
    "UNCERTAIN",
    "You fall between two sizes, an additional measurement such as inseam doesn’t match, or the data needed for a trustworthy answer is missing. Check before buying.",
  ],
  [
    "MISMATCH",
    "A critical measurement is verified outside the permitted range. The option is hidden from your results, and we tell you why.",
  ],
];

export default function MethodologyPage() {
  return (
    <article className="mx-auto max-w-[720px] px-4 py-12 sm:px-8 sm:py-20">
      <p className="eyebrow text-muted">Privacy &amp; methodology</p>
      <h1 className="mt-5 font-serif text-[40px] leading-tight sm:text-[52px]">
        How we check.
      </h1>
      <p className="mt-6 leading-relaxed text-muted">
        Fit results come from fixed rules, not from an AI guess. AI only helps
        read product pages and reviews, and never decides a result. We show the
        evidence, and the decision stays yours. Results aren’t fit guarantees.
      </p>
      <dl className="mt-10 divide-y divide-line border-y border-line">
        {RULES.map(([outcome, text]) => (
          <div
            key={outcome}
            className="grid gap-2 py-5 sm:grid-cols-[120px_1fr]"
          >
            <dt className="text-sm font-semibold">{outcome}</dt>
            <dd className="text-sm leading-relaxed text-muted">{text}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-6 text-sm leading-relaxed text-muted">
        Quick Fit compares your size with published size ranges, so it’s always
        approximate. We never work out exact measurements from a size label.
        Quick Fit hides an option only if your size’s range is too far from
        every size on sale for any measurement in your size to fit.
      </p>
      <h2 className="mt-12 text-xl">Your data</h2>
      <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-relaxed text-muted">
        <li>
          Your measurements are used only to personalize your product checks. We
          never sell them.
        </li>
        <li>Feedback is never posted as a public review.</li>
        <li>
          We only check stores on our supported list and respect each store’s
          robots.txt.
        </li>
      </ul>
    </article>
  );
}
