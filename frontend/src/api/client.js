import { supabase } from "../lib/supabase";

// In dev, VITE_API_BASE_URL is empty and requests go through the Vite proxy.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function authHeader() {
  if (!supabase) return {};
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

async function handle(res) {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  /** Run a simulation. Public — no auth required. */
  async runSimulation(config) {
    const res = await fetch(`${API_BASE}/api/run-simulation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    return handle(res);
  },

  /** Aggregate-only summary for a run. Public. */
  async getSummary(runId) {
    const res = await fetch(`${API_BASE}/api/run/${runId}/summary`);
    return handle(res);
  },

  /** List recent runs. Admin only. */
  async listRuns() {
    const res = await fetch(`${API_BASE}/api/admin/runs`, {
      headers: { ...(await authHeader()) },
    });
    return handle(res);
  },

  /** Download raw CSV for a single run. Admin only. Returns a Blob. */
  async downloadCsv(runId) {
    const res = await fetch(`${API_BASE}/api/admin/run/${runId}/download-csv`, {
      headers: { ...(await authHeader()) },
    });
    if (!res.ok) {
      throw new Error(`Download failed (${res.status})`);
    }
    return res.blob();
  },

  /** Download ALL runs combined into one CSV. Admin only. Returns a Blob. */
  async downloadAllCsv() {
    const res = await fetch(`${API_BASE}/api/admin/download-all-csv`, {
      headers: { ...(await authHeader()) },
    });
    if (!res.ok) {
      throw new Error(`Download failed (${res.status})`);
    }
    return res.blob();
  },
};
