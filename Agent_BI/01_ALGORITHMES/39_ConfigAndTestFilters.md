# BP-39 — Configurer et tester les filtres du rapport

> **Statut d'implémentation : ✅ Implémenté** — moteur : [`03_PYTHON/rules/bp_39.py`](../03_PYTHON/rules/bp_39.py), tests : `03_PYTHON/tests/test_bp_39.py`.

## 1. Objectif

Vérifier que les filtres déclarés dans le rapport :

1. référencent des objets existants dans le modèle sémantique ;
2. ne contiennent pas de contradiction **démontrable** entre niveaux.

La règle doit éviter de conclure à une contradiction lorsque la sémantique complète du filtre n'est pas interprétable.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<REPORT_PATH>/definition/report.json
<REPORT_PATH>/definition/pages/**/page.json
<REPORT_PATH>/definition/pages/**/visual.json
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Le moteur consomme :

```text
model_object_index
filter_index
filter_parser
report_coverage
semantic_model_coverage
```

---

## 3. Validation des références

Chaque filtre peut référencer :

```text
Column
Measure
```

Le moteur doit résoudre le couple technique :

```text
(Entity, Property, Kind)
```

Si l'objet est absent d'un modèle dont la couverture est complète :

```text
KO
```

Si la couverture du modèle est incomplète :

```text
NA
```

---

## 4. Champ non résolvable

Un filtre dont le champ utilise une construction PBIR non supportée par le parser ne doit pas être considéré cassé.

```text
UNKNOWN_FIELD_REFERENCE -> NA
```

---

## 5. Normalisation des conditions

Les conditions doivent être converties vers une représentation logique structurée.

Exemples :

```text
IN
NOT IN
=, <>, <, <=, >, >=
BETWEEN
AND
OR
```

Représentation possible :

```python
FilterConstraint(
    field=...,
    allowed_values=...,
    excluded_values=...,
    lower_bound=...,
    upper_bound=...,
    expression_tree=...,
    completeness=...
)
```

---

## 6. Contradiction prouvée

Un `KO` n'est produit que si l'intersection des contraintes est **mathématiquement vide** avec une représentation complète.

Exemple :

```text
rapport : Year IN {2024}
visuel  : Year NOT IN {2024}
```

Intersection :

```text
∅
```

Donc :

```text
KO
```

Autre exemple :

```text
page   : Year IN {2024, 2025}
visuel : Year IN {2024}
```

Intersection :

```text
{2024}
```

Donc aucune contradiction.

---

## 7. Conditions non totalement interprétables

Exemples :

```text
Top N
relative date
measure filter
expression dynamique
condition PBIR inconnue
```

Si le parser ne peut pas prouver la satisfiabilité ou l'insatisfiabilité :

```text
NA
```

Le moteur ne doit pas approximer ces filtres en ensembles statiques.

---

## 8. Typage des littéraux

Les valeurs doivent être normalisées en respectant le type du champ :

```text
string
int64
decimal
date
dateTime
boolean
```

Le littéral PBIR :

```text
"0L"
```

doit être interprété selon son contrat, pas comme la chaîne `"0L"`.

Si le type ne peut pas être résolu :

```text
NA
```

---

## 9. Pile de filtres applicable

Pour chaque visuel :

```text
report filters
+
page filters
+
visual filters
```

Le moteur regroupe les contraintes par champ **uniquement lorsque l'identité du champ est résolue de façon fiable**.

---

## 10. Décision par filtre

| Situation | Statut |
|---|---|
| champ résolu et existant | `OK` pour la référence |
| champ absent dans modèle complet | `KO` |
| champ non résolu | `NA` |
| condition absente/illisible | `NA` |

---

## 11. Décision de contradiction

| Situation | Statut |
|---|---|
| intersection vide démontrée | `KO` |
| intersection non vide démontrée | `OK` pour ce sous-contrôle |
| logique partiellement interprétable | `NA` |

---

## 12. Pseudo-code

```python
def validate_filter_reference(
    filter_obj,
    context,
):
    ref = context.filter_parser.resolve_field(
        filter_obj
    )

    if ref is None:
        return finding_na(
            object=filter_obj.id,
            reason="Champ filtré non résolvable",
        )

    target = context.model_object_index.resolve(
        ref.entity,
        ref.property,
        ref.kind,
    )

    if target is not None:
        return finding_ok(
            object=filter_obj.id,
            evidence={
                "field": ref.to_dict(),
            },
        )

    if context.semantic_model_coverage_complete:
        return finding_ko(
            object=filter_obj.id,
            reason="Filtre référence un objet absent du modèle",
            evidence={
                "field": ref.to_dict(),
            },
        )

    return finding_na(
        object=filter_obj.id,
        reason="Objet non trouvé avec couverture modèle incomplète",
    )
```

```python
def evaluate_filter_stack(
    filters,
    context,
):
    constraints = []

    for filter_obj in filters:
        parsed = context.filter_parser.parse_constraint(
            filter_obj
        )

        if not parsed.complete:
            return finding_na(
                object="filter_stack",
                reason="Au moins une contrainte n'est pas interprétable intégralement",
                evidence={
                    "unresolved_filter": filter_obj.id,
                },
            )

        constraints.append(parsed)

    result = solve_constraints(
        constraints
    )

    if result == "UNSAT":
        return finding_ko(
            object="filter_stack",
            reason="Filtres mutuellement exclusifs",
            evidence={
                "constraints": [
                    c.to_evidence()
                    for c in constraints
                ],
            },
        )

    if result == "SAT":
        return finding_ok(
            object="filter_stack",
        )

    return finding_na(
        object="filter_stack",
        reason="Satisfiabilité non déterminable",
    )
```

---

## 13. Aucun filtre

Si aucun filtre explicite n'est présent :

```text
NA
```

La règle n'a rien à tester.

---

## 14. Statut global

```python
if any(r.status == "KO" for r in results):
    rule_status = "KO"

elif any(r.status == "NA" for r in results):
    rule_status = "NA"

elif results:
    rule_status = "OK"

else:
    rule_status = "NA"
```

Priorité :

```text
KO > NA > OK
```

---

## 15. Preuve obligatoire

### Champ invalide

```text
filter_id
level
page
visual
field_kind
entity
property
model_coverage_complete
source_file
```

### Contradiction

```text
visual
field
constraints
normalized_literals
solver_result = UNSAT
evidence
```

---

## 16. Résumé

```text
RÈGLE BP-39

INVENTORIER les filtres

POUR chaque filtre
    RÉSOUDRE le champ

    SI objet absent et modèle complet
        -> KO

    SI non résolvable
        -> NA
FIN

POUR chaque visuel
    CONSTRUIRE sa pile de filtres

    SI toutes les contraintes sont interprétables
        RÉSOUDRE l'intersection

        intersection vide
            -> KO

        intersection non vide
            -> OK
    SINON
        -> NA
FIN

AUCUN filtre
    -> NA
```
