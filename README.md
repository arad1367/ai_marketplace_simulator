# AI Marketplace Simulator

Agent-based simulation of an AI-driven online marketplace. Multiple firms deploy
AI pricing agents that compete for a population of consumers. The app runs the
simulation on a Python backend, logs detailed per-firm/per-timestep data to
**Supabase (Postgres)**, exposes **aggregate summaries** to everyone, and
restricts **raw-data CSV export** to an **admin (researcher)** account.

The logged data supports two research studies:

- **Study 1** — quantitative analysis of simulation outputs.
- **Study 2** — qualitative / digital-trace analysis of agent reasoning text and
  emergent-event notes.

---

## Architecture

```
Simulation APP/
├── backend/                 FastAPI app (simulation engine + API)
│   ├── app/
│   │   ├── main.py          FastAPI entrypoint, CORS, routers
│   │   ├── config.py        Env-based settings
│   │   ├── database.py      Supabase client factories (service / anon)
│   │   ├── auth.py          JWT verification + admin gate
│   │   ├── schemas.py       Pydantic request/response models
│   │   ├── services.py      Run + persist; summary/CSV queries
│   │   ├── csv_export.py    Streaming CSV serializer
│   │   ├── routers/
│   │   │   ├── simulation.py  POST /run-simulation, GET /run/{id}/summary
│   │   │   └── admin.py       GET /admin/runs, GET /admin/run/{id}/download-csv
│   │   └── simulation/      The model
│   │       ├── agents.py    Heuristic pricing agents (3 objectives)
│   │       ├── consumers.py Heterogeneous demand (vectorised NumPy)
│   │       ├── market.py    Price dispersion + collusion indicators
│   │       └── engine.py    Orchestrates the run
│   └── tests/               Engine unit tests (no DB needed)
├── frontend/                React + Vite SPA
│   └── src/
│       ├── pages/           ConfigPage (public), AdminPage (protected)
│       ├── components/      SummaryCharts, LoginForm
│       ├── context/         AuthContext (Supabase session + is_admin)
│       ├── api/client.js    Typed-ish fetch wrapper
│       └── lib/supabase.js  Browser Supabase client
├── supabase/schema.sql      Tables, indexes, RLS, profile trigger
├── api/index.py             Vercel serverless wrapper for the FastAPI app
├── vercel.json              Vercel build + routing
└── requirements.txt         Root deps for the Vercel Python function
```

### Access model

| Capability                         | Public user | Admin (researcher) |
| ---------------------------------- | :---------: | :----------------: |
| Configure & run a simulation       |     ✅      |         ✅         |
| View aggregate summary + charts    |     ✅      |         ✅         |
| List all runs                      |     ❌      |         ✅         |
| Download raw logs (CSV)            |     ❌      |         ✅         |

Admin endpoints verify the Supabase JWT and require `profiles.is_admin = true`.
Raw `simulation_logs` have **no client-side read policy** under RLS — they are
reachable only through the admin-gated backend (service role).

---

## 1. Supabase setup

1. Create a project at <https://supabase.com>.
2. Open **SQL Editor** and run the contents of [`supabase/schema.sql`](supabase/schema.sql).
   This creates `simulation_runs`, `simulation_logs`, `profiles`, indexes, RLS
   policies, and a trigger that auto-creates a profile row on signup.
3. Collect your keys from **Project Settings → API**:
   - `Project URL`
   - `anon` public key
   - `service_role` secret key (server-only)

### Create the admin (researcher) user

1. Start the app (below) and go to `/admin` → **Sign up** with your email/password
   (or create the user in **Supabase → Authentication → Users**).
2. In the SQL editor, promote the account:

   ```sql
   update public.profiles set is_admin = true
   where email = 'researcher@example.com';
   ```

---

## 2. Run the backend

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env     # then fill in your Supabase keys
uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/api/health>
Interactive API docs: <http://localhost:8000/docs>

`backend/.env`:

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
APP_ENV=development
```

### Run the tests

The engine tests need no database:

```bash
cd backend
pip install pytest numpy pydantic
pytest
```

---

## 3. Run the frontend

Requires Node 18+.

```bash
cd frontend
npm install
cp .env.example .env      # fill in the public Supabase values
npm run dev
```

Open <http://localhost:5173>. In dev, `/api/*` is proxied to the backend on
`:8000`, so no CORS configuration is needed locally.

`frontend/.env`:

```env
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_BASE_URL=                # empty in dev (uses the Vite proxy)
```

---

## 4. API reference

### `POST /api/run-simulation` — public

Body (JSON): `num_firms`, `num_consumers`, `num_timesteps`, `random_seed?`,
`run_description`, `agent_type`, `info_visibility`, `regulation_mode`,
`coordination_mode`, `baseline_cost`, `demand_alpha`, `collusion_threshold`.

Response:

```json
{ "run_id": "run_2026_06_08_103000_ab12", "num_rows": 150, "status": "completed" }
```

### `GET /api/run/{run_id}/summary` — public

Returns **aggregate-only** series (no raw rows): average market price, average
consumer surplus, and average collusion indicator per timestep, plus total
profit per firm.

### `GET /api/admin/runs` — admin only

Recent runs for the dashboard. Requires `Authorization: Bearer <supabase_jwt>`.

### `GET /api/admin/run/{run_id}/download-csv` — admin only

Streams all raw `simulation_logs` rows as CSV with the exact research column
schema. Returns `403` for non-admins.

---

## 5. The simulation model

- **Agents** use hill-climbing: keep moving price in the current direction while
  the objective improves; reverse when it worsens. Objective depends on
  `agent_type` (profit / revenue / units sold). With visible competitor prices
  they anchor partly toward the competitor mean; `shared_model` increases that
  anchoring (which can produce emergent synchronized pricing).
- **Consumers** each hold a heterogeneous `baseline_quality` per firm and choose
  the firm maximising `quality − demand_alpha · price`, or buy nothing if the
  best utility is negative. Vectorised with NumPy.
- **Market metrics**: `market_avg_price`, `market_price_std`, and a per-firm
  `collusion_indicator ∈ [0,1]` (price similarity to competitors).
- **Regulation**: `soft_cap` limits the price margin over cost; `penalty_on_collusion`
  subtracts a penalty from profit when alignment exceeds `collusion_threshold`.
- Every firm/timestep produces a row including `agent_decision_reasoning`
  (natural-language trace) and `event_notes` (emergent-event flags) for Study 2.

Runs are deterministic when `random_seed` is set.

---

## 6. Deploy to Vercel

This repo is configured for a single Vercel project that serves the React SPA
and the FastAPI backend as a Python serverless function (`api/index.py`).

1. Push the repo to GitHub and **Import** it in Vercel.
2. Set **Environment Variables** (Project → Settings → Environment Variables):
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` (backend)
   - `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (frontend build)
   - Leave `VITE_API_BASE_URL` empty (same-origin `/api`).
3. Deploy. `vercel.json` builds `frontend/dist` and routes `/api/*` to the
   Python function; all other paths fall back to the SPA.

> **Heavy runs & serverless limits.** A request runs the whole simulation
> synchronously. Very large configurations can approach the function
> `maxDuration` (60s here). For large research batches, host the backend on a
> long-running service (Render / Railway / Fly.io) and set `VITE_API_BASE_URL`
> to that backend instead.

---

## License

Provided for academic research use.
