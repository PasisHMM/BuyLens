# Buy Lens Glossary

The domain terms used in code, the database and the UI. Code names are in `services/api/app/pipeline/models.py` and `measurements.py`.

| Term | Code / DB | Meaning |
|---|---|---|
| **Measurement** (dimension) | `Dimension` · `measurement_dimensions` | One body measurement in cm: chest, waist, hips, shoulders, inseam, sleeve, height. |
| **Chest / bust** | `Dimension.CHEST` | One measurement: the fullest girth of the upper body. Charts saying "bust" map to it. |
| **Basis** | `Basis` · `measurement_basis` | What a number measures. **Body:** the person, or a brand's body-size chart. **Garment:** the clothing itself, laid flat or from a garment chart. Body numbers are compared with body charts, and garment numbers with garment charts. |
| **Fit category** | `FitCategory` · `fit_category` | A garment group with agreed fit rules: bottoms (jeans and pants), tops, dresses, outerwear. Products in other categories (shorts, skirts) have no rules yet. |
| **Product type** | `ProductType` (planned, `taxonomy.py`) | One of the 8 MVP types: skirts, shorts, sweaters, tops/cardigans, hoodies, jeans, pants, hats. Each maps to a fit category or to none. |
| **Priority measurement** | `PRIORITY_DIMENSIONS` | Waist, hips and shoulders. Each category uses the ones that apply. Quick Fit compares only these. |
| **Attribute** | planned, `taxonomy.py` | A design fact from a fixed list (e.g. sleeve length: three-quarter). It describes the item and never affects the fit outcome. |
| **Comparable offer** | planned (Phase 4) | An offer priced in EUR. Offers in other currencies keep their own price and are labelled "Not directly comparable to EUR offers". |
| **Critical measurement** | `CategoryRule.critical` | If it's verified outside the range beyond tolerance on every listed size, the result is a **mismatch**. If it's missing, the result is **uncertain**. |
| **Secondary measurement** | `CategoryRule.secondary` | An additional measurement, such as inseam or sleeve. If it's known and beyond tolerance, the result is **uncertain**, never a mismatch. If it's missing, it's reported as not checked and doesn't block a match. |
| **Tolerance** | `CategoryRule.tolerance_cm(basis)` | How far, in cm, a measurement may be outside a range without being a mismatch. Inside the tolerance but outside the range is **uncertain**. Depends on category and basis. |
| **Plausible range** | `DimensionSpec.plausible_cm` | Adult range for a measurement. Values outside it are treated as a unit mix-up (inches typed as cm). |
| **Fit mode** | `FitMode` · `fit_mode` | How a profile describes the user. **Quick Fit:** one standard size per category, which is approximate. **Personal Fit:** exact measurements. |
| **Quick size** | `QuickSize` · `quick_sizes` | XS / S / M / L / XL, chosen per fit category in Quick Fit. |
| **Size system** | `SizeSystem` · `size_system` | EU or US. Picked by the user before Quick Fit sizes. |
| **Size reference** | `SizeReference` · `size_references` | The approximate body range in cm for a standard size, always with a named **source**. Empty today: Quick Fit reads the product's own chart. |
| **Fit outcome** | `FitOutcome` | The result of comparing a profile with one listing. **MATCH:** one size clearly fits, with nothing known against it. **UNCERTAIN:** between sizes, an additional concern, or not enough evidence. **MISMATCH:** a critical measurement is verified outside the permitted range; hidden from the visible results. |
| **Shared boundary** | §2.3 | A value on the inclusive end of two sizes' ranges. **Uncertain** only when both sizes remain candidates. |
| **Proven Quick Fit mismatch** | `_gap_proof` | The chosen size's range is beyond tolerance from every listed size's range, in a priority measurement. The only way Quick Fit returns MISMATCH. |
| **Hidden mismatch** | `hidden_mismatches` | An option kept in storage and left out of the visible results, counted in a note with its reason. |
| **Sample measurements** | `PERSONAL_SAMPLES` | Fixed values with Python's results ready, so the browser prototype can show Personal Fit. Saved nowhere. |
| **Demo shop** | `SHOPS` in `lib/shops.ts`, `pipeline/demo_shop.py` | **Merchandizable:** a fictional shop for the mock-data prototype. Not a supported retailer. |
| **Demo size chart** | `DEMO_CHART` | The demo shop's body chart, XXS–4XL, with EU and UK labels. Sample data, not verified, and separate from the global catalog and Quick Fit sizes. |
| **Coming-soon shop** | `status: "coming_soon"` | A shop shown gray and disabled. Its definition is kept so it can be re-enabled by configuration. |
| **Offer** | `Offer` in `lib/outbound.ts` | One displayed option: `listing_id` (stable offer identifier), `seller.domain` (retailer) and `url`. |
| **Outbound link** | `resolveOutboundLink` | A validated link to the offer's own page. Adds no tracking. |
| **Prototype milestone** | §11.1 | A demonstrable product on mock data. Doesn't need a readable store. |
| **Live-product milestone** | §11.1 | Real retailers, real data, production services. Needs at least one readable EU store. |
| **Rule set** | `RuleSet` (planned, Phase 9) | The complete, validated values the engine uses for one check. Plain data, never code. Built from the **defaults** in code, or from a published version. |
| **Published version** | `rule_set_versions` (planned, Phase 9) | An immutable snapshot of a rule set. One is active at a time. Rollback publishes an older snapshot as a new version. |
| **Content block** | planned, Phase 9 | One typed piece of page content (e.g. heading, FAQ item) or a predefined section, from a fixed registry. Holds no HTML or code. |
| **Fit feedback** | DB enum `fit_outcome` on `feedback.fit` | What the user reports after buying: too tight / fits well / too loose. *Not the same thing as Fit outcome.* The database type name predates the redesign. |
