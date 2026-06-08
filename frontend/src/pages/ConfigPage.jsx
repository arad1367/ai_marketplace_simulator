import { useState } from "react";
import { api } from "../api/client";
import SummaryCharts from "../components/SummaryCharts";

const AGENT_TYPES = [
  { value: "profit_maximizer", label: "Profit maximizer" },
  { value: "revenue_maximizer", label: "Revenue maximizer" },
  { value: "market_share_maximizer", label: "Market-share maximizer" },
];
const INFO_VISIBILITY = [
  { value: "local", label: "Local (own history only)" },
  { value: "global", label: "Global (all competitor prices)" },
  { value: "noisy_global", label: "Noisy global (with observation noise)" },
];
const REGULATION_MODES = [
  { value: "none", label: "None" },
  { value: "soft_cap", label: "Soft cap (limit margin over cost)" },
  { value: "penalty_on_collusion", label: "Penalty on collusion" },
];
const COORDINATION_MODES = [
  { value: "independent", label: "Independent" },
  { value: "shared_model", label: "Shared model" },
];

const DEFAULTS = {
  num_firms: 3,
  num_consumers: 1000,
  num_timesteps: 50,
  random_seed: "",
  run_description: "",
  agent_type: "profit_maximizer",
  info_visibility: "global",
  regulation_mode: "none",
  coordination_mode: "independent",
  baseline_cost: 6.0,
  demand_alpha: 1.0,
  collusion_threshold: 0.8,
};

const STATUS = {
  idle: "Not started",
  running: "Running…",
  completed: "Completed",
  error: "Error",
};

export default function ConfigPage() {
  const [form, setForm] = useState(DEFAULTS);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [summary, setSummary] = useState(null);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function buildPayload() {
    return {
      num_firms: Number(form.num_firms),
      num_consumers: Number(form.num_consumers),
      num_timesteps: Number(form.num_timesteps),
      random_seed:
        form.random_seed === "" || form.random_seed === null
          ? null
          : Number(form.random_seed),
      run_description: form.run_description,
      agent_type: form.agent_type,
      info_visibility: form.info_visibility,
      regulation_mode: form.regulation_mode,
      coordination_mode: form.coordination_mode,
      baseline_cost: Number(form.baseline_cost),
      demand_alpha: Number(form.demand_alpha),
      collusion_threshold: Number(form.collusion_threshold),
    };
  }

  async function onSubmit(e) {
    e.preventDefault();
    setStatus("running");
    setError("");
    setResult(null);
    setSummary(null);
    try {
      const res = await api.runSimulation(buildPayload());
      setResult(res);
      const sum = await api.getSummary(res.run_id);
      setSummary(sum);
      setStatus("completed");
    } catch (err) {
      setError(err.message || "Something went wrong.");
      setStatus("error");
    }
  }

  const running = status === "running";

  return (
    <div className="page">
      <section className="page__intro">
        <h1>Configure a marketplace simulation</h1>
        <p className="muted">
          Multiple firms deploy AI pricing agents that compete for a population
          of consumers. Configure the market below and run the model. You will
          see aggregate results; raw per-step logs are available to the
          researcher only.
        </p>
      </section>

      <form className="grid" onSubmit={onSubmit}>
        <fieldset className="card" disabled={running}>
          <legend>General parameters</legend>

          <div className="field">
            <label htmlFor="num_firms">Number of firms</label>
            <input
              id="num_firms"
              type="number"
              min={2}
              max={10}
              value={form.num_firms}
              onChange={(e) => update("num_firms", e.target.value)}
            />
            <span className="hint">2–10 firms</span>
          </div>

          <div className="field">
            <label htmlFor="num_consumers">Number of consumers</label>
            <input
              id="num_consumers"
              type="number"
              min={10}
              max={100000}
              value={form.num_consumers}
              onChange={(e) => update("num_consumers", e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="num_timesteps">Number of timesteps</label>
            <input
              id="num_timesteps"
              type="number"
              min={1}
              max={500}
              value={form.num_timesteps}
              onChange={(e) => update("num_timesteps", e.target.value)}
            />
            <span className="hint">up to 500</span>
          </div>

          <div className="field">
            <label htmlFor="random_seed">Random seed (optional)</label>
            <input
              id="random_seed"
              type="number"
              min={0}
              placeholder="leave blank for random"
              value={form.random_seed}
              onChange={(e) => update("random_seed", e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="run_description">Run description</label>
            <textarea
              id="run_description"
              rows={3}
              placeholder="e.g. Baseline: 3 profit-maximizers, global info, no regulation."
              value={form.run_description}
              onChange={(e) => update("run_description", e.target.value)}
            />
          </div>
        </fieldset>

        <fieldset className="card" disabled={running}>
          <legend>Agent design</legend>

          <SelectField
            id="agent_type"
            label="Agent type"
            value={form.agent_type}
            options={AGENT_TYPES}
            onChange={(v) => update("agent_type", v)}
          />
          <SelectField
            id="info_visibility"
            label="Information visibility"
            value={form.info_visibility}
            options={INFO_VISIBILITY}
            onChange={(v) => update("info_visibility", v)}
          />
          <SelectField
            id="regulation_mode"
            label="Regulation mode"
            value={form.regulation_mode}
            options={REGULATION_MODES}
            onChange={(v) => update("regulation_mode", v)}
          />
          <SelectField
            id="coordination_mode"
            label="Coordination mode"
            value={form.coordination_mode}
            options={COORDINATION_MODES}
            onChange={(v) => update("coordination_mode", v)}
          />
        </fieldset>

        <fieldset className="card" disabled={running}>
          <legend>Advanced parameters</legend>

          <div className="field">
            <label htmlFor="baseline_cost">Baseline cost</label>
            <input
              id="baseline_cost"
              type="number"
              step="0.1"
              min={0.1}
              value={form.baseline_cost}
              onChange={(e) => update("baseline_cost", e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="demand_alpha">Demand alpha (price sensitivity)</label>
            <input
              id="demand_alpha"
              type="number"
              step="0.1"
              min={0.1}
              value={form.demand_alpha}
              onChange={(e) => update("demand_alpha", e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="collusion_threshold">Collusion threshold</label>
            <input
              id="collusion_threshold"
              type="number"
              step="0.05"
              min={0}
              max={1}
              value={form.collusion_threshold}
              onChange={(e) => update("collusion_threshold", e.target.value)}
            />
            <span className="hint">0–1</span>
          </div>
        </fieldset>

        <div className="run-bar">
          <button type="submit" className="btn btn--primary" disabled={running}>
            {running ? "Running…" : "Run simulation"}
          </button>
          <StatusPill status={status} />
        </div>
      </form>

      {error && <div className="alert alert--error">{error}</div>}

      {result && summary && (
        <ResultPanel result={result} summary={summary} />
      )}
    </div>
  );
}

function SelectField({ id, label, value, options, onChange }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function StatusPill({ status }) {
  return (
    <span className={`pill pill--${status}`}>
      <span className="pill__dot" />
      {STATUS[status]}
    </span>
  );
}

function ResultPanel({ result, summary }) {
  return (
    <section className="result">
      <div className="result__head">
        <div>
          <h2>Run complete</h2>
          <p className="muted">
            Run ID <code>{result.run_id}</code>
          </p>
        </div>
        <div className="stat-row">
          <Stat label="Firms" value={summary.num_firms} />
          <Stat label="Timesteps" value={summary.num_timesteps} />
          <Stat label="Logged rows" value={result.num_rows} />
        </div>
      </div>

      <SummaryCharts summary={summary} />

      <div className="profit-table">
        <h3>Total profit by firm</h3>
        <table>
          <thead>
            <tr>
              <th>Firm</th>
              <th>Total profit</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(summary.total_profit_by_firm).map(([fid, p]) => (
              <tr key={fid}>
                <td>{fid}</td>
                <td>{p.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat__value">{value}</span>
      <span className="stat__label">{label}</span>
    </div>
  );
}
