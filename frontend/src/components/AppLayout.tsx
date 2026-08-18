import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function AppLayout() {
  const { user, logout } = useAuth();
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/reviews" className="app-title">
          PR Review
        </Link>
        <div className="app-user">
          <span>{user?.display_name}</span>
          <button onClick={() => void logout()}>Déconnexion</button>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
