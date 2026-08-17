---
name: agent-bi-bpa-mapper
description: Comparer des règles externes de Best Practice Analyzer Power BI (Tabular Editor BPA, etc.) au catalogue de règles BP-XX d'Agent BI. À utiliser pour évaluer un référentiel BPA externe, repérer des contrôles manquants, détecter des recouvrements ou proposer de nouvelles règles candidates.
---

# Agent BI BPA Mapper

## Mission

Comparer des règles Power BI externes (Best Practice Analyzer, Tabular Editor, etc.) au catalogue :

```text
Agent_BI/01_ALGORITHMES/
```

Les règles BPA externes sont un matériau de référence. Elles ne deviennent pas automatiquement des règles Agent BI.

## Classification

Utiliser :

```text
EQUIVALENT
RECOUVREMENT_PARTIEL
NOUVEAU_CANDIDAT
CONFLIT
NON_APPLICABLE
INFORMATION_INSUFFISANTE
```

## Déroulé

### 1. Comprendre la règle externe

Identifier :

```text
ID
intention
périmètre
preuve technique
condition
sévérité
correction proposée
```

### 2. Rechercher dans les règles Agent BI

Comparer sémantiquement, pas seulement par le titre.

### 3. Comparer les conditions

Comparer :

```text
périmètre
propriétés
seuils
exceptions
OK
KO
NA
correction
```

### 4. Protéger la politique d'entreprise

Une recommandation externe ne doit jamais automatiquement l'emporter sur :

```text
les algorithmes Agent BI
la politique d'entreprise (COMPANY_POLICY.md)
les conventions internes
la politique de risque
```

### 5. Nouveaux candidats

Un `NOUVEAU_CANDIDAT` doit passer par `agent-bi-rule-engineer` avant toute implémentation.

## Sortie attendue

```json
{
  "external_rule": "...",
  "internal_rule": "BP-XX|null",
  "classification": "...",
  "common_scope": [],
  "differences": [],
  "recommendation": "..."
}
```

## Règles

Ne jamais :

- importer directement une règle externe en production ;
- remplacer la sémantique `OK`/`KO`/`NA` d'Agent BI ;
- transformer une recommandation externe en politique d'entreprise sans validation ;
- créer une règle BP-XX en double ;
- exécuter automatiquement une correction (`FixExpression`) externe.
