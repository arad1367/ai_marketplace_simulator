import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "./context/AuthContext";

export default function App() {
  const { user, isAdmin, signOut, configured } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <Link to="/" className="brand">
            <span className="brand__mark">◆</span>
            <span className="brand__text">AI Marketplace Simulator</span>
          </Link>

          <nav className="nav">
            <NavLink to="/" end className="nav__link">
              Simulate
            </NavLink>
            {isAdmin && (
              <NavLink to="/admin" className="nav__link">
                Admin
              </NavLink>
            )}
            {configured ? (
              user ? (
                <div className="nav__auth">
                  <span className="nav__user" title={user.email}>
                    {user.email}
                    {isAdmin && <span className="badge">admin</span>}
                  </span>
                  <button className="btn btn--ghost" onClick={() => signOut()}>
                    Sign out
                  </button>
                </div>
              ) : (
                <NavLink to="/admin" className="nav__link">
                  Sign in
                </NavLink>
              )
            ) : null}
          </nav>
        </div>
      </header>

      <main className="app-main">
        <Outlet />
      </main>

      <footer className="app-footer">
        <span>
          Agent-based pricing research · Aggregate views are public · Raw data
          is admin-only
        </span>
      </footer>
    </div>
  );
}
