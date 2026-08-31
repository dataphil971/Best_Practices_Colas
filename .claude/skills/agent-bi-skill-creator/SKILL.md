---
name: agent-bi-skill-creator
description: Concevoir, réviser et maintenir les skills Agent BI. À utiliser pour décider si une nouvelle capacité Agent BI doit être un contrôle Python déterministe, un workflow hybride, ou un Agent Skill.
---

# Agent BI Skill Creator

## Mission

Concevoir les skills d'Agent BI en préservant son architecture centrale (cf. `README_Agent_BI.md`) :

- un contrôle déterministe appartient à Python (`03_PYTHON/`) ;
- un raisonnement contextuel peut appartenir à un skill ;
- un skill ne remplace jamais un checker BP-XX déterministe ;
- un skill ne modifie jamais silencieusement un projet PBIP.

## Processus de décision

Avant de créer un skill, vérifier qu'il est réellement nécessaire.

Se poser les questions :

1. L'information requise est-elle explicitement disponible dans le PBIP, le TMDL, le PBIR ou le JSON ?
2. La même entrée produit-elle toujours le même résultat ?
3. Les statuts `OK`, `KO` et `NA` peuvent-ils s'exprimer avec des conditions objectives ?

Si OUI aux trois :

```text
DETERMINISTE
→ implémenter en Python (Agent_BI/03_PYTHON/rules/)
→ ne pas créer de skill
```

Sinon, déterminer si la capacité est :

```text
HYBRIDE
CONTEXTUELLE
OUTILLAGE_DEVELOPPEMENT
```

## Classification

### DETERMINISTE

Exemples : validation de `summarizeBy`, cardinalité de relation, relations bidirectionnelles, descriptions manquantes, références d'objet invalides.

Cible : `Agent_BI/03_PYTHON/`

### HYBRIDE

Python détecte des candidats ; un skill n'examine que le contexte non résolu.

### CONTEXTUELLE

À utiliser quand les propriétés techniques seules ne permettent pas de répondre en sécurité.

### OUTILLAGE_DEVELOPPEMENT

Exemples : Rule Engineering, Rule Review, génération de tests, mapping BPA.

## Règles

Ne jamais créer un skill par BP-XX.

Préférer des capacités réutilisables, transverses à plusieurs BP.

Un skill ne doit jamais :

- transformer une incertitude en `KO` ;
- transformer une absence de preuve en `OK` ;
- inventer une propriété PBIP ;
- inventer une politique d'entreprise (`COMPANY_POLICY.md`) ;
- modifier silencieusement un PBIP ;
- écraser une preuve déterministe sans justification.

## Sortie attendue

Pour chaque skill demandé, renvoyer :

```text
Classification
Skill justifié : OUI / NON
Raison
Implémentation recommandée
```

Si la capacité est déterministe :

```text
SKILL_REJETE
Raison : la capacité relève du moteur Python déterministe.
```
