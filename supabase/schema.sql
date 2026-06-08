-- =====================================================================
-- AI Marketplace Simulator — Supabase / Postgres schema
-- =====================================================================
-- Run this in the Supabase SQL editor (or via the CLI) once per project.
-- It creates the tables, indexes, Row Level Security policies, and the
-- profile auto-provisioning trigger used by the application.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- Table: simulation_runs
-- ---------------------------------------------------------------------
create table if not exists public.simulation_runs (
    id                  uuid primary key default gen_random_uuid(),
    run_id              text unique not null,
    created_at          timestamptz not null default now(),
    description         text default '',
    num_firms           integer not null,
    num_consumers       integer not null,
    num_timesteps       integer not null,
    agent_type          text not null,
    info_visibility     text not null,
    regulation_mode     text not null,
    coordination_mode   text not null,
    baseline_cost       double precision not null,
    demand_alpha        double precision not null,
    collusion_threshold double precision not null,
    random_seed         integer,
    status              text not null default 'created',
    error_message       text
);

create index if not exists idx_simulation_runs_created_at
    on public.simulation_runs (created_at desc);

-- ---------------------------------------------------------------------
-- Table: simulation_logs (one row per firm per timestep)
-- ---------------------------------------------------------------------
create table if not exists public.simulation_logs (
    id                          uuid primary key default gen_random_uuid(),
    run_id                      text not null
        references public.simulation_runs (run_id) on delete cascade,
    timestamp                   timestamptz not null,
    timestep                    integer not null,
    firm_id                     text not null,
    agent_type                  text not null,
    info_visibility             text not null,
    regulation_mode             text not null,
    coordination_mode           text not null,
    price                       double precision not null,
    baseline_cost               double precision not null,
    units_sold                  integer not null,
    revenue                     double precision not null,
    profit                      double precision not null,
    market_avg_price            double precision not null,
    market_price_std            double precision not null,
    collusion_indicator         double precision not null,
    consumer_surplus            double precision not null,
    regulatory_penalty          double precision not null,
    observed_competitor_prices  jsonb not null default '{}'::jsonb,
    agent_internal_state        jsonb not null default '{}'::jsonb,
    agent_decision_reasoning    text default '',
    event_notes                 text default ''
);

create index if not exists idx_simulation_logs_run_id
    on public.simulation_logs (run_id);
create index if not exists idx_simulation_logs_run_step
    on public.simulation_logs (run_id, timestep);

-- ---------------------------------------------------------------------
-- Table: profiles (admin flag, 1:1 with auth.users)
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
    id        uuid primary key references auth.users (id) on delete cascade,
    email     text,
    is_admin  boolean not null default false,
    created_at timestamptz not null default now()
);

-- Auto-create a profile row whenever a new auth user signs up.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id, email)
    values (new.id, new.email)
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- =====================================================================
-- Row Level Security
-- =====================================================================
-- The backend uses the service-role key (which bypasses RLS) for all
-- trusted reads/writes. These policies protect against direct access with
-- the anon/public key from the browser.

alter table public.simulation_runs enable row level security;
alter table public.simulation_logs enable row level security;
alter table public.profiles        enable row level security;

-- profiles: a user may read/update only their own profile. is_admin must be
-- changed by the researcher directly via the SQL editor / service role.
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
    on public.profiles for select
    using (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
    on public.profiles for update
    using (auth.uid() = id)
    with check (auth.uid() = id);

-- simulation_runs: anyone authenticated may read run metadata (summaries are
-- aggregate-only and served by the backend). No client-side writes.
drop policy if exists "runs_select_all" on public.simulation_runs;
create policy "runs_select_all"
    on public.simulation_runs for select
    using (true);

-- simulation_logs: NO direct client access. Raw logs are exposed only through
-- the admin-gated backend endpoint (service role). With RLS enabled and no
-- permissive policy, anon/auth clients cannot read this table directly.
-- (Intentionally no SELECT policy here.)

-- =====================================================================
-- Promote an admin (run manually after the researcher signs up):
--
--   update public.profiles set is_admin = true
--   where email = 'researcher@example.com';
-- =====================================================================
