# Phase 3 Report: Clickable Web Prototype

> **App:** `apps/web` (Next.js 16, React 19, Tailwind CSS 4)
> **Mode:** built-in sample data by default (`NEXT_PUBLIC_API_MODE=mock`). It switches to the real API with `live`.
> **Design source:** the 13 desktop and mobile screenshots (Preferences, Product analyzer, Analysis loading, Product results, Feedback Yes/No, Feedback saved)

---

## 1. Summary

All design screens are built and clickable, on desktop and phone, and need no backend, sign-in or keys. Verdicts come from a small copy of the backend's rules, so they react to the measurements each tester enters.

| Check | Result |
|---|---|
| Lint (ESLint) and type check (TypeScript strict) | ✅ Clean |
| Production build | ✅ Passes; Vercel's build of `main` also succeeded |
| Manual test in the browser, desktop 1440 px and phone 390 px | ✅ Every screen and flow listed below |
| Horizontal scrolling at 390 px | ✅ None on any screen |
| Backend unit tests / integration tests | ✅ 145 / ✅ 10 (integration tests run against a local Postgres 16) |

---

## 2. What was tested

| Flow | Result |
|---|---|
| First visit sends you to Preferences | ✅ |
| Preferences: save waist, inseam, hips and brands | ✅ |
| Preferences: unit mix-up (inseam 76 with IN on) shows "Check the unit (IN / cm)" | ✅ |
| Preferences: IN ↔ cm toggle converts the typed values both ways | ✅ |
| Analyzer: profile bar, `W26/L30` header pill, sample links | ✅ |
| Loading dialog: 4 live steps with details, "Step N of 4" | ✅ |
| **CONSIDER** result (Levi's): matches the design, including card numbers and option order | ✅ |
| **BUY** result (Madewell): 2 options, every fit row passes | ✅ |
| **SKIP** result (marketplace seller): high risk, red-flag reviews, 1 option | ✅ |
| Option tabs switch the summary, cards and "View at …" button | ✅ |
| Feedback **Yes** → "Too tight at hips" → saved state | ✅ |
| Feedback **No** → Price + Seller risk → toast and saved state | ✅ |
| "Store blocks us" sample → "We couldn't finish this check." | ✅ (after fix) |
| Unsupported store → inline "We don't support this store yet." | ✅ |
| **Cancel** partway through a check | ✅ stops, stays on home, saved as cancelled |
| "Check another product" → home page with an empty link field and a recent-check card | ✅ (after fix) |

---

## 3. Bugs found and fixed

| # | Bug | Effect | Fix |
|---|---|---|---|
| 1 | Returning home after a result **bounced back to the old result** | "Check another product" didn't work | Close the loading dialog and clear the field before opening the result |
| 2 | "Store blocks us" sample **hung forever** in the loading dialog | A crash on a check with no options | Failing samples skip the verdict; any unexpected error now ends the check with "failed" |
| 3 | Link field **squashed to half height** on phones | Hard to tap | Fixed height on mobile (48 px, as in the design) |
| 4 | Recent-check badge shown on phones, **cutting the product name short** | Didn't match the design | Badge hidden on phones |
| 5 | Preferences headline wrapped onto 3 lines on desktop | Didn't match the design | Wider layout; now 2 lines, as designed |
| 6 | Inner focus outline drawn inside text fields | Looked like a double border | Removed; the field border shows focus |
| 7 | Fit column said "Garment" for *body* size charts | Misleading | Says "Size chart" when the store gives body measurements |
| 8 | Fit notes said "hips matches the size chart" | Grammar | Singular "hip", in the prototype and the backend |
| 9 | SKIP hint said "compare the options above" when there was only 1 | Confusing | Wording depends on the number of options |
| 10 | Sample option order differed from the design (DenimMarket above Nordstrom) | Didn't match the design | Sample prices adjusted (same $97 total) |
| 11 | CI database job failed | Red CI on GitHub | Test cleanup tried to delete a seller that listings still pointed to; it now disables it. All 10 integration tests pass |

---

## 4. Known limitations (by design for a prototype)

- **Sample data only.** Prices, ratings and policies are illustrative. "DenimMarket" and "Rivet & Row" are fictional. The header shows a "Sample data" badge.
- **Data stays in each tester's browser** (`localStorage`). Testers don't share data, and clearing site data resets the app.
- **Product images are placeholders.**
- **Feedback works only in sample mode.** The backend endpoint comes with Phase 4.
- **Only 4 sample stores answer:** levi.com (CONSIDER), madewell.com (BUY), denimmarket.example (SKIP) and agolde.com (blocked). Other links get "We don't support this store yet."

---

## 5. Design notes for you

- **Two verdict colors have low contrast** for small text (the WCAG AA guideline is 4.5:1). I kept your colors unchanged; these are suggestions.

  | Color | On background | Contrast | Passes AA? | Same hue, darkened to pass |
  |---|---|---|---|---|
  | Buy `#7CA28D` | `#EAF2EC` | 2.5:1 | ❌ (visibly faint in the BUY banner and "Low risk" pill) | `#587364` (4.5:1) |
  | Consider `#976D2D` | `#F5EDDC` | 4.0:1 | ❌ for small text | `#8A6429` (4.6:1) |
  | Skip `#A33E36` | `#F8EAE7` | 5.4:1 | ✅ | n/a |
- **Analyzer helper text** says "Works with most fashion retailers", but the real app only checks stores on its allow-list. Consider "Works with the stores we support."
- **Colors not in your list** (secondary gray text, borders, light-gray panels) were matched from the screenshots: `#6E6C72`, `#E6E3DE`, `#F0EEEA`.

---

## 6. Deployment (Vercel)

- **Project:** `buy-lens` in team `buy-lens-corp`. It builds from `main`, with Root Directory `apps/web`. GitHub shows the build of each commit as successful.
- **The site needs a Vercel login** because Deployment Protection is on. Visitors are redirected to a Vercel sign-in page. To share it publicly:
  1. Vercel → project **buy-lens** → **Settings** → **Deployment Protection**.
  2. Set **Vercel Authentication** to **Disabled** (or "Only Preview Deployments"), then **Save**.
  3. Open **Settings → Domains** to see your public address.
- **Watch out for similar addresses:** `buy-lens.vercel.app` and `buylens.vercel.app` belong to **other people's apps**, not this project.

---

## 7. CI

The workflow now has 3 jobs:

| Job | What it checks |
|---|---|
| API | Lint, strict types, 145 unit tests, OpenAPI contract |
| Migrations + RLS | Both migrations and the seed on Postgres 16, plus 10 integration tests |
| Web *(new)* | `npm ci`, lint, type check, production build |

---

## 8. Next steps

1. Switch off Vercel Deployment Protection so testers can open the link.
2. Decide on the Buy color contrast and the "most fashion retailers" wording.
3. Phase 4: feedback endpoint and memory loop, which replaces the browser-only feedback.
4. Live mode: run the analyzer migration, add Redis and Gemini, host the API (see `docs/phase-2-report.md` §6).
