"use strict";

/**
 * Lance le moteur Python (Agent_BI/03_PYTHON/main.py) en sous-processus.
 *
 * Exigence de sécurité (issue de l'analyse d'intégration) : `spawn` reçoit
 * un tableau d'arguments et jamais `{ shell: true }`. Il n'y a donc aucune
 * interpolation de chaîne dans une commande shell, donc aucune injection
 * possible via `projectPath`, quel que soit son contenu.
 */

const path = require("path");
const { spawn } = require("child_process");

const PYTHON_EXECUTABLE = process.env.AGENT_BI_PYTHON || "python";
const MAIN_PY_PATH = path.resolve(__dirname, "..", "..", "03_PYTHON", "main.py");

function runAnalysis(projectPath) {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON_EXECUTABLE, [MAIN_PY_PATH, projectPath], {
      shell: false,
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });

    child.on("error", (err) => {
      reject(new Error(`Impossible de lancer Python (${PYTHON_EXECUTABLE}) : ${err.message}`));
    });

    child.on("close", (exitCode) => {
      if (exitCode !== 0) {
        reject(new Error(`Le moteur Python s'est terminé en erreur (code ${exitCode}) : ${stderr.trim()}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (err) {
        reject(new Error(`Sortie du moteur Python illisible (JSON invalide) : ${err.message}`));
      }
    });
  });
}

module.exports = { runAnalysis, MAIN_PY_PATH, PYTHON_EXECUTABLE };
