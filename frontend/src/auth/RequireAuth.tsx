import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function RequireAuth() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <p className="page-loading">Chargement…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
