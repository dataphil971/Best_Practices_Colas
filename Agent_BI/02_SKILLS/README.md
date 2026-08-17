# Agent BI Skills

Les skills exécutables (fichiers `SKILL.md`) de la couche agentique d'Agent BI ne sont pas stockés dans ce dossier.

Ils vivent à la racine du dépôt, dans :

```text
.claude/skills/
```

Cet emplacement est reconnu à la fois par Claude Code et par GitHub Copilot (`.github/skills`, `.claude/skills` et `.agents/skills` sont interchangeables pour Copilot), ce qui évite de dupliquer les mêmes skills à deux endroits.

Ce dossier `02_SKILLS/` est conservé uniquement pour documenter la place de la couche agentique dans l'architecture fonctionnelle d'Agent BI (`01_ALGORITHMES → 02_SKILLS → 03_PYTHON → 04_DOCS`), telle que décrite dans `README_Agent_BI.md`.

## Skills actuellement définis

| Skill | Rôle |
|---|---|
| `agent-bi-skill-creator` | Décide si une capacité doit être un skill ou un contrôle Python déterministe |
| `agent-bi-rule-engineer` | Transforme une bonne pratique en algorithme BP-XX (Rule Engineering) |
| `agent-bi-rule-review` | Contrôle la cohérence Algorithme / Python / Tests (Rule Review) |
| `agent-bi-context-review` | Analyse contextuelle non déterministe (Contextual Analysis) |
| `agent-bi-test-generator` | Génère les scénarios de test et fixtures à partir d'un algorithme BP-XX |
| `agent-bi-fix-planner` | Classe une correction en Auto-fix / Assisted fix / Manual fix |
| `agent-bi-bpa-mapper` | Compare des règles BPA externes au catalogue BP-XX |
