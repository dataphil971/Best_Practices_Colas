// Client de l'agent local (Agent_BI/05_NODE/server.js), sur 127.0.0.1.
// Protocole distinct du backend FastAPI : pas de Bearer/cookie, un jeton
// d'appairage (X-Agent-Token) obtenu via un code affiché côté agent — cf.
// Agent_BI/README_Agent_BI.md, section 05_NODE, et
// Backend/pbi-agent-overlay-v2.js (même protocole, jamais branché avant ce
// frontend).

import type { AgentEnvelope } from "../types";

const DEFAULT_AGENT_ENDPOINT = "http://127.0.0.1:27841";
const ENDPOINT_STORAGE_KEY = "agentbi.endpoint";
// sessionStorage (pas localStorage) : le jeton d'appairage ne doit pas
// survivre au-delà de l'onglet, comme dans l'overlay legacy.
const TOKEN_STORAGE_KEY = "agentbi.token";

export function getAgentEndpoint(): string {
  return localStorage.getItem(ENDPOINT_STORAGE_KEY) ?? DEFAULT_AGENT_ENDPOINT;
}

export function setAgentEndpoint(endpoint: string): void {
  localStorage.setItem(ENDPOINT_STORAGE_KEY, endpoint);
}

export function getAgentToken(): string | null {
  return sessionStorage.getItem(TOKEN_STORAGE_KEY);
}

function setAgentToken(token: string): void {
  sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
}

async function agentFetch(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Agent-Protocol": "2",
  };
  if (options.auth) {
    const token = getAgentToken();
    if (token) headers["X-Agent-Token"] = token;
  }
  return fetch(`${getAgentEndpoint()}/api/v1${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
}

export interface AgentHealth {
  version: string;
  protocol: string;
  capabilities: string[];
}

export async function detectAgent(timeoutMs = 2500): Promise<AgentHealth | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${getAgentEndpoint()}/api/v1/health`, { signal: ctrl.signal });
    if (!res.ok) return null;
    return (await res.json()) as AgentHealth;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function requestPairing(): Promise<void> {
  const res = await agentFetch("/pairing/request", {
    method: "POST",
    body: { origin: window.location.origin },
  });
  if (!res.ok) throw new Error("Échec de la demande d'appairage.");
}

export async function confirmPairing(code: string): Promise<string> {
  const res = await agentFetch("/pairing/confirm", { method: "POST", body: { code } });
  if (!res.ok) throw new Error("Code refusé ou expiré.");
  const data = (await res.json()) as { token: string };
  setAgentToken(data.token);
  return data.token;
}

export interface AnalysisStartResult {
  analysis_id: string;
  status: "RUNNING" | "SUCCEEDED" | "FAILED";
}

export async function startAnalysis(projectPath: string): Promise<AnalysisStartResult> {
  const res = await agentFetch("/analyses", {
    method: "POST",
    body: { project_path: projectPath },
    auth: true,
  });
  if (res.status === 401) throw new Error("Non appairé : reconnecte l'agent.");
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { message?: string };
    throw new Error(data.message ?? "Impossible de démarrer l'analyse.");
  }
  return res.json();
}

export interface AnalysisPollResult {
  analysis_id: string;
  status: "RUNNING" | "SUCCEEDED" | "FAILED";
  result: AgentEnvelope | null;
  error: string | null;
}

export async function pollAnalysis(id: string): Promise<AnalysisPollResult> {
  const res = await agentFetch(`/analyses/${id}`, { auth: true });
  if (!res.ok) throw new Error("Analyse introuvable.");
  return res.json();
}

export async function waitForAnalysis(
  id: string,
  { intervalMs = 500, timeoutMs = 60_000 }: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<AnalysisPollResult> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const poll = await pollAnalysis(id);
    if (poll.status !== "RUNNING") return poll;
    if (Date.now() > deadline) throw new Error("Délai d'analyse dépassé.");
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
