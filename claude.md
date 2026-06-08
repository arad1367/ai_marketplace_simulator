# AI Marketplace Simulator – Agent-Based Pricing and Log Collection

## Overview

This project is a web application for simulating an AI-driven online marketplace.
Multiple firms deploy AI pricing agents that interact in a shared market with a
population of consumers.

The app must:

- Let users configure simulation parameters via a web UI.
- Run an agent-based simulation on the backend.
- Log detailed data for each time step and each firm to a **Supabase (Postgres)** database.
- Restrict raw data export (CSV) to an **admin-only** endpoint (only the researcher).
- Expose only **aggregate summaries** to normal users.

The logged data will be used for academic research:

- Study 1: quantitative analysis of simulation outputs.
- Study 2: qualitative / digital-trace analysis (especially agent reasoning text and event notes).

This README is detailed enough that an AI coding assistant can implement the full application.

---

## Tech Stack

Preferred stack (can be adapted, but must meet these requirements):

- Backend: **Python** (FastAPI preferred; Flask acceptable)
- Frontend: **React** (Vite or Create React App) or server-rendered templates if simpler
- Database: **Supabase** (Postgres)
- ORM/DB layer: SQLAlchemy or equivalent (or direct Postgres client)
- Auth: **Supabase Auth** (email/password)

The app must be runnable locally (against a Supabase project) and deployable later.

---

## Core Concepts

### Simulation Run

A **Simulation Run** is a single execution of the marketplace model with a given set of parameters.

- Identified by `run_id` (string, unique, e.g., `"run_2026_06_08_001"`).
- Has metadata: description, created_at, parameters, status.
- Produces many log rows (one row per firm per timestep).

### Marketplace

- Consists of:
  - A set of **firms** (each with an AI pricing agent).
  - A population of **consumers**.
- Simulated in discrete timesteps (0, 1, 2, ..., T).

### AI Agents (Firms)

- Each firm is controlled by an AI pricing agent.
- At each timestep, an agent chooses a `price` based on:
  - Its internal state (e.g., last profit, last price, last demand).
  - Observed competitor prices (depending on information visibility).
- For logging, each agent must provide:
  - Numeric decision: `price`.
  - Internal state summary: JSON-serializable dict.
  - Short natural-language reasoning string, e.g.,  
    `"Increased price because last period profit increased and competitors also raised prices."`

### Consumers

- Represented as a population with heterogeneous preferences.
- Demand model can be simple but must produce at each timestep:
  - `units_sold` per firm.
  - Approximate `consumer_surplus` (a numeric estimate).

---

## User Roles and Access Control

Two roles:

1. **Admin (researcher)**
   - Has a Supabase auth user with `is_admin = true` in the `profiles` table.
   - Can:
     - View list of all runs.
     - Download full raw logs as CSV.
     - Access admin-only API endpoints.

2. **Regular User (participant)**
   - Can:
     - Configure and run simulations through the UI.
     - View summary statistics and simple charts for _their_ run.
   - Cannot:
     - Download CSV.
     - Access raw logs or admin endpoints.

### Implementation Details

- Use Supabase Auth for login.
- Create a `profiles` table with an `is_admin` boolean field.
- The backend must:
  - Check `is_admin` for any endpoint that returns raw logs/CSV.
- The frontend must:
  - Show admin UI (admin page + "Download CSV" buttons) **only** if the user is authenticated and `is_admin` is true.

---

## Frontend Requirements

### 1. Simulation Configuration Page (Public)

Route: `/`

Form fields:

- General parameters:
  - `num_firms` (integer, default 3, min 2, max 10)
  - `num_consumers` (integer, default 1000)
  - `num_timesteps` (integer, default 50, max 500)
  - `random_seed` (integer, optional)
  - `run_description` (text area)

- Agent design parameters:
  - `agent_type` (dropdown):
    - `profit_maximizer`
    - `revenue_maximizer`
    - `market_share_maximizer`
  - `info_visibility` (dropdown):
    - `local` (only own history)
    - `global` (all competitors’ current prices)
    - `noisy_global` (competitor prices with noise)
  - `regulation_mode` (dropdown):
    - `none`
    - `soft_cap` (hard cap on price relative to cost)
    - `penalty_on_collusion` (penalty when collusion indicator is high)
  - `coordination_mode` (dropdown):
    - `independent`
    - `shared_model`

- Advanced parameters (include in form, even if simple in v1):
  - `baseline_cost` (float, default 6.0)
  - `demand_alpha` (float, price sensitivity, default 1.0)
  - `collusion_threshold` (float, default 0.8)

Behavior:

- “Run Simulation” button:
  - Sends POST to `/api/run-simulation` with JSON body containing all fields above.
- Show status:
  - `Not started` → `Running` → `Completed` or `Error`.
- On success:
  - Display `run_id`.
  - Display summary:
    - Number of timesteps, number of firms, total logged rows.
  - Display minimal visualization (nice-to-have):
    - Line chart of average market price over time (data from `/api/run/{run_id}/summary`).

Important:

- **No** CSV download on this page.
- Only summary data is visible to regular users.

### 2. Admin Page (Protected)

Route: `/admin`

- Requires login via Supabase Auth.
- After login:
  - Check `is_admin` via `profiles` table.
  - If not admin: redirect or show “Access denied”.

Admin view:

- Table listing recent simulation runs:
  - Columns: `run_id`, `created_at`, `description`, `num_timesteps`, `status`.
- For each run:
  - Button: “Download CSV”:
    - Calls `GET /api/admin/run/{run_id}/download-csv`.

---

## Backend API Requirements

### 1. POST /api/run-simulation

**Access:** Public (any user)

**Input (JSON):**

- `num_firms` (int)
- `num_consumers` (int)
- `num_timesteps` (int)
- `random_seed` (int, optional)
- `run_description` (string)
- `agent_type` (string)
- `info_visibility` (string)
- `regulation_mode` (string)
- `coordination_mode` (string)
- `baseline_cost` (float)
- `demand_alpha` (float)
- `collusion_threshold` (float)

**Behavior:**

1. Create a new record in `simulation_runs`:
   - Generate unique `run_id`.
   - Set status: `"created"` → `"running"` → `"completed"` or `"failed"`.
2. Initialize firms and consumers.
3. For each timestep from 0 to `num_timesteps - 1`:
   - For each firm:
     - Determine observed competitor prices based on `info_visibility`.
     - Choose price using a heuristic based on `agent_type`:
       - Example heuristic:
         - If last profit increased → increase price slightly.
         - If last profit decreased → decrease price slightly.
     - Apply regulatory rules:
       - If `regulation_mode` = `soft_cap`, cap `price` at `baseline_cost + max_margin`.
   - Compute demand and consumer surplus:
     - Each consumer has a `baseline_quality` for each firm and utility:
       - `utility = baseline_quality - demand_alpha * price` (simple linear utility).
     - Assign each consumer to the firm with highest utility (or no purchase if all negative).
     - Aggregate `units_sold` per firm.
     - Compute `revenue`, `profit`, and `consumer_surplus` (approximate).
   - Compute market-level metrics:
     - `market_avg_price`
     - `market_price_std`
     - `collusion_indicator` per firm (normalized similarity to competitor prices; higher = more similar).
   - Apply regulatory penalty:
     - If `regulation_mode` = `penalty_on_collusion` and `collusion_indicator > collusion_threshold`, set `regulatory_penalty` > 0 and reduce effective profit.
   - Create:
     - `observed_competitor_prices` (JSON dict per firm).
     - `agent_internal_state` (JSON; e.g., last price, last profit, last demand).
     - `agent_decision_reasoning` (short string explaining the price move).
     - `event_notes` (e.g., `"Emergent synchronized price increase."` or empty).
   - Insert one row per firm into `simulation_logs`.

4. On success:
   - Set `simulation_runs.status = "completed"`.

**Output (JSON):**

Example:

```json
{
  "run_id": "run_2026_06_08_001",
  "num_rows": 150,
  "status": "completed"
}
```

---

### 2. GET /api/run/{run_id}/summary

**Access:** Public / any logged-in user

**Behavior:**

- Return aggregated summary statistics for the run, **not** raw logs.

Example output:

```json
{
  "run_id": "run_2026_06_08_001",
  "num_firms": 3,
  "num_timesteps": 50,
  "avg_market_price_by_timestep": [10.3, 10.9, 11.1],
  "avg_consumer_surplus_by_timestep": [500.0, 480.0, 470.0],
  "avg_collusion_indicator_by_timestep": [0.1, 0.8, 0.85]
}
```

---

### 3. GET /api/admin/run/{run_id}/download-csv

**Access:** Admin only

Behavior:

- Verify current user is authenticated via Supabase.
- Join with `profiles` and check `is_admin = true`.
- If not admin → return HTTP 403.
- If admin → query all `simulation_logs` rows where `run_id = {run_id}`.
- Stream them as a CSV file with columns:

CSV columns (exact names, types in parentheses):

- `run_id` (string)
- `timestamp` (ISO datetime string)
- `timestep` (int)
- `firm_id` (string)
- `agent_type` (string)
- `info_visibility` (string)
- `regulation_mode` (string)
- `coordination_mode` (string)
- `price` (float)
- `baseline_cost` (float)
- `units_sold` (int)
- `revenue` (float)
- `profit` (float)
- `market_avg_price` (float)
- `market_price_std` (float)
- `collusion_indicator` (float)
- `consumer_surplus` (float)
- `regulatory_penalty` (float)
- `observed_competitor_prices` (JSON string)
- `agent_internal_state` (JSON string)
- `agent_decision_reasoning` (text)
- `event_notes` (text)

**Example CSV snippet (conceptual):**

```csv
run_id,timestamp,timestep,firm_id,agent_type,info_visibility,regulation_mode,coordination_mode,price,baseline_cost,units_sold,revenue,profit,market_avg_price,market_price_std,collusion_indicator,consumer_surplus,regulatory_penalty,observed_competitor_prices,agent_internal_state,agent_decision_reasoning,event_notes
"run_2026_06_08_001","2026-06-08T10:30:00Z",0,"A","profit_maximizer","global","none","independent",10.0,6.0,100,1000.0,400.0,10.3,0.25,0.10,500.0,0.0,"{""B"": 10.5, ""C"": 10.4}","{""last_profit"": 380.0, ""last_price"": 9.8}","Set price near competitor mean to explore demand at slightly higher margin.",""
"run_2026_06_08_001","2026-06-08T10:30:00Z",0,"B","profit_maximizer","global","none","independent",10.5,6.0,95,997.5,427.5,10.3,0.25,0.10,498.0,0.0,"{""A"": 10.0, ""C"": 10.4}","{""last_profit"": 410.0, ""last_price"": 10.3}","Slightly higher than competitors to test elasticity.",""
```

Values are illustrative; schema and types are what matter.

---

## Simulation Logic (Minimum Behavior)

The RL/agent logic can be heuristic-based in v1; the important part is consistent, state-dependent behavior.

### Initialization

- Create `num_firms` firms with IDs `"A"`, `"B"`, `"C"`, etc.
- Assign all firms the same `baseline_cost` for now.
- Create `num_consumers` each with a random `baseline_quality` per firm (e.g., normal or uniform distribution).

### Per-timestep Loop

For each timestep `t`:

1. **Agent decision** (for each firm):
   - Input:
     - Last price
     - Last profit
     - Observed competitor prices (depends on `info_visibility`)
   - Heuristic example (profit_maximizer):
     - If last_profit increased more than a small threshold → increase price by `+delta`.
     - If last_profit decreased → decrease price by `-delta`.
     - Keep price in [baseline_cost, some max_price].
   - For other `agent_type`s:
     - Revenue_maximizer: similar but focus on `revenue`.
     - Market_share_maximizer: adjust price to increase units_sold.

2. **Apply regulation**:
   - `soft_cap`: cap price at `baseline_cost + max_margin`.
   - `penalty_on_collusion`: compute collusion and apply penalty later.

3. **Demand and consumer surplus**:
   - For each consumer, compute utility for each firm:
     - `utility = baseline_quality_firm - demand_alpha * price_firm`.
   - Consumer chooses firm with highest utility (or no purchase).
   - Aggregate `units_sold`, `revenue`, `profit` for each firm.
   - Approximate `consumer_surplus`.

4. **Market metrics**:
   - `market_avg_price`: mean of firm prices.
   - `market_price_std`: standard deviation.
   - `collusion_indicator` per firm: normalized similarity between firm price and mean competitor price (0–1).

5. **Regulatory penalty**:
   - If `regulation_mode = "penalty_on_collusion"` and `collusion_indicator > collusion_threshold`, set `regulatory_penalty` positive and reduce profit.

6. **Logging**:
   - For each firm, log all fields to `simulation_logs`.

### Termination

- After last timestep: set `simulation_runs.status = "completed"`.

---

## Supabase / Postgres Schema

### Table: simulation_runs

Columns:

- `id` (UUID or serial primary key)
- `run_id` (text, unique)
- `created_at` (timestamptz, default now())
- `description` (text)
- `num_firms` (integer)
- `num_consumers` (integer)
- `num_timesteps` (integer)
- `agent_type` (text)
- `info_visibility` (text)
- `regulation_mode` (text)
- `coordination_mode` (text)
- `baseline_cost` (double precision)
- `demand_alpha` (double precision)
- `collusion_threshold` (double precision)
- `random_seed` (integer, nullable)
- `status` (text) -- 'created', 'running', 'completed', 'failed'
- `error_message` (text, nullable)

### Table: simulation_logs

Columns:

- `id` (UUID or serial primary key)
- `run_id` (text, foreign key → simulation_runs.run_id)
- `timestamp` (timestamptz)
- `timestep` (integer)
- `firm_id` (text)
- `agent_type` (text)
- `info_visibility` (text)
- `regulation_mode` (text)
- `coordination_mode` (text)
- `price` (double precision)
- `baseline_cost` (double precision)
- `units_sold` (integer)
- `revenue` (double precision)
- `profit` (double precision)
- `market_avg_price` (double precision)
- `market_price_std` (double precision)
- `collusion_indicator` (double precision)
- `consumer_surplus` (double precision)
- `regulatory_penalty` (double precision)
- `observed_competitor_prices` (jsonb)
- `agent_internal_state` (jsonb)
- `agent_decision_reasoning` (text)
- `event_notes` (text)

### Table: profiles (for admin flag)

- `id` (uuid, primary key, references `auth.users.id`)
- `is_admin` (boolean, default false)

Use `profiles.is_admin` to gate admin endpoints.

---

## Example JSON Log Data (for the Assistant)

Target structure for each log row (JSON-like):

```json
{
  "run_id": "run_2026_06_08_001",
  "timestamp": "2026-06-08T10:30:00Z",
  "timestep": 0,
  "firm_id": "A",
  "agent_type": "profit_maximizer",
  "info_visibility": "global",
  "regulation_mode": "none",
  "coordination_mode": "independent",
  "price": 10.0,
  "baseline_cost": 6.0,
  "units_sold": 100,
  "revenue": 1000.0,
  "profit": 400.0,
  "market_avg_price": 10.3,
  "market_price_std": 0.25,
  "collusion_indicator": 0.1,
  "consumer_surplus": 500.0,
  "regulatory_penalty": 0.0,
  "observed_competitor_prices": { "B": 10.5, "C": 10.4 },
  "agent_internal_state": { "last_profit": 380.0, "last_price": 9.8 },
  "agent_decision_reasoning": "Set price near competitor mean to explore demand at slightly higher margin.",
  "event_notes": ""
}
```

As long as the implemented app matches these interfaces and data structures, it will be suitable for the planned research and admin-only data access.

---

## Running the App (High-Level)

The final repo should include this README plus:

- Instructions for setting Supabase env vars (URL, anon key, service key).
- How to run backend:
  - e.g., `uvicorn main:app --reload`
- How to run frontend:
  - e.g., `npm install && npm run dev`
- How to create an admin user and set `is_admin = true` in `profiles`.
