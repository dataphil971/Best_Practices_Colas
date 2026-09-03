---
name: agent-bi-rule-review
description: Vérifier la cohérence d'une implémentation BP-XX entre son algorithme fonctionnel, son checker Python et ses tests. À utiliser pour une revue de code, une pull request, la validation d'un checker ou une analyse de régression.
---

# Agent BI Rule Review

## Mission

Valider la cohérence entre :

```text
01_ALGORITHMES
      ↓
03_PYTHON/rules
      ↓
03_PYTHON/test
```

L'algorithme BP-XX est la référence fonctionnelle.

## Déroulé

### 1. Extraire le contrat de l'algorithme

Identifier :

```text
rule_id
périmètre
sources
propriétés
conditions OK
conditions KO
conditions NA
normalisation
agrégation
preuve
cas limites
```

### 2. Inspecter le code Python

Vérifier que l'implémentation :

- lit la bonne source ;
- lit la bonne propriété ;
- parcourt tous les objets requis (pas d'arrêt à la première anomalie) ;
- applique la normalisation exigée ;
- respecte `OK`/`KO`/`NA` ;
- conserve la preuve requise.

### 3. Comparer les décisions

Exemple :

```text
Algorithme :
propriété absente → NA

Python :
propriété absente → KO
```

Renvoyer :

```text
INCOHERENCE_CRITIQUE
```

### 4. Détecter un parcours incomplet

Vérifier que Python ne :

- s'arrête pas après la première violation ;
- n'ignore pas les tables sans spécification particulière ;
- n'avale pas les erreurs de parsing silencieusement ;
- ne convertit pas une structure inconnue en `OK`.

### 5. Réviser les tests

Attendus quand pertinent :

```text
OK
KO
NA
violations multiples
source manquante
source non supportée
cas limites documentés dans l'algorithme
```

### 6. Détecter une dérive de périmètre

Si Python implémente une condition absente de l'algorithme :

```text
COMPORTEMENT_NON_SPECIFIE
```

## Sévérité

Utiliser :

```text
CRITIQUE
MAJEUR
MINEUR
INFO
```

`CRITIQUE` signifie que le défaut peut changer une décision `OK`/`KO`/`NA`.

## Sortie attendue

```text
Règle : BP-XX

Verdict :
PASS | FAIL | PARTIEL

Constats :
- sévérité
- emplacement
- attendu par l'algorithme
- comportement de l'implémentation
- impact
- correction requise

Couverture :
OK
KO
NA
Cas limites
```

## Règle d'or

Un checker qui contredit son algorithme BP-XX est incorrect, même s'il « fonctionne ».
