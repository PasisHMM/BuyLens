# Buy Lens

Paste a clothing link and get a **BUY / CONSIDER / SKIP** verdict based on your exact measurements, the real total price, and seller risk.

Full design and plan: [`../buy-lens-architecture-and-plan.md`](../buy-lens-architecture-and-plan.md)

---

## Status

| Phase | Status | Report |
|---|---|---|
| 1. Foundation & setup | ✅ Done; CI green on GitHub | this README |
| 2. Core analyzer engine | ✅ Built and unit-tested · ⏳ needs migration + Redis + Gemini key to run live | [`docs/phase-2-report.md`](docs/phase-2-report.md) |
| 3. Frontend | Not started | |
| 4. Feedback & memory loop | Not started (tables and memory reads are in place) | |

---

## Repository layout

```
buy-lens/
├── apps/web/                 # Next.js app (Phase 3; placeholder for now)
├── services/api/             # FastAPI app + arq check worker
│   ├── app/
│   │   ├── main.py           # create_app(): CORS, routers, DB/Redis lifespan
│   │   ├── worker.py         # arq WorkerSettings: runs the check pipeline
│   │   ├── queue.py          # job queue + per-user rate limiter
│   │   ├── llm/              # provider layer: Gemini (default), Anthropic
│   │   ├── pipeline/         # extract → source → price → fit → seller risk → rules → copy
│   │   ├── config.py         # pydantic-settings (env vars / .env)
│   │   ├── auth.py           # Supabase JWT verification (JWKS or legacy HS256)
│   │   ├── db.py             # asyncpg pool; user_tx() runs queries under RLS
│   │   ├── units.py          # in ↔ cm (storage is always cm)
│   │   ├── log_config.py     # JSON logs; request bodies are never logged
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── repos/            # SQL access (Protocol + Postgres implementation)
│   │   └── routers/          # /healthz, /v1/profile, /v1/brands, /v1/checks
│   ├── tests/                # unit tests (in-memory repos) + integration/ (real Postgres)
│   └── scripts/export_openapi.py
├── packages/contracts/openapi.json   # API contract for the web app's generated TS types
├── supabase/
│   ├── migrations/           # schema, RLS policies, grants
│   ├── seed.sql              # brands + seller allow-list (idempotent)
│   └── ci/auth_stub.sql      # stand-in for Supabase's auth schema in CI only
└── .github/workflows/ci.yml
```

---

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/healthz` | — | Liveness |
| `GET` | `/v1/profile` | Bearer | Returns the profile in the user's unit. Returns `404` if there's no profile yet, and the web app then routes to `/preferences` |
| `PUT` | `/v1/profile` | Bearer | Saves measurements, unit and brands. Returns `204`, or `422` for invalid input |
| `GET` | `/v1/brands?q=&limit=` | — | Brand search for the "+ Add brand" combobox |
| `POST` | `/v1/checks` | Bearer | `{"url"}` → `202 {id, status}`. Returns `422` for an unsupported store or bad link, `409` with no saved measurements, `429` when rate-limited |
| `GET` | `/v1/checks/{id}/events` | Bearer | Server-Sent Events for the loading modal (4 steps, then `complete` / `failed` / `cancelled`); supports `Last-Event-ID` |
| `GET` | `/v1/checks/{id}` | Bearer | Full result: verdict, headline, explanation, why-not lines, up to 3 options with Price / Fit / Seller cards |
| `GET` | `/v1/checks?limit=5` | Bearer | Recent checks ("A recent check" card) |
| `DELETE` | `/v1/checks/{id}` | Bearer | Cancel a queued or running check |

`PUT /v1/profile` body, matching the Preferences screen:

```json
{ "unit": "in", "waist": 26, "inseam": 30, "hips": 36, "brand_ids": ["<uuid>", "<uuid>"] }
```

- `hips` is optional. Sending `null` deletes a previously saved value.
- Values are converted to cm and checked against plausible adult ranges. A unit mix-up (for example 26 sent with `"unit": "cm"`) returns `422` with "Check the unit (IN / cm)."
- Unknown fields, unknown brand IDs, and more than 30 brands are rejected.

Interactive docs: `http://localhost:8000/docs` (disabled when `ENV=prod`).

---

## Security model

- **Authentication.** Every Supabase session, including **anonymous sign-ins**, is a JWT. The API checks the signature, `iss`, `aud` (`authenticated`) and `exp`. Asymmetric keys are verified through the project's JWKS endpoint, and the legacy HS256 secret is supported as a fallback.
- **Row-level security applies to the API too.** `Database.user_tx()` runs each request's transaction as the `authenticated` role with the caller's `sub` claim set. The same RLS policies that protect browser clients therefore protect the API, so a missing `where user_id = …` can't leak another user's measurements. The integration tests check this directly.
- **Catalog tables** (`brands`, `sellers`, `products`, `listings`) are read-only for users. Only the service role, used by the check worker, can write to them.
- **No measurements in logs.** Request bodies are never logged.

---

## Setup

### 1. Supabase project (manual, one-time)

1. Create a project at [supabase.com](https://supabase.com).
2. **Authentication → Sign In / Providers → enable "Allow anonymous sign-ins".** The designs have no login screen, so the app signs users in anonymously.
3. Apply the schema and seed data. Use either **SQL Editor** (paste and run each file in `supabase/migrations/` in name order, then `supabase/seed.sql`) or the Supabase CLI:
   ```bash
   npx supabase link --project-ref <project-ref>
   ```
   ```bash
   npx supabase db push
   ```
   > Never run `supabase/ci/auth_stub.sql` against Supabase. It exists only for plain-Postgres CI.
4. Turn on **Supabase CAPTCHA protection** (Authentication → Attack Protection) before going public. Anonymous sign-ins are otherwise easy to abuse.

### 2. API

Requires [uv](https://docs.astral.sh/uv/). It installs a suitable Python (3.12 or newer) automatically.

```bash
cd services/api
```
```bash
uv sync
```
```bash
cp .env.example .env
```

Fill in `DATABASE_URL` and `SUPABASE_URL` in `.env`. Use the direct or **session-pooler** connection string, not the transaction pooler on port 6543. Phase 2 also needs `REDIS_URL` and a Gemini key and model IDs (see `.env.example`). Then start the API and, in a second terminal, the check worker:

```bash
uv run uvicorn app.main:create_app --factory --reload
```
```bash
uv run arq app.worker.WorkerSettings
```

### 3. Checks (same as CI)

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q
```

Integration tests against your own Postgres, after applying `supabase/ci/auth_stub.sql`, the migrations and the seed:

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres uv run pytest -m integration
```

After changing any endpoint or schema, regenerate the API contract:

```bash
uv run python scripts/export_openapi.py
```

---

## Differences from the plan document (Phase 1)

- **Flat profile body.** `PUT /v1/profile` takes plain numbers (`"waist": 26`) instead of `{"value": 26}` objects, which is simpler for the form.
- **Plausibility check runs in cm** for every dimension instead of only checking the waist in inches.
- **`feedback.applied_delta` column added.** It stores the memory change made by each answer, so Phase 4 can reverse it when a user edits their feedback.
