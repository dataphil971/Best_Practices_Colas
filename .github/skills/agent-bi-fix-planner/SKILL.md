---
name: agent-bi-fix-planner
description: Analyser les constats KO confirmés d'Agent BI et proposer un plan de correction sûr, sans jamais modifier silencieusement le projet PBIP. À utiliser pour déterminer si une correction est de type Auto-fix, Assisted fix ou Manual fix.
---

# Agent BI Fix Planner

## Mission

Transformer un constat `KO` démontré en proposition de correction sûre.

L'analyse et la correction restent strictement séparées (cf. `Analyse et correction` du README).

## Préconditions

Une correction nécessite :

```text
rule_id
status = KO
objet
expected
actual
evidence
```

Ne jamais proposer de correction à partir d'un résultat `NA`.

## Classification

Utiliser la classification définie par le README (`Types de correction`) :

```text
AUTO_FIX
ASSISTED_FIX
MANUAL_FIX
NO_FIX
```

### AUTO_FIX

Uniquement quand :

- la correction est déterministe ;
- la valeur cible exacte est connue ;
- l'impact est limité ;
- l'intention sémantique du modèle est préservée.

Exemple : `summarizeBy: sum` → `summarizeBy: none`.

### ASSISTED_FIX

Une correction concrète peut être proposée, mais une validation humaine est requise avant application.

### MANUAL_FIX

À utiliser pour une restructuration architecturale ou sémantique.

Exemples : restructuration de relations, refonte du modèle, suppression de visuel, nommage métier.

### NO_FIX

Aucune correction automatisable n'est identifiable ; seule une recommandation est produite.

## Risque

Renvoyer :

```text
FAIBLE
MOYEN
ELEVE
```

## Sortie attendue

```json
{
  "rule_id": "BP-XX",
  "fix_type": "AUTO_FIX|ASSISTED_FIX|MANUAL_FIX|NO_FIX",
  "risk": "FAIBLE|MOYEN|ELEVE",
  "target": "...",
  "current_value": "...",
  "proposed_value": "...",
  "reason": "...",
  "validation_required": true
}
```

## Vérification

Après toute modification :

```text
reparser
→ réexécuter la BP concernée
→ vérifier le résultat
```

Ne jamais supposer qu'une correction a réussi simplement parce qu'un fichier a changé.
