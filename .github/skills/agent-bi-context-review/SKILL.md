---
name: agent-bi-context-review
description: Résoudre les candidats contextuels ou sémantiques produits par les checkers déterministes d'Agent BI, quand la seule preuve technique ne permet pas de trancher en sécurité. À utiliser pour les règles hybrides comme la redondance de visuels, l'organisation ou la clarté sémantique.
---

# Agent BI Context Review

## Mission

Effectuer un raisonnement contextuel uniquement après l'analyse Python déterministe.

Déroulé attendu :

```text
PBIP
 ↓
Parser Python
 ↓
Checker déterministe
 ↓
Candidat
 ↓
Context Review
```

Ne jamais remplacer le parser.

## Préconditions

Ne réviser que les règles classées :

```text
HYBRIDE
CONTEXTUELLE
```

Si Python peut répondre objectivement à la question, s'en remettre à Python.

## Entrées à privilégier

```text
rule_id
type_candidat
objets
contexte_page
références_sémantiques
preuve_technique
contexte_navigation
company_policy
constats_déterministes
```

## Décisions

Utiliser des décisions contextuelles telles que :

```text
JUSTIFIE
NON_CONFORME_CONFIRME
NON_RESOLU
```

Ne pas inventer un mapping `OK`/`KO` différent de celui défini par l'algorithme BP-XX concerné.

## Confiance

Utiliser :

```text
HAUTE
MOYENNE
BASSE
```

La confiance n'est pas une preuve.

## Déroulé

1. Accepter les faits déterministes comme des faits.
2. Identifier la question contextuelle non résolue.
3. Rechercher les preuves contextuelles disponibles.
4. Déterminer si la situation est justifiée.
5. Préserver l'incertitude quand la preuve est insuffisante.

Si insuffisant :

```text
NON_RESOLU
```

## Sortie attendue

```json
{
  "rule_id": "BP-XX",
  "candidate_id": "...",
  "decision": "JUSTIFIE|NON_CONFORME_CONFIRME|NON_RESOLU",
  "confidence": "HAUTE|MOYENNE|BASSE",
  "reason": "...",
  "evidence": []
}
```

## Comportements interdits

Ne jamais :

- déclarer une non-conformité parce qu'une situation paraît simplement inhabituelle ;
- inventer une intention métier ;
- inventer une politique d'entreprise ;
- réécrire le rapport ;
- écraser une preuve technique ;
- traiter un contexte manquant comme une preuve de non-conformité.

## Principe fondamental

```text
candidat != violation
```
