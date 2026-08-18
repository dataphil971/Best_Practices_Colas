import { apiFetch, setAccessToken, refreshSession } from "./client";
import type { UserOut } from "../types";

export function fetchMe(): Promise<UserOut> {
  return apiFetch<UserOut>("/me");
}

export async function loginLocal(email: string, password: string): Promise<UserOut> {
  const { access_token } = await apiFetch<{ access_token: string }>("/auth/login/local", {
    method: "POST",
    body: { email, password },
    skipAuth: true,
  });
  setAccessToken(access_token);
  return fetchMe();
}

export function registerLocal(
  email: string,
  password: string,
  display_name: string,
): Promise<UserOut> {
  return apiFetch<UserOut>("/auth/register", {
    method: "POST",
    body: { email, password, display_name },
    skipAuth: true,
  });
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}

// Tentée au démarrage de l'app : restaure la session depuis le refresh
// token (cookie httpOnly) sans redemander les identifiants, tant que le
// cookie est encore valide.
export async function silentRefresh(): Promise<UserOut | null> {
  const ok = await refreshSession();
  if (!ok) return null;
  try {
    return await fetchMe();
  } catch {
    return null;
  }
}
