"use strict";

/**
 * Appairage navigateur <-> agent local.
 *
 * Protocole repris de Backend/pbi-agent-overlay-v2.js (déjà écrit côté
 * frontend, jamais branché à un vrai agent) : le code n'est JAMAIS renvoyé
 * dans la réponse HTTP de /pairing/request, seulement affiché côté agent
 * (ici : la console du process Node). C'est ce qui garantit qu'une page
 * web quelconque ne peut pas s'auto-appairer sans qu'un humain lise le
 * code sur la machine qui fait tourner l'agent.
 */

const crypto = require("crypto");

const CODE_TTL_MS = 60 * 1000;

function createPairingStore() {
  const pendingCodes = new Map(); // origin -> { code, expiresAt }
  const tokens = new Set();

  function requestPairing(origin) {
    const code = String(crypto.randomInt(0, 1000000)).padStart(6, "0");
    const expiresAt = Date.now() + CODE_TTL_MS;
    pendingCodes.set(origin, { code, expiresAt });
    return { code, expiresAt };
  }

  function confirmPairing(origin, code) {
    const pending = pendingCodes.get(origin);
    if (!pending) {
      return null;
    }
    if (Date.now() > pending.expiresAt) {
      pendingCodes.delete(origin);
      return null;
    }
    if (pending.code !== code) {
      return null;
    }

    pendingCodes.delete(origin);
    const token = crypto.randomBytes(24).toString("hex");
    tokens.add(token);
    return token;
  }

  function isValidToken(token) {
    return typeof token === "string" && tokens.has(token);
  }

  return { requestPairing, confirmPairing, isValidToken };
}

module.exports = { createPairingStore, CODE_TTL_MS };
