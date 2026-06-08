import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";
import LoginForm from "../components/LoginForm";

export default function AdminPage() {
  const { configured, loading, user, isAdmin } = useAuth();

  if (!configured) {
    return (
      <div className="page">
        <div className="alert alert--warn">
          Supabase authentication is not configured. Set{" "}
          <code>VITE_SUPABASE_URL</code> and <code>VITE_SUPABASE_ANON_KEY</code>{" "}
          to enable the admin area.
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page">
        <p className="muted">Checking session…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="page page--narrow">
        <h1>Researcher sign in</h1>
        <p className="muted">
          The admin area is restricted to the researcher. Sign in to view runs
          and export raw data.
        </p>
        <LoginForm />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="page page--narrow">
        <div className="alert alert--error">
          <strong>Access denied.</strong> This account does not have admin
          privileges.
        </div>
      </div>
    );
  }

  return <AdminDashboard />;
}

function AdminDashboard() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(null);
  const [downloadingAll, setDownloadingAll] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api.listRuns();
      setRuns(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function onDownload(runId) {
    setDownloading(runId);
    setError("");
    try {
      const blob = await api.downloadCsv(runId);
      saveBlob(blob, `${runId}_logs.csv`);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(null);
    }
  }

  async function onDownloadAll() {
    setDownloadingAll(true);
    setError("");
    try {
      const blob = await api.downloadAllCsv();
      const stamp = new Date().toISOString().slice(0, 10);
      saveBlob(blob, `all_simulation_logs_${stamp}.csv`);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloadingAll(false);
    }
  }

  return (
    <div className="page">
      <div className="page__head">
        <h1>Admin · Simulation runs</h1>
        <div className="head-actions">
          <button className="btn btn--ghost" onClick={load} disabled={loading}>
            Refresh
          </button>
          <button
            className="btn btn--primary"
            onClick={onDownloadAll}
            disabled={downloadingAll || runs.length === 0}
            title="Export every run across all users as a single combined CSV"
          >
            {downloadingAll ? "Preparing…" : "⬇ Download ALL runs (one CSV)"}
          </button>
        </div>
      </div>

      <p className="muted" style={{ marginTop: -12, marginBottom: 20 }}>
        All runs are stored together in one dataset. Use{" "}
        <strong>Download ALL runs</strong> for the complete combined CSV (every
        run, distinguished by the <code>run_id</code> column), or download a
        single run from its row below.
      </p>

      {error && <div className="alert alert--error">{error}</div>}

      {loading ? (
        <p className="muted">Loading runs…</p>
      ) : runs.length === 0 ? (
        <p className="muted">No runs yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Created</th>
                <th>Description</th>
                <th>Firms</th>
                <th>Timesteps</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id}>
                  <td>
                    <code>{r.run_id}</code>
                  </td>
                  <td>{formatDate(r.created_at)}</td>
                  <td className="td-desc" title={r.description}>
                    {r.description || <span className="muted">—</span>}
                  </td>
                  <td>{r.num_firms}</td>
                  <td>{r.num_timesteps}</td>
                  <td>
                    <span className={`tag tag--${r.status}`}>{r.status}</span>
                  </td>
                  <td>
                    <button
                      className="btn btn--small"
                      onClick={() => onDownload(r.run_id)}
                      disabled={downloading === r.run_id}
                    >
                      {downloading === r.run_id ? "Preparing…" : "Download CSV"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
