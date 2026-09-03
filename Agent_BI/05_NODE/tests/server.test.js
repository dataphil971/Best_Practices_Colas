"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");

const { server, pairing } = require("../server");

const FIXTURE_PROJECT = path.resolve(__dirname, "fixtures", "valid-pbip");

// Le serveur exporté n'écoute pas automatiquement (require.main !== module
// dans server.js) : chaque test démarre sa propre instance sur un port
// éphémère (0), pour ne jamais entrer en conflit avec un agent déjà lancé
// sur le port par défaut (27841) ni entre exécutions parallèles.
function listen() {
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve(`http://127.0.0.1:${port}`);
    });
  });
}

function close() {
  return new Promise((resolve) => server.close(resolve));
}

test("GET /api/v1/health renvoie version, protocole et capacités", async () => {
  const base = await listen();
  try {
    const res = await fetch(`${base}/api/v1/health`);
    const body = await res.json();

    assert.equal(res.status, 200);
    assert.equal(body.protocol, "2");
    assert.ok(Array.isArray(body.capabilities));
  } finally {
    await close();
  }
});

test("POST /api/v1/analyses sans jeton est refusé (401)", async () => {
  const base = await listen();
  try {
    const res = await fetch(`${base}/api/v1/analyses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_path: FIXTURE_PROJECT }),
    });

    assert.equal(res.status, 401);
  } finally {
    await close();
  }
});

test("POST /api/v1/pairing/confirm avec un mauvais code est refusé (401)", async () => {
  const base = await listen();
  try {
    pairing.requestPairing("http://test.local");

    const res = await fetch(`${base}/api/v1/pairing/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: "http://test.local" },
      body: JSON.stringify({ code: "000000" }),
    });

    assert.equal(res.status, 401);
  } finally {
    await close();
  }
});

test("appairage puis analyse de bout en bout sur un vrai projet PBIP", async () => {
  const base = await listen();
  try {
    // Le code n'est jamais renvoyé par /pairing/request (il est affiché
    // côté agent) : on récupère ici la même valeur que verrait un humain
    // en lisant la console, via le store directement.
    const { code } = pairing.requestPairing("http://test.local");

    const confirmRes = await fetch(`${base}/api/v1/pairing/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: "http://test.local" },
      body: JSON.stringify({ code }),
    });
    assert.equal(confirmRes.status, 200);
    const { token } = await confirmRes.json();
    assert.ok(token);

    const startRes = await fetch(`${base}/api/v1/analyses`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body: JSON.stringify({ project_path: FIXTURE_PROJECT }),
    });
    assert.equal(startRes.status, 202);
    const { analysis_id: analysisId, status: initialStatus } = await startRes.json();
    assert.equal(initialStatus, "RUNNING");

    // Python tourne en sous-processus (asynchrone) : on interroge jusqu'à
    // ce qu'il ait terminé, avec un budget de temps raisonnable.
    let job;
    const deadline = Date.now() + 10_000;
    do {
      const pollRes = await fetch(`${base}/api/v1/analyses/${analysisId}`, {
        headers: { "X-Agent-Token": token },
      });
      assert.equal(pollRes.status, 200);
      job = await pollRes.json();
      if (job.status === "RUNNING") {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    } while (job.status === "RUNNING" && Date.now() < deadline);

    assert.equal(job.status, "SUCCEEDED", job.error || "");
    assert.equal(job.result.schema_version, "1.1");
    // Plusieurs règles tournent désormais (cf. rules/registry.py) : on ne
    // suppose pas d'ordre dans `results`, seulement que BP-22 y figure.
    const bp22 = job.result.results.find((r) => r.rule_id === "BP-22");
    assert.ok(bp22, "BP-22 doit figurer dans les résultats");
    assert.equal(bp22.rule_status, "OK");
  } finally {
    await close();
  }
});

test("GET /api/v1/analyses/{id} inconnu renvoie 404", async () => {
  const base = await listen();
  try {
    const { code } = pairing.requestPairing("http://test2.local");
    const confirmRes = await fetch(`${base}/api/v1/pairing/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: "http://test2.local" },
      body: JSON.stringify({ code }),
    });
    const { token } = await confirmRes.json();

    const res = await fetch(`${base}/api/v1/analyses/does-not-exist`, {
      headers: { "X-Agent-Token": token },
    });

    assert.equal(res.status, 404);
  } finally {
    await close();
  }
});
