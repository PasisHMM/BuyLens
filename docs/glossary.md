# Buy Lens Glossary

The domain terms used in code, the database and the UI. Code names are in `services/api/app/pipeline/models.py` and `measurements.py`.

| Term | Code / DB | Meaning |
|---|---|---|
| **Measurement** (dimension) | `Dimension` · `measurement_dimensions` | One body measurement in cm: chest, waist, hips, shoulders, inseam, sleeve, height. |
| **Chest / bust** | `Dimension.CHEST` | One measurement: the fullest girth of the upper body. Charts saying "bust" map to it. |
| **Basis** | `Basis` · `measurement_basis` | What a number measures. **Body:** the person, or a brand's body-size chart. **Garment:** the clothing itself, laid flat or from a garment chart. Body numbers are compared with body charts, and garment numbers with garment charts. |
| **Fit category** | `FitCategory` · `fit_category` | A garment group with agreed fit rules: bottoms (jeans and pants), tops, dresses, outerwear. Products in other categories (shorts, skirts) have no rules yet. |
| **Product type** | `ProductType` (planned, `taxonomy.py`) | One of the 8 MVP types: skirts, shorts, sweaters, tops/cardigans, hoodies, jeans, pants, hats. Each maps to a fit category or to none. |
| **Attribute** | planned, `taxonomy.py` | A design fact from a fixed list (e.g. sleeve length: three-quarter). It describes the item and never affects the fit outcome. |
| **Comparable offer** | planned (Phase 4) | An offer priced in EUR. Offers in other currencies keep their own price and are labelled "Not directly comparable to EUR offers". |
| **Critical measurement** | `CategoryRule.critical` | If it's outside tolerance, the result is a **mismatch**. If it's missing, the result is **uncertain**. |
| **Secondary measurement** | `CategoryRule.secondary` | Checked when known. If it's off or missing, the result is **uncertain**, never a mismatch. |
| **Tolerance** | `CategoryRule.tolerance_cm(basis)` | How far, in cm, a size may be from the user's measurement and still count as within range. Depends on category and basis. |
| **Plausible range** | `DimensionSpec.plausible_cm` | Adult range for a measurement. Values outside it are treated as a unit mix-up (inches typed as cm). |
| **Fit mode** | `FitMode` · `fit_mode` | How a profile describes the user. **Quick Fit:** one standard size per category, which is approximate. **Personal Fit:** exact measurements. |
| **Quick size** | `QuickSize` · `quick_sizes` | XS / S / M / L / XL, chosen per fit category in Quick Fit. |
| **Size system** | `SizeSystem` · `size_system` | EU or US. Picked by the user before Quick Fit sizes. |
| **Size reference** | `SizeReference` · `size_references` | The approximate body range in cm for a standard size, always with a named **source**. Quick Fit uses it. |
| **Fit outcome** | `FitOutcome` | The result of comparing a profile with one listing. **MATCH:** every critical measurement is within tolerance. **UNCERTAIN:** data is missing or not enough to judge. **MISMATCH:** a critical measurement is outside tolerance (Personal Fit only). |
| **Rule set** | `RuleSet` (planned, Phase 9) | The complete, validated values the engine uses for one check. Plain data, never code. Built from the **defaults** in code, or from a published version. |
| **Published version** | `rule_set_versions` (planned, Phase 9) | An immutable snapshot of a rule set. One is active at a time. Rollback publishes an older snapshot as a new version. |
| **Content block** | planned, Phase 9 | One typed piece of page content (e.g. heading, FAQ item) or a predefined section, from a fixed registry. Holds no HTML or code. |
| **Fit feedback** | DB enum `fit_outcome` on `feedback.fit` | What the user reports after buying: too tight / fits well / too loose. *Not the same thing as Fit outcome.* The database type name predates the redesign. |
