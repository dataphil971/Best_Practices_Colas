# Copilot — Instructions du dépôt

Ce dépôt contient **Agent BI**, un moteur d'analyse automatisée de projets Power BI au format PBIP, documenté dans `Agent_BI/README_Agent_BI.md`. Toujours lire ce fichier avant de proposer une modification structurante.

## Règles non négociables

- Les contrôles de conformité n'ont que **trois statuts possibles : `OK`, `KO`, `NA`**. Jamais de `WARN`, `WARNING`, `PARTIEL`, `INFO`, `NON_EVALUE` ou tout autre statut métier. `NA` signifie « information insuffisante pour conclure » — ce n'est jamais un synonyme de `KO`.
- Une règle qui peut être déterminée par du code doit être déterminée par du code (`Agent_BI/03_PYTHON/`), pas par un skill ou un agent.
- Les identifiants de bonne pratique suivent la convention `BP-NN` (ex. `BP-21`), pas `SM-XXX-001`/`RP-XXX-001` (convention abandonnée, ne pas la réintroduire).
- Chaque algorithme (`Agent_BI/01_ALGORITHMES/*.md`) décrit CE QUI doit être contrôlé, indépendamment de Python. Ne pas coupler l'algorithme à une implémentation Python spécifique.
- Toute correction reste séparée de l'analyse et se classe en `AUTO_FIX` / `ASSISTED_FIX` / `MANUAL_FIX` / `NO_FIX` — jamais de modification silencieuse d'un projet PBIP.

## Architecture

```text
Agent_BI/
├── 01_ALGORITHMES/   règles fonctionnelles (BP-NN.md), source de vérité
├── 03_PYTHON/        moteur déterministe (rules/, tests/) — actuellement vide, en construction
└── 04_DOCS/          documentation transverse
```

Les skills exécutables du projet sont dans `.github/skills/` (un `SKILL.md` par capacité : création de règle, revue de règle, analyse contextuelle, génération de tests, planification de correction, mapping BPA externe).

## Revue de code

Pour toute modification de `Agent_BI/01_ALGORITHMES/**`, voir en complément `.github/instructions/agent-bi-algorithmes.instructions.md`.
