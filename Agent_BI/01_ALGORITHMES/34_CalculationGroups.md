# BP-34 — Identifier les opportunités de Calculation Groups

## 1. Objectif

Détecter des **familles candidates** de mesures pouvant potentiellement être factorisées avec un Calculation Group, sans affirmer automatiquement qu'un groupe de calcul est la bonne architecture.

Un Calculation Group est un choix de conception.

Une similarité de structure DAX, même forte, ne suffit pas à prouver :

```text
factorisation souhaitable
```

ou :

```text
factorisation possible sans modifier la sémantique
```

Statuts :

```text
OK / KO / NA
```

---

## 2. Architecture hybride

### Python déterministe

Détecte :

```text
STRUCTURAL_FAMILY_CANDIDATE
```

à partir de l'AST DAX.

### Reviewer contextuel

Qualifie chaque famille :

```text
FACTORABLE_CONFIRMED
JUSTIFIED_AS_SEPARATE_MEASURES
UNRESOLVED
```

Le reviewer tient compte :

- du rôle métier ;
- des dépendances ;
- des mesures de base ;
- des dimensions concernées ;
- des Calculation Groups existants ;
- de la compatibilité avec `SELECTEDMEASURE()` ;
- du coût de migration.

---

## 3. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Contexte :

```text
dax_ast
measure_dependency_graph
calculation_group_index
usage_index
context_review_results
company_policy
```

---

## 4. Empreinte structurelle

Le moteur doit utiliser l'AST.

Il peut normaliser :

```text
noms de variables locales
identifiants de colonnes
identifiants de mesures
littéraux
```

tout en conservant :

```text
fonctions
opérateurs
structure
ordre des arguments
```

Pseudo-code :

```python
def structural_fingerprint(
    measure,
    context,
):
    parsed = context.dax_parser.parse(
        measure.expression
    )

    if not parsed.success:
        return None

    canonical = context.dax_ast_normalizer.normalize(
        parsed.ast,
        replace_local_variable_names=True,
        replace_column_identifiers=True,
        replace_measure_identifiers=True,
        replace_literals=True,
    )

    return hash_ast(
        canonical
    )
```

---

## 5. Seuil de détection

Le nombre minimal de mesures dans une famille doit être configurable.

```text
min_family_size
```

Sans seuil configuré :

```text
NA
```

Le checker ne doit pas imposer silencieusement :

```text
4 mesures
```

---

## 6. Similarité de nom

Un patron de nom commun peut renforcer le diagnostic :

```text
pct_*_On_ALL
Color_*
YTD_*
```

mais ne constitue pas une preuve de factorisation.

Il reste :

```text
diagnostic evidence
```

---

## 7. Existing Calculation Groups

La présence d'un `calculationGroup` est détectable statiquement.

En revanche, déterminer qu'il « couvre déjà le patron » peut demander une comparaison sémantique plus riche.

Valeurs :

```text
COVERED_CONFIRMED
NOT_COVERED_CONFIRMED
UNKNOWN
```

Si la couverture n'est pas démontrable :

```text
UNKNOWN
```

---

## 8. Qualification contextuelle

Exemple de candidat :

```json
{
  "candidate_id": "CG-001",
  "members": [
    "pct_Worry_Level_On_ALL",
    "pct_Interest_Level_On_ALL",
    "pct_Training_Level_On_ALL"
  ],
  "structural_fingerprint": "...",
  "dependency_summary": {}
}
```

Le reviewer peut conclure :

### `FACTORABLE_CONFIRMED`

La famille représente réellement une transformation réutilisable compatible avec un Calculation Group.

### `JUSTIFIED_AS_SEPARATE_MEASURES`

La similarité est accidentelle ou la séparation est plus claire / plus sûre.

### `UNRESOLVED`

Les informations ne suffisent pas.

---

## 9. Décision

| Situation | Statut |
|---|---|
| aucune famille candidate, analyse complète | `OK` |
| famille candidate non qualifiée | `NA` |
| toutes les familles sont justifiées séparément | `OK` |
| famille `FACTORABLE_CONFIRMED` + policy exige factorisation | `KO` |
| famille `FACTORABLE_CONFIRMED` sans obligation de policy | `NA` + diagnostic |
| parsing DAX incomplet pouvant masquer des familles | `NA` |

Par défaut, BP-34 est une règle d'opportunité et ne produit pas `KO` uniquement parce qu'une factorisation serait possible.

---

## 10. Politique optionnelle

Exemple :

```yaml
bp_34:
  min_family_size: 5
  require_factorization_when_confirmed: true
```

Dans ce cas :

```text
FACTORABLE_CONFIRMED
+
taille >= seuil
+
require_factorization_when_confirmed
-> KO
```

---

## 11. Pseudo-code

```python
def evaluate_bp34(
    semantic_model,
    context,
):
    threshold = (
        context.company_policy
        .bp34_min_family_size
    )

    if threshold is None:
        return rule_na(
            reason="Seuil de famille BP-34 non configuré"
        )

    groups = {}
    unresolved_measures = []

    for measure in semantic_model.all_measures():
        fp = structural_fingerprint(
            measure,
            context,
        )

        if fp is None:
            unresolved_measures.append(
                measure.qualified_name
            )
            continue

        groups.setdefault(
            fp,
            []
        ).append(measure)

    candidates = [
        build_calc_group_candidate(
            members
        )
        for members in groups.values()
        if len(members) >= threshold
    ]

    if not candidates:
        if unresolved_measures:
            return rule_na(
                reason="Analyse DAX partielle",
                evidence={
                    "unresolved": unresolved_measures,
                },
            )

        return rule_ok(
            evidence={
                "candidate_count": 0,
            },
        )

    decisions = []

    for candidate in candidates:
        review = context.calc_group_reviews.get(
            candidate.id
        )

        if review is None:
            decisions.append("UNRESOLVED")
            continue

        decisions.append(
            review.decision
        )

    if (
        "FACTORABLE_CONFIRMED" in decisions
        and context.company_policy
        .bp34_require_factorization_when_confirmed
    ):
        return rule_ko(
            evidence={
                "candidates": candidates,
                "decisions": decisions,
            },
        )

    if (
        "UNRESOLVED" in decisions
        or "FACTORABLE_CONFIRMED" in decisions
        or unresolved_measures
    ):
        return rule_na(
            evidence={
                "candidates": candidates,
                "decisions": decisions,
                "unresolved": unresolved_measures,
            },
            diagnostic_level=(
                "INFO"
                if "FACTORABLE_CONFIRMED" in decisions
                else None
            ),
        )

    return rule_ok(
        evidence={
            "candidates": candidates,
            "decisions": decisions,
        },
    )
```

---

## 12. Preuve obligatoire pour KO

```text
candidate_id
members
structural_fingerprint
review = FACTORABLE_CONFIRMED
review_evidence
policy_id
policy_version
require_factorization_when_confirmed = true
evidence
```

---

## 13. Résumé

```text
RÈGLE BP-34

DÉTECTER les familles structurelles

SI analyse complète ET aucune famille
    -> OK

POUR chaque famille candidate
    QUALIFIER :
        FACTORABLE_CONFIRMED
        JUSTIFIED_AS_SEPARATE_MEASURES
        UNRESOLVED

SI factorisation confirmée
   ET policy l'impose
    -> KO

SI candidat non résolu
   OU factorisation recommandée mais non obligatoire
    -> NA + diagnostic

SINON
    -> OK
```
