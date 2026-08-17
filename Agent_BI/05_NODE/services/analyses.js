"use strict";

/**
 * Registre en mémoire des analyses lancées.
 *
 * `POST /analyses` répond immédiatement (202) avec un identifiant ; le
 * résultat n'est disponible qu'ensuite via `GET /analyses/{id}` — le moteur
 * Python peut prendre plusieurs secondes sur un gros modèle, on ne bloque
 * jamais la requête HTTP en attendant.
 */

const crypto = require("crypto");
const { runAnalysis } = require("./python-runner");

function createAnalysisStore() {
  const jobs = new Map(); // id -> { id, status, createdAt, result, error }

  function startAnalysis(projectPath) {
    const id = crypto.randomUUID();
    const job = {
      id,
      status: "RUNNING", // RUNNING | SUCCEEDED | FAILED
      createdAt: Date.now(),
      result: null,
      error: null,
    };
    jobs.set(id, job);

    runAnalysis(projectPath)
      .then((envelope) => {
        job.status = "SUCCEEDED";
        job.result = envelope;
      })
      .catch((err) => {
        job.status = "FAILED";
        job.error = err.message;
      });

    return job;
  }

  function getAnalysis(id) {
    return jobs.get(id) || null;
  }

  return { startAnalysis, getAnalysis };
}

module.exports = { createAnalysisStore };
