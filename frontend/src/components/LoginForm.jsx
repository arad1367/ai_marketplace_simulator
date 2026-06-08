import { useState } from "react";
import { useAuth } from "../context/AuthContext";

/**
 * Sign-in only form. Public account creation is intentionally disabled: the
 * admin area is restricted to the researcher. New researcher accounts (if ever
 * needed) are provisioned directly in Supabase, not through the app.
 */
export default function LoginForm() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { error } = await signIn(email, password);
      if (error) throw error;
    } catch (err) {
      setError(err.message || "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card auth-card" onSubmit={onSubmit}>
      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      {error && <div className="alert alert--error">{error}</div>}

      <button className="btn btn--primary" type="submit" disabled={busy}>
        {busy ? "Please wait…" : "Sign in"}
      </button>

      <p className="muted" style={{ marginTop: 12, fontSize: "0.82rem" }}>
        Restricted area. Accounts are provisioned by the researcher.
      </p>
    </form>
  );
}
