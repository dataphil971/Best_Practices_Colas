---
name: agent-bi-test-generator
description: Générer les scénarios de test et les fixtures minimales PBIP/TMDL/PBIR à partir d'un algorithme Agent BI BP-XX. À utiliser lors de l'implémentation d'un checker, de l'ajout de tests de non-régression ou de la validation de la couverture OK/KO/NA.
---

# Agent BI Test Generator

## Mission

Générer les tests à partir des algorithmes BP-XX.

L'algorithme est la référence.

## Déroulé

Lire l'algorithme et en extraire :

```text
OK
KO
NA
sources
propriétés
normalisation
agrégation
cas limites
```

Générer les scénarios pertinents pour :

```text
OK nominal
KO nominal
NA nominal
objets multiples
violations multiples
source manquante
propriété manquante
propriété malformée
parsing partiel
conditions limites
```

## Fixtures

Privilégier des fixtures minimales :

```text
Agent_BI/03_PYTHON/tests/
└── fixtures/
    └── bp_xx/
        ├── ok/
        ├── ko/
        ├── na/
        └── edge/
```

Ne pas copier un rapport de production complet quand une fixture réduite suffit.

## Attendus

Chaque scénario doit définir explicitement :

```text
input
expected_status
expected_evidence
```

Exemple :

```json
{
  "scenario": "summarizeBy absent",
  "expected_status": "NA"
}
```

## Tests de non-régression

Chaque bug corrigé doit recevoir un test de non-régression reproduisant l'échec d'origine.

## Règle

Ne jamais changer le résultat attendu simplement parce que l'implémentation Python actuelle se comporte différemment.

Si l'implémentation et l'algorithme divergent, signaler l'incohérence (cf. `agent-bi-rule-review`) plutôt que d'adapter le test à l'implémentation.
