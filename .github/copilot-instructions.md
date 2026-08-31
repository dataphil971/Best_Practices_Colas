# Copilot — Instructions du dépôt

Ce dépôt contient **Agent BI**, un moteur d'analyse automatisée de projets Power BI au format PBIP, documenté dans `Agent_BI/README_Agent_BI.md`. Toujours lire ce fichier avant de proposer une modification structurante.

## Règles non négociables

- Les contrôles de conformité n'ont que **trois statuts possibles : `OK`, `KO`, `NA`**. Jamais de `WARN`, `WARNING`, `PARTIEL`, `INFO`, `NON_EVALUE` ou tout autre statut métier. `NA` signifie « information insuffisante pour conclure » — ce n'est jamais un synonyme de `KO`.
- `execution_status` (`SUCCESS` / `PARTIAL` / `ERROR`) est une dimension **distincte** du statut métier : une règle peut s'exécuter parfaitement et conclure `KO`.
- Une règle qui peut être déterminée par du code doit être déterminée par du code (`Agent_BI/03_PYTHON/`), pas par un skill ou un agent.
- Les identifiants de bonne pratique suivent la convention `BP-NN` (ex. `BP-21`), pas `SM-XXX-001`/`RP-XXX-001` (convention abandonnée, ne pas la réintroduire).
- Chaque algorithme (`Agent_BI/01_ALGORITHMES/*.md`) décrit CE QUI doit être contrôlé, indépendamment de Python. Ne pas coupler l'algorithme à une implémentation Python spécifique.
- Toute correction reste séparée de l'analyse et se classe en `AUTO_FIX` / `ASSISTED_FIX` / `MANUAL_FIX` / `NO_FIX` — jamais de modification silencieuse d'un projet PBIP.
- Une bonne pratique n'est **exécutée** que si elle est déclarée `IMPLEMENTED` dans le catalogue `Agent_BI/03_PYTHON/rules/registry.py`. Une règle `PLANNED` n'apparaît jamais dans un résultat d'analyse — ne pas la faire apparaître avec un statut `NA`, ce qui laisserait croire qu'un contrôle a été tenté.

## Architecture

```text
Agent_BI/
├── 01_ALGORITHMES/   règles fonctionnelles (NN_Nom.md), source de vérité fonctionnelle
│                     README.md = index, statut ✅ implémenté / ⏳ spécifié
├── 02_SKILLS/        place de la couche agentique (les SKILL.md vivent dans .claude/skills/)
├── 03_PYTHON/        moteur déterministe
├── 04_DOCS/          documentation transverse
└── 05_NODE/          pont HTTP local entre le frontend et 03_PYTHON
```

### Moteur Python (`Agent_BI/03_PYTHON`)

Le moteur s'exécute **depuis les sources** (`python main.py <projet_pbip>`), sans packaging :
c'est ce que consomme le pont Node (`05_NODE/services/python-runner.js`). Les modules sont
donc à plat, et `conftest.py` ajoute `03_PYTHON/` au `sys.path` pour les tests.

```text
03_PYTHON/
├── main.py        point d'entrée CLI minimal — un argument, l'enveloppe JSON sur stdout
├── core.py        vocabulaire partagé (RuleStatus, ExecutionStatus, RuleScope)
├── errors.py      exceptions prévisibles (AgentBIError et dérivées)
├── version.py     version exposée dans l'enveloppe JSON (`engine_version`)
├── engine/        contexte partagé, orchestrateur, modèles, enveloppe JSON, api.py,
│                  usage_index.py (index d'usage des colonnes, partagé entre règles)
├── powerbi/       parseurs TMDL / PBIR / PBIR legacy / DAX / M — lecture pure,
│                  aucune décision OK/KO/NA
├── rules/         une règle par fichier (bp_NN.py) + registry.py (catalogue)
├── fixes/         corrections — jamais importées par rules/
└── tests/         tests + fixtures/bp_NN/{ok,ko,na}/
```

Conventions à respecter pour toute contribution Python :

- **Imports absolus depuis la racine du moteur** : `from engine.context import ...`, `from rules import bp_07`. Jamais d'import relatif.
- **Typage moderne** : `list[str]`, `dict[str, Any]`, `str | None` — pas de `typing.List`, `Optional`, `Dict`.
- **Le projet PBIP est lu une seule fois** (`AnalysisContext`) : une règle ne reparcourt jamais le projet pour son propre compte.
- Une règle est une **fonction pure** `check(context) -> RuleResult`, sans effet de bord.
- Toute règle produit un `Finding` par objet analysé, **y compris les `OK`** : un consommateur externe ne doit jamais avoir à redériver une preuve.
- Un constat porte sa preuve localisée : fichier, ligne, extrait, remédiation (cf. `SourceLocation`).

### Contrat JSON

`engine/envelope.py` produit une enveloppe versionnée. `schema_version` suit `MAJEUR.MINEUR` : MAJEUR pour une évolution incompatible, MINEUR pour un ajout de champ. Ne jamais retirer ni renommer un champ existant sans incrémenter le majeur.

## Ajouter une bonne pratique

1. Écrire l'algorithme dans `Agent_BI/01_ALGORITHMES/NN_Nom.md`, bannière de statut comprise.
2. Implémenter `03_PYTHON/rules/bp_NN.py` sur le modèle de `bp_22.py`.
3. Tester dans `03_PYTHON/tests/test_bp_NN.py` avec des fixtures `03_PYTHON/tests/fixtures/bp_NN/{ok,ko,na}/`.
4. Basculer l'entrée du catalogue de `_planned(...)` vers un `RuleSpec` `IMPLEMENTED`.
5. Mettre à jour la bannière de l'algorithme et l'index `01_ALGORITHMES/README.md`.

`03_PYTHON/tests/test_registry.py` échoue si l'une de ces étapes est oubliée.

## Revue de code

Pour toute modification de `Agent_BI/01_ALGORITHMES/**`, voir en complément `.github/instructions/agent-bi-algorithmes.instructions.md`.

Les skills exécutables du projet sont dans `.claude/skills/` (un `SKILL.md` par capacité : création de règle, revue de règle, analyse contextuelle, génération de tests, planification de correction, mapping BPA externe, sourcing de preuve, revue adverse d'un verdict). C'est le seul emplacement lu **à la fois** par Claude Code et par GitHub Copilot.
