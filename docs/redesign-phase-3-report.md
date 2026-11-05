# Redesign Phase 3 Report: Revised Fit Analysis and Product Types

**Date:** 2026-11-05
**Result:** implemented, tested and pushed to `main`. GitHub CI passed on all three jobs, and Vercel reports a completed deployment.

> This is the redesign's Phase 3. The older `phase-3-prototype-report.md` covers an earlier plan's frontend phase.

The rules are also in [`redesign-plan.md`](redesign-plan.md), §2.1–2.3.

---

## 1. What was implemented

- **New fit engine** (`pipeline/fit_analysis.py`, `pipeline/size_charts.py`), replacing `fitting.py`. It compares published size ranges and returns MATCH, UNCERTAIN or MISMATCH with reasons.
- **Priority measurements:** waist, hips and shoulders. Each category uses the ones that apply.
- **Published ranges are kept.** The size chart parser used to reduce `66–74` to its midpoint. It now keeps the range too.
- **Product types** (`pipeline/taxonomy.py`): the 8 MVP types, each mapped to a fit category or to none, with an explanation when no rules apply.
- **Results filtering** (`pipeline/ranking.py`): MATCH first, UNCERTAIN in its own section, MISMATCH hidden with a count and reasons.
- **New API results:** `matches`, `uncertain`, `hidden_mismatches{count, reasons}` and `fit_mode_used`.
- **One results screen** for live and demo checks, fed by Python's result groups.
- **Personal Fit demo:** the browser can't run Python, so the fixture holds Python's results for 3 sample measurements. They save nothing to the profile.
- **New demo product:** Demo Petite Trousers (XXS, XS), which shows a proven Quick Fit mismatch.
- **Old system removed** (§5).
- **Deferred task added to the roadmap:** the size-system selector review, in your wording. The selector and stored size-system data are unchanged.

---

## 2. The exact fit-decision logic

### Measurements per category

| Category | Critical | Used by Quick Fit | Secondary | Tolerance |
|---|---|---|---|---|
| Jeans, pants | Waist, hips | Waist, hips | Inseam | ±2 cm body chart, ±1 cm garment chart |
| Sweaters, tops, hoodies | Chest, shoulders | Shoulders | Waist, sleeve | ±2 cm |
| Dresses (not an MVP type) | Chest, waist, hips | Waist, hips | None | ±2 cm |
| Outerwear (not an MVP type) | Chest, shoulders | Shoulders | Sleeve | ±3 cm |
| Skirts, shorts, hats | None: UNCERTAIN with a reason | | | |

### Personal Fit, in order

1. **No rules, no chart, or no listed size the chart describes:** UNCERTAIN.
2. **Find candidates:** every published size where all comparable critical measurements are inside their inclusive ranges. A value is comparable only if both sides exist and share a basis (body or garment).
3. **If a candidate is on sale:**
   - More than one distinct candidate: **UNCERTAIN**. This covers shared boundaries and overlaps.
   - One candidate: a missing critical measurement, or a secondary measurement beyond tolerance: **UNCERTAIN**.
   - Otherwise: **MATCH**.
4. **If no candidate is on sale:**
   - Outside a range but within tolerance on a listed size: **UNCERTAIN**.
   - Every listed size has a critical measurement beyond tolerance: **MISMATCH**. This outranks missing and secondary data.
   - Otherwise (a listed size has nothing to compare): **UNCERTAIN**.

### Quick Fit, in order

1. No rules: UNCERTAIN.
2. No size chosen for the product's own category: UNCERTAIN ("Add your Bottoms size.").
3. No chart, or the chart doesn't describe the chosen size or the listed sizes: UNCERTAIN.
4. **Product listed in the chosen size:**
   - A priority measurement isn't published: UNCERTAIN.
   - The size overlaps a neighbour beyond a touching end: UNCERTAIN.
   - Otherwise: **MATCH**, labelled approximate.
5. **Product not listed in the chosen size:** MISMATCH only with the proof in §4. Otherwise UNCERTAIN.

### Decisions where your brief needed interpretation

These are my readings of the brief. Please correct any you disagree with.

| Topic | Decision | Why |
|---|---|---|
| Chest | Stays critical in Personal Fit for tops, dresses and outerwear. Quick Fit doesn't use it. | You asked not to remove a required dimension silently, and to use only the priority group in Quick Fit. |
| Sleeve | Added as secondary for tops and outerwear. | Your brief names it as an additional measurement. |
| Missing inseam | Doesn't block MATCH; shown as "Not checked: inseam". | Your MATCH rule says no *known* additional measurement creates a concern. This changes the earlier rule. |
| Within tolerance but outside the range | UNCERTAIN. | MATCH requires being inside the range, and MISMATCH requires being beyond tolerance. |
| Boundary with another deciding measurement | Waist 70 on S/M, with hips only in S, is MATCH for S. | There's no genuine ambiguity when another critical measurement rules out M. |
| Boundary with an unsold size | Still UNCERTAIN. | The person may really need the size that isn't sold. |
| Single published value, no range | The tolerance acts as its range, and the nearest size is used. | A single value has no range to be inside. |
| Stretch | The existing 2.54 cm allowance applies only to garment circumferences, on the tight side, with known fabric. It can't create a MATCH. | This keeps the existing value, which isn't in the approved tolerance table. Please confirm it. |
| Fit memory | Not applied to results. | Nothing writes it yet, so nothing changes today. It returns with Phase 7. |

Tolerances are unchanged. Comparisons use exact decimals to avoid floating-point boundary errors.

---

## 3. Examples

All use the Merchandizable chart, or the test chart where stated.

| Outcome | Example | Why |
|---|---|---|
| **MATCH** | Quick Fit, Bottoms M, Demo Wide-Leg Trousers | Listed in M; waist and hips are published. Labelled approximate. |
| **MATCH** | Personal Fit, waist 70, hips 95, same trousers | Inside S on both. Inseam shown as not checked. |
| **UNCERTAIN** | Personal Fit, waist 74, hips 97.5 | Both values fit S and M. |
| **UNCERTAIN** | Quick Fit, any size, Demo Relaxed Sweater | Shoulders are the priority measurement and aren't in the chart. |
| **UNCERTAIN** | Quick Fit, Levi's baggy jeans | Sold in waist/length sizes, which the letter chart doesn't describe. |
| **UNCERTAIN** | Test chart, waist 91 with L at 80–90 | Outside the range, within the ±2 cm tolerance. |
| **UNCERTAIN** | Test chart, inside S, inseam 90 with S at 76–80 | A secondary measurement doesn't match. |
| **MISMATCH** | Personal Fit, waist 125, hips 135, chest 125, trousers sold up to XXL | Waist is beyond XXL's 105–117.5 cm plus tolerance. Hidden with the reason. |
| **MISMATCH** | Test chart, chest 95, shoulders 60, top | "Shoulders 60 cm is outside…", beyond tolerance. |
| **MISMATCH** | Quick Fit, Bottoms XL, Demo Petite Trousers | Proven gap (§4). |

---

## 4. Can Quick Fit produce a verified MISMATCH?

**Yes, but only with this proof.** All four must hold:

1. The product isn't listed in the chosen size.
2. The chart publishes a range for the chosen size in a priority measurement of the category.
3. Every listed size publishes a range for that same measurement.
4. The chosen size's range is **more than the approved tolerance** away from **every** listed size's range.

**Example:** Bottoms XL has waist 93–105 cm. Demo Petite Trousers are sold only up to XS, with waist 64–66 cm. The gap is 27 cm, far beyond the 2 cm tolerance, so nothing in the XL range can fit a listed size.

**What doesn't count as proof:**
- Bottoms S against the same trousers: S (66–74 cm) touches XS at 66 cm, so it's UNCERTAIN.
- A gap of exactly the tolerance: UNCERTAIN.
- A measurement outside the priority group, such as chest: UNCERTAIN.
- A listed size that doesn't publish the measurement: UNCERTAIN.

**The assumption behind it:** the person's body lies within the published range of the size they chose. Quick Fit never derives a number for the person, and it stays labelled approximate.

**In the demo chart:** Tops can't reach MATCH or MISMATCH in Quick Fit, because the chart has no shoulders. Nothing was invented to change that.

---

## 5. What obsolete code was removed

| Removed | Replaced by |
|---|---|
| `pipeline/rules.py` (verdict rules, score) | `pipeline/ranking.py` |
| `pipeline/narrate.py` (verdict copy) | Deterministic reasons and seller summary |
| `pipeline/fitting.py` (old fit card, size choice) | `fit_analysis.py`, `size_charts.py` |
| `Verdict`, `Decision`, `Narrative`, `DecisionMemory`, `FitMatch`, `SizeChoice`, `RankedOption.score` | `FitOutcome`, `DimensionStatus` |
| Market average; `market_avg_cents`, `delta_cents`, `delta_pct`, `comparable_count` | Actual price, shipping and total |
| API `verdict`, `headline`, `explanation`, `why_not`, `options` | `matches`, `uncertain`, `hidden_mismatches`, `fit_mode_used` |
| `mock/engine.ts` (TypeScript copy of the rules), `mock/scenarios.ts`, `DemoResultView` | The generated fixture and one results screen |
| Verdict badge, banner and scale; market lines; BUY/CONSIDER/SKIP on the methodology page and in metadata | Outcome badge, findings and rewritten copy |
| Color tokens named `buy`, `consider`, `skip` | `positive`, `caution`, `negative` |

`tests/test_obsolete_removed.py` fails if the old modules, models, contract fields or source mentions return.

**Kept on purpose:** price, seller reliability, extraction, feedback UI and `fit_memory`.

**Side effects:**
- The prototype's older sample checks are gone, and old browser-stored results are no longer read. Saved profiles are kept.
- The AI no longer writes copy. It's still used for extraction and review summaries.

---

## 6. What remains for Phase 4

- Budget field in €, on the homepage and in ranking.
- Currency fix: unknown currency isn't USD, "not directly comparable to EUR", and EUR formatting. The `USD` defaults in `ProductExtract`, `fmtMoney` and the JSON-LD extractor are still there.
- `check_runs.fit_mode_used` column (the API reads the mode from the stored snapshot for now).
- Idempotency key on `POST /v1/checks`.
- Response guards where data enters the web app, and the `live.ts` duplicate.

**Already done early, by your decision:** verdict and market removal, the results contract and screen, and Python fixtures replacing `mock/engine.ts`.

**Migration B (Phase 8):** drop the columns no longer written (`verdict`, `headline`, `explanation`, `why_not`, `check_options.score`), the `verdict` and `skip_reason` enums, and the `decision_memory` table.

**Moved to the live-product milestone:** `size_references` source columns and the Levi's DE chart.

---

## 7. Tests and quality gates

| Check | Result |
|---|---|
| Backend unit tests | **433 passed**, 28 integration tests skipped in that run |
| Backend integration tests (local Postgres) | **28 passed** |
| Ruff format and check, mypy | Passed |
| OpenAPI and prototype-data checks | Passed |
| Web tests | **179 passed** |
| Web lint, typecheck, production build | Passed |
| GitHub CI, [run on `46f9033`](https://github.com/PasisHMM/BuyLens/actions/runs/42027385793) | **All 3 jobs passed** |
| Vercel | Status reports "Deployment has completed"; I didn't open the deployed site |
| Mutator (fit analysis, size charts, taxonomy, ranking, measurements, fit profile, demo shop, pricing) | **108 of 108 covered mutants killed**; 5 sites report as uncovered |
| Crapper, backend | All new functions under 10. `run_check` is 13 (was 17) and `parse_table` is 24 (was 27): both are older and I changed them |
| Crapper, web | New and rewritten functions under 10. Older screens I barely touched remain high: `ProgressDialog`, `BrandChips`, `FeedbackDialog`, `live.ts` |
| Dryer | No new duplicates. Two older ones remain, in `live.ts` and `primitives.tsx` |
| Browser, desktop and 375 px | MATCH, UNCERTAIN and hidden MISMATCH flows work, with no sideways scroll on mobile |

Mutator's first run left 20 survivors, including missing boundary tests. Each was then killed by a new test or removed by simplifying the code.

**Not checked:**
- Live mode wasn't run end to end. It's covered by API, pipeline and integration tests.
- The real SumUp page wasn't opened today.
- The browser tests clicked some controls by script. Keyboard use has only component tests.

---

## 8. Git commits and push status

Pushed normally to `main` (`6c5a4ba..46f9033`), with no force-push or history rewrite.

| Commit | Change |
|---|---|
| `e85140e` | Migration: keep every option in storage (not applied remotely) |
| `887249a` | Taxonomy: eight product types |
| `b69efff` | Fit analysis v2; verdicts and market figures removed |
| `0f260d8` | Web: one results screen; mock verdict engine removed |
| `46f9033` | Docs: revised rules, Quick Fit proof, Phase 3 results |

This report is in a later docs-only commit. `b69efff` is large because the pipeline, models and contract change together, and the web commit that follows it restores a compiling frontend. Only the final state was tested.

No remote Supabase change was made. `.claude/` remains uncommitted.

---

## 9. Limitations and deferred decisions

**Limitations:**
- **Personal Fit in the browser:** someone's own measurements show UNCERTAIN, with the reason, because the comparison runs in Python. The 3 sample measurements show real Python results.
- **Tops in the demo:** at best UNCERTAIN, because the chart has no shoulders. A MATCH on a top needs shoulder data you supply.
- **Inseam in the demo:** never compared, because the chart doesn't list it.
- **Sample data:** the chart, prices and fictional products are unverified, and each MATCH says so.
- **Live garment charts:** a profile with body measurements can't be compared with a garment-only chart, so those results are UNCERTAIN. That's correct under your rule, but many real stores may publish garment charts.
- **Live mode needs two remote migrations** before it can run this code: Phase 1 and `20261105000000`. Neither is applied.
- **Mutator's uncovered sites:** 5 sites on multi-line expressions or unused branches report as uncovered. They aren't counted as killed.

**Decisions for you:**
1. **Should within-tolerance-but-outside-range stay UNCERTAIN?** I recommend yes. The alternative is treating it as MATCH, as the old glossary did.
2. **Do you approve the 2.54 cm stretch allowance?** I kept the existing value so as not to change a number silently, but it was never in the approved table. I recommend keeping it until you have real garment-chart data.
3. **Do you want to supply shoulder and inseam values for the demo chart?** It's the only way a demo top can reach MATCH.

**Deferred on the roadmap:**
- Review and improve the user-facing size-system selector (EU/US and potentially additional regional systems), including conversion and category-specific labels.
- Real retailers, store access and the Phase 9 admin panel, as planned.
