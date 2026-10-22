# Phase 2 Report: Core Analyzer Engine

> **Scope:** link ingestion, page fetching and parsing, cross-seller sourcing, the deterministic Price / Fit / Seller checks, the verdict rules, LLM-written copy, live progress, and the check API and worker.
> **Plan reference:** [`../../buy-lens-architecture-and-plan.md`](../../buy-lens-architecture-and-plan.md), Phase 2 (steps 2.0–2.7)

---

## 1. Summary

A pasted product link now becomes a stored verdict with up to 3 ranked options. The loading modal streams the 4 design steps live, and the results endpoint returns everything the **Product results** screen shows.

| | Result |
|---|---|
| Unit tests | ✅ **145 passed**, no network, database, Redis or model calls |
| Postgres integration tests | ⏳ **10 tests** (6 from Phase 1, 4 new) skip locally and run in the CI `database` job |
| Lint and types | ✅ `ruff` clean, `mypy --strict` clean (45 source files) |
| New migration | ✅ Parses with the real Postgres parser (`pglast`) |
| Gemini schemas | ✅ All 3 LLM output schemas convert with the `google-genai` SDK (checked offline, no API call) |
| **Live run** | ❌ **Not done.** No Redis, Gemini key or reachable test store on this machine. See [§6](#6-what-still-needs-a-live-test). |

The tests reproduce the design's example end to end: Levi's 501 Original Cropped, W26 / L30, $98 at the official store, no hip measurement. The result is **CONSIDER**, headline *"Check the hips before you buy."*, with the fit card showing waist 26 vs 27, inseam 30 vs 30 and hips 36 vs "—".

---

## 2. How a check runs

```
POST /v1/checks {url}
  │ normalize URL (https, tracking params stripped) · seller must be allow-listed
  │ profile required · rate limits (10 per 10 min, 2 at a time)
  │ snapshot profile + memory → check_runs (queued) → arq job
  ▼
Worker: run_check(run_id)            ── progress events → Redis Stream → SSE
  1. product  extract listing (adapter → JSON-LD → meta → size-chart table → LLM)
              choose the user's size (e.g. W26 / L30)
  2. prices   same product at other allow-listed sellers → totals → market average
  3. fit      deterministic Fit Check per listing (brand size chart reused)
  4. seller   seller data + review summary (LLM, cached per listing)
  ─────────
  rank by overall value → verdict rules → copy (LLM, checked; template fallback)
  → check_runs (done) + check_options ×3 → event "complete"
```

Events the loading modal receives (`GET /v1/checks/{id}/events`):

| Step | Event `detail` when done (example from the tests) |
|---|---|
| 1 of 4: product | `501® Original Cropped Jeans, medium wash` |
| 2 of 4: prices | `$97.00 total across 2 sellers` |
| 3 of 4: fit | `Waist, inseam compared` |
| 4 of 4: seller | `Reviews and return policy checked` |
| end | `complete` · `failed` (with a user-safe message) · `cancelled` |

Streams can be replayed: a page that connects late, or reconnects with `Last-Event-ID`, still sees every step. If the stream has expired, the endpoint falls back to the run's status in the database.

---

## 3. What was built (by plan step)

| Step | What | Files |
|---|---|---|
| **2.0 LLM provider layer** | One `LLM.structured()` interface, with Gemini as the default (JSON-schema output) and Anthropic as the alternative (forced tool call). Switch with `LLM_PROVIDER`. Any failure becomes `LLMError`, so callers always have a fallback. | `app/llm/` |
| **2.1 Link ingestion & jobs** | `POST /v1/checks` (validation, allow-list, profile snapshot, rate limits). `GET` for result, recent checks and SSE events; `DELETE` to cancel. An arq worker runs jobs with job id = run id (no double runs), a 90 s timeout, and no silent retries. | `app/routers/checks.py`, `app/repos/checks.py`, `app/queue.py`, `app/worker.py` |
| **2.2 Pipeline** | The 4 visible steps plus rank, decide, copy and persist. Cancel takes effect between steps. Store and network errors become clear user messages; unexpected errors are logged and shown generically. | `app/pipeline/run_check.py`, `progress.py`, `store.py` |
| **2.3 Extraction** | A polite fetcher: https only, allow-listed hosts (also enforced on every redirect), robots.txt, per-host spacing, 3 MB cap. Then the Shopify `.js` adapter, JSON-LD (`Product` / `ProductGroup`, `@graph`, offers, shipping, ratings, reviews), OpenGraph fallback, and a deterministic **size-chart table parser** (rows or columns, in/cm, ranges, ½, flat garment measurements doubled). The **LLM fallback** must copy numbers literally: any number not found in the page text is dropped. | `app/pipeline/fetch.py`, `extract/` |
| **2.4 Fit Check** | Size choice limited to sizes the store sells, with length variants (`26x30`) setting the inseam. Separate tolerances for *garment* charts (need ease) and *body* charts (should match). Stretch-fabric allowance and per-brand fit-memory adjustment. Missing measurements stay "—" and lower confidence. | `app/pipeline/fitting.py` |
| **2.5 Price & ranking** | Total = price + shipping. Shipping comes from the page or a *verified* seller rule, otherwise "unknown" and never assumed free. Market average is a trimmed mean over at least 3 same-product, same-currency listings (shipping excluded). Ranking is by overall value with weights personalized by decision memory. | `app/pipeline/pricing.py`, `rules.py` |
| **2.6 Verdict rules** | SKIP / CONSIDER / BUY from reason codes (table below). The LLM never decides. | `app/pipeline/rules.py` |
| **2.7 Copy** | The template copy always works and reproduces the design wording. The LLM may only reword it, and its output is rejected unless it passes a guard: no "guaranteed fit", no contradicting the verdict, it names the missing measurement, every $ amount is real, and lengths are bounded. One retry, then the template. "Why not BUY / SKIP?" is always deterministic. | `app/pipeline/narrate.py` |
| Seller risk | Seller trust, review rating and count, verified return policy, and an LLM review summary (themes, fit signal, repeated red flags). | `app/pipeline/seller_risk.py` |
| Sourcing | Search adapters per seller (Shopify today), same-product matching (variant GTIN overlap or brand + MPN = exact; same brand + ~identical name + same color = likely), plus stored listings of the same product. | `app/pipeline/sourcing.py` |

### Verdict rules

| Reason code | Verdict | Trigger |
|---|---|---|
| `FIT_MISMATCH` | **SKIP** | Any measurement outside its range (tight, loose, short or long) |
| `SELLER_HIGH_RISK` | **SKIP** | Trust under 3.0, rating under 3.5 with 20+ reviews, or 2+ repeated red flags in reviews |
| `OVERPRICED` | **SKIP** | More than 25% above the market average |
| `FIT_DATA_MISSING` | CONSIDER | A measurement you saved isn't published for this item (design: hips) |
| `FIT_UNCERTAIN` | CONSIDER | Only partial size data, or reviews say it runs small or large |
| `ABOVE_MARKET` | CONSIDER | More than 5% above the market average |
| `RETURN_RISK` | CONSIDER | Medium seller risk, returns not free, or **return policy not verified yet** |
| none | **BUY** | Everything passes |

### Database changes (`supabase/migrations/20261022000000_analyzer_engine.sql`)

- **Grants for `service_role`:** the worker writes as `service_role`.
- **New columns:** `products.image_url`, `listings.external_id`, `listings.extract` (the full parsed listing, reused as a comparable), and `sellers.shipping_policy`.
- **Indexes:** unique `(product_id, seller_id)` on listings, and a GTIN index on products.
- **Phase 1 bug fix:** `unique nulls not distinct (brand_id, mpn)` treated **every product with no brand and no MPN as the same product**. It's replaced by a partial unique index that applies only when an MPN is known.

---

## 4. Findings that affect the product

These came out of building against real-world constraints. Each one changes what users will actually see.

1. **Cross-seller search will rarely find anything yet.**
   - Only Shopify stores have a search adapter, and Shopify's default `robots.txt` usually disallows `/search`. The fetcher respects robots.txt, so it will skip those searches. Check this per store.
   - None of the 5 seeded sellers uses the `shopify` adapter.
   - **Effect:** most checks will show **1 option**, and no market average (it needs 3 or more listings), until real sourcing exists.
   - **Next step (needs a decision):** per-seller product feeds or affiliate APIs (for example the stores' affiliate programs or a shopping-search API), or sitemap-based lookup, which robots.txt usually allows.
2. **Big retailers often block bots.** A `403` or `429` becomes "The store blocked our check. Try again later." Expect this from some seeded stores (large brand sites commonly use bot protection), and test each one. Official feeds or APIs are the robust fix.
3. **Size charts often aren't in the page HTML.** Many stores load them in a modal or on a separate page. The table parser and LLM can only use what's in the fetched HTML. A headless-browser fallback (Playwright) was **deferred**: it's heavy, and it doesn't solve bot walls.
4. **Every verdict is at most CONSIDER until seller data is verified.** The seed leaves return policies as `{"verified": false}` on purpose, which triggers `RETURN_RISK`. Fill in `return_policy`, `shipping_policy` and `trust_rating` for each seller from their published policies.
5. **Body vs garment charts matter.** Most brand charts give *body* measurements, while the design's "Garment 27" is a *garment* measurement. Both are handled with different tolerances. The parser marks a chart as garment only when the page says so ("garment measurements", "laid flat"), and treats it as body otherwise.

---

## 5. Differences from the plan document

| Plan | Built | Why |
|---|---|---|
| LLM writes headline, explanation **and** why-not lines | LLM may only reword the template's headline, explanation and option summaries. Why-not lines are always rule-generated. | Keeps the "explain, never decide" rule testable. The verdict page never waits on, or depends on, the LLM. |
| A product GTIN identifies a product | **Variant GTINs** are kept separately and matched on overlap | A GTIN identifies one size, so the first listed size would otherwise decide matching |
| Playwright fallback | Deferred | See finding 3 |
| Fit before seller risk, with no feedback between them | Fit runs at step 3; if reviews say it "runs small/large", the fit card is re-evaluated after step 4 | Keeps the design's step order and still uses the review signal |
| SSE with `EventSource` + cookie | Bearer header; the frontend should use a fetch-based SSE client (`@microsoft/fetch-event-source`) | No cookie auth exists yet; avoids putting tokens in URLs |
| LLM page input truncated to ~30k tokens | ~40k tokens (150k chars) of *cleaned* text | Gemini handles long input well; scripts and nav are stripped first |

---

## 6. What still needs a live test

- [ ] **Apply the new migration** in the Supabase SQL editor: `supabase/migrations/20261022000000_analyzer_engine.sql`.
- [ ] **Confirm the worker can act as `service_role`** by running this in the SQL editor. It should return `true`:
  ```sql
  select pg_has_role('postgres', 'service_role', 'member');
  ```
- [ ] **Push to GitHub** and confirm the CI `database` job passes. It runs the 4 new check-flow tests against Postgres, including a full pipeline run with real SQL.
- [ ] **Redis:** create one (for example Upstash) and set `REDIS_URL`.
- [ ] **Gemini:** set `GEMINI_API_KEY`, `GEMINI_FAST_MODEL` and `GEMINI_SMART_MODEL` (copy current IDs from Google AI Studio). Use a **billing-enabled key before any real user data**, because free-tier prompts may be used by Google.
- [ ] **Identify the bot:** set `FETCH_USER_AGENT` with a contact address.
- [ ] **Run both processes:**
  ```bash
  uv run uvicorn app.main:create_app --factory --reload
  ```
  ```bash
  uv run arq app.worker.WorkerSettings
  ```
- [ ] **Try one real product link per seeded store** and note which stores block us, which expose JSON-LD, and which have a size chart in the HTML. That list decides the sourcing work (finding 1).

> **Note:** this project folder is not a git checkout. Copy the changed files (listed below) into your GitHub clone before pushing.

---

## 7. Files

**New**

```
supabase/migrations/20261022000000_analyzer_engine.sql
services/api/app/llm/{__init__,base,gemini,anthropic}.py
services/api/app/pipeline/{models,urls,fetch,cache,fitting,pricing,seller_risk,rules,
                           narrate,sourcing,progress,store,run_check}.py
services/api/app/pipeline/extract/{__init__,text,attributes,jsonld,sizechart,shopify,llm}.py
services/api/app/{queue,worker}.py
services/api/app/{routers,repos,schemas}/checks.py
services/api/tests/{fakes,test_checks_api,test_llm}.py
services/api/tests/pipeline/{test_extract,test_sizechart,test_decision,test_run_check,test_fetch_urls}.py
services/api/tests/integration/test_checks_db.py
services/api/tests/fixtures/{brand_product,meta_only,text_only}.html   (synthetic pages)
docs/phase-2-report.md
```

**Changed**

```
services/api/app/{config,db,main}.py        settings, service_tx(), Redis/queue wiring
services/api/pyproject.toml, uv.lock        httpx, beautifulsoup4, redis, arq, google-genai, anthropic
services/api/.env.example                   Redis, LLM, fetch settings
packages/contracts/openapi.json             regenerated (checks endpoints)
README.md                                   status, layout, API, run instructions
```

---

## 8. Next

- **Phase 3 (frontend)** can start now: the results, recent-check and event contracts are in `packages/contracts/openapi.json`.
- **Sourcing decision.** Choose how to find the same product at other stores (feeds, affiliate APIs, a shopping-search API or sitemaps). This is the biggest gap between the engine and the "3 best options" in the design.
- **Seller data.** Verify return and shipping policies and trust ratings, otherwise BUY can never appear.
