"use strict";

/**
 * Serveur pont Agent BI : reçoit les requêtes du frontend et lance le
 * moteur Python en local. Protocole compatible avec
 * Backend/pbi-agent-overlay-v2.js (port 27841, préfixe /api/v1, headers
 * X-Agent-Protocol / X-Agent-Token) sans réimplémenter les parties de cet
 * overlay hors périmètre (connexion TOM live, sélecteur de fichier natif).
 *
 * N'écoute que sur 127.0.0.1 : ce serveur ne doit jamais être exposé sur
 * le réseau, il exécute du code Python arbitraire sur la machine locale.
 */

const http = require("http");
const fs = require("fs");
const { URL } = require("url");

const { createPairingStore } = require("./services/pairing");
const { createAnalysisStore } = require("./services/analyses");

const HOST = "127.0.0.1";
const PORT = Number(process.env.AGENT_BI_NODE_PORT) || 27841;
const PROTOCOL_VERSION = "2";
const AGENT_VERSION = "0.1.0";

const pairing = createPairingStore();
const analyses = createAnalysisStore();

function sendJson(res, statusCode, body) {
  const payload = JSON.stringify(body);
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
    });
    req.on("end", () => {
      if (!raw) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

function applyCors(req, res) {
  const origin = req.headers.origin;
  if (origin) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Vary", "Origin");
  }
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader(
    "Access-Control-Allow-Headers",
    "Content-Type, X-Agent-Protocol, X-Agent-Token, Idempotency-Key",
  );
  // Le CORS permet seulement au navigateur d'appeler l'agent : la vraie
  // barrière de sécurité reste le jeton d'appairage (X-Agent-Token),
  // vérifié explicitement par requireToken() sur les routes /analyses.
}

function requireToken(req, res) {
  const token = req.headers["x-agent-token"];
  if (!pairing.isValidToken(token)) {
    sendJson(res, 401, {
      error: "unauthorized",
      message: "Jeton d'appairage manquant ou invalide.",
    });
    return false;
  }
  return true;
}

function isPlausibleProjectPath(value) {
  return typeof value === "string" && value.trim().length > 0 && !value.includes("\0");
}

async function handleRequest(req, res) {
  applyCors(req, res);

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === "GET" && url.pathname === "/api/v1/health") {
    sendJson(res, 200, {
      version: AGENT_VERSION,
      protocol: PROTOCOL_VERSION,
      capabilities: ["pairing", "analyses"],
    });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/v1/pairing/request") {
    const body = await readJsonBody(req).catch(() => ({}));
    const origin = req.headers.origin || body.origin || "unknown";
    const { code, expiresAt } = pairing.requestPairing(origin);
    console.log(`\n=== Code d'appairage Agent BI : ${code} ===`);
    console.log(
      `Origine : ${origin} — expire dans ${Math.round((expiresAt - Date.now()) / 1000)}s\n`,
    );
    sendJson(res, 200, {});
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/v1/pairing/confirm") {
    const body = await readJsonBody(req).catch(() => ({}));
    const origin = req.headers.origin || body.origin || "unknown";
    const token = pairing.confirmPairing(origin, String(body.code || ""));
    if (!token) {
      sendJson(res, 401, { error: "invalid_code", message: "Code refusé ou expiré." });
      return;
    }
    sendJson(res, 200, { token });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/v1/analyses") {
    if (!requireToken(req, res)) return;
    const body = await readJsonBody(req).catch(() => ({}));
    if (!isPlausibleProjectPath(body.project_path)) {
      sendJson(res, 400, {
        error: "invalid_project_path",
        message: "project_path est requis.",
      });
      return;
    }
    if (!fs.existsSync(body.project_path) || !fs.statSync(body.project_path).isDirectory()) {
      sendJson(res, 400, {
        error: "invalid_project_path",
        message: "project_path doit être un dossier existant.",
      });
      return;
    }
    const job = analyses.startAnalysis(body.project_path);
    sendJson(res, 202, { analysis_id: job.id, status: job.status });
    return;
  }

  const analysisMatch = url.pathname.match(/^\/api\/v1\/analyses\/([^/]+)$/);
  if (req.method === "GET" && analysisMatch) {
    if (!requireToken(req, res)) return;
    const job = analyses.getAnalysis(analysisMatch[1]);
    if (!job) {
      sendJson(res, 404, { error: "not_found", message: "Analyse inconnue." });
      return;
    }
    sendJson(res, 200, {
      analysis_id: job.id,
      status: job.status,
      result: job.result,
      error: job.error,
    });
    return;
  }

  sendJson(res, 404, { error: "not_found", message: "Route inconnue." });
}

const server = http.createServer((req, res) => {
  handleRequest(req, res).catch((err) => {
    sendJson(res, 500, { error: "internal_error", message: err.message });
  });
});

if (require.main === module) {
  server.listen(PORT, HOST, () => {
    console.log(`Agent BI (pont Node) à l'écoute sur http://${HOST}:${PORT}`);
  });
}

module.exports = { server, pairing, analyses, HOST, PORT };
