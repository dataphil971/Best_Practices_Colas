import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  confirmPairing,
  detectAgent,
  getAgentToken,
  requestPairing,
  startAnalysis,
  waitForAnalysis,
} from "../api/agent";
import { submitAgentResults } from "../api/reviews";
import type { AgentEnvelope, AgentImportResult } from "../types";

type Phase =
  | "idle"
  | "checking"
  | "not_found"
  | "pairing_code"
  | "ready"
  | "running"
  | "analyzed"
  | "done";

export function AgentConnectPanel({ reviewId }: { reviewId: string }) {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<Phase>(getAgentToken() ? "ready" : "idle");
  const [projectPath, setProjectPath] = useState("");
  const [code, setCode] = useState("");
  const [envelope, setEnvelope] = useState<AgentEnvelope | null>(null);
  const [importResult, setImportResult] = useState<AgentImportResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function onConnect() {
    setErrorMessage(null);
    setPhase("checking");
    const health = await detectAgent();
    if (!health) {
      setPhase("not_found");
      return;
    }
    if (getAgentToken()) {
      setPhase("ready");
      return;
    }
    try {
      await requestPairing();
      setPhase("pairing_code");
    } catch {
      setErrorMessage("Impossible de contacter l'agent pour l'appairage.");
      setPhase("not_found");
    }
  }

  async function onConfirmCode(e: FormEvent) {
    e.preventDefault();
    setErrorMessage(null);
    try {
      await confirmPairing(code);
      setPhase("ready");
    } catch {
      setErrorMessage("Code refusé ou expiré.");
    }
  }

  async function onRunAnalysis() {
    setErrorMessage(null);
    setPhase("running");
    try {
      const started = await startAnalysis(projectPath);
      const finished = await waitForAnalysis(started.analysis_id);
      if (finished.status === "FAILED" || !finished.result) {
        throw new Error(finished.error ?? "L'analyse a échoué.");
      }
      setEnvelope(finished.result);
      setPhase("analyzed");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Échec de l'analyse.");
      setPhase("ready");
    }
  }

  const importMutation = useMutation({
    mutationFn: () => {
      if (!envelope) throw new Error("Aucun résultat à appliquer.");
      return submitAgentResults(reviewId, envelope);
    },
    onSuccess: (result) => {
      setImportResult(result);
      setPhase("done");
      void queryClient.invalidateQueries({ queryKey: ["review", reviewId] });
    },
    onError: () => setErrorMessage("Échec de l'application des résultats."),
  });

  return (
    <section className="agent-panel">
      <h2>Agent BI</h2>

      {phase === "idle" && (
        <button className="btn-primary" onClick={() => void onConnect()}>
          Connecter l'agent local
        </button>
      )}

      {phase === "checking" && <p>Recherche de l'agent sur 127.0.0.1…</p>}

      {phase === "not_found" && (
        <div>
          <p className="error-text">
            Aucun agent local détecté. Démarre-le avec <code>node server.js</code> dans{" "}
            <code>Agent_BI/05_NODE/</code>, puis réessaie.
          </p>
          <button onClick={() => void onConnect()}>Réessayer</button>
        </div>
      )}

      {phase === "pairing_code" && (
        <form onSubmit={(e) => void onConfirmCode(e)} className="pairing-form">
          <p>Un code à 6 chiffres est affiché dans la console de l'agent local.</p>
          <input
            maxLength={6}
            inputMode="numeric"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="••••••"
          />
          <button type="submit">Confirmer l'appairage</button>
        </form>
      )}

      {(phase === "ready" || phase === "running") && (
        <div className="run-form">
          <label>
            Chemin du projet PBIP
            <input
              value={projectPath}
              onChange={(e) => setProjectPath(e.target.value)}
              placeholder="C:\Projects\MonRapport"
              disabled={phase === "running"}
            />
          </label>
          <button
            className="btn-primary"
            onClick={() => void onRunAnalysis()}
            disabled={phase === "running" || !projectPath}
          >
            {phase === "running" ? "Analyse en cours…" : "Lancer l'analyse"}
          </button>
        </div>
      )}

      {phase === "analyzed" && envelope && (
        <div className="agent-results-preview">
          <h3>Résultats {envelope.project.name ? `— ${envelope.project.name}` : ""}</h3>
          <ul>
            {envelope.results.map((r) => (
              <li
                key={r.rule_id}
                className={`rule-status rule-status--${r.rule_status.toLowerCase()}`}
              >
                <strong>{r.rule_id}</strong> — {r.rule_name} : {r.rule_status}
              </li>
            ))}
          </ul>
          <button
            className="btn-primary"
            onClick={() => importMutation.mutate()}
            disabled={importMutation.isPending}
          >
            {importMutation.isPending ? "Application…" : "Appliquer à la revue"}
          </button>
        </div>
      )}

      {phase === "done" && importResult && (
        <div className="agent-import-summary">
          <p>
            {importResult.applied} appliqué(s), {importResult.conflicts} conflit(s) (statut
            humain conservé), {importResult.already_applied} déjà à jour,{" "}
            {importResult.unmatched} non reconnu(s).
          </p>
          <button onClick={() => setPhase("ready")}>Relancer une analyse</button>
        </div>
      )}

      {errorMessage && <p className="error-text">{errorMessage}</p>}
    </section>
  );
}
