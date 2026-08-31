# BP-13 — Positionner les merges/appends après les réductions de volume pertinentes

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier que les opérations de fusion ou de concaténation Power Query ne sont pas exécutées avant des réductions de volume qui pourraient **être déplacées en amont sans changer le résultat**.

Cette règle ne doit pas confondre :

```text
merge placé tôt
```

avec :

```text
non-conformité prouvée
```

La position numérique d'une étape dans un bloc `let ... in ...` est uniquement un **signal**.

Un `KO` nécessite de démontrer qu'une réduction de lignes ou de colonnes située après le merge/append pourrait être appliquée avant cette opération sans modifier la sémantique de la requête.

Statuts :

```text
OK / KO / NA
```

Les indicateurs de position restent disponibles via :

```text
diagnostic_level
```

et ne deviennent jamais un quatrième statut.

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
```

La règle consomme le `AnalysisContext` partagé :

```text
m_ast
m_step_index
query_dependency_graph
column_lineage
```

Elle ne relit pas le projet complet.

---

## 3. Opérations concernées

```python
MERGE_APPEND_FUNCTIONS = {
    "Table.NestedJoin",
    "Table.Join",
    "Table.FuzzyNestedJoin",
    "Table.Combine",
}
```

Les expansions directement liées à une jointure peuvent être rattachées à la même opération logique.

---

## 4. Réductions candidates

Exemples de réductions qui peuvent parfois être poussées avant une opération lourde :

```text
Table.SelectRows
Table.SelectColumns
Table.RemoveColumns
```

Mais elles ne sont déplaçables que si leur indépendance est démontrée.

Exemple :

```m
Merged = Table.NestedJoin(
    Sales,
    {"CustomerId"},
    Customers,
    {"CustomerId"},
    "Customer",
    JoinKind.LeftOuter
),

Filtered = Table.SelectRows(
    Merged,
    each [OrderDate] >= RangeStart
)
```

Si `OrderDate` provient uniquement de `Sales`, et que le filtre ne dépend d'aucune colonne issue de `Customers`, il peut être candidat à un déplacement avant le merge.

À l'inverse :

```m
Filtered = Table.SelectRows(
    Merged,
    each [Customer.Country] = "FR"
)
```

dépend du résultat du merge.

Le moteur ne doit pas considérer ce filtre comme déplaçable.

---

## 5. Analyse de dépendances

Pour chaque étape située après un merge/append, déterminer :

```text
referenced_columns
source_relations
depends_on_join_output
rewrite_safety
```

Valeurs de `rewrite_safety` :

```text
SAFE
UNSAFE
UNKNOWN
```

Pseudo-code :

```python
def determine_rewrite_safety(
    reducing_step,
    heavy_step,
    lineage,
):
    refs = extract_column_references(
        reducing_step.expression
    )

    resolution = lineage.resolve_before_step(
        refs,
        heavy_step,
    )

    if not resolution.complete:
        return "UNKNOWN"

    if resolution.depends_on_heavy_output:
        return "UNSAFE"

    if reducing_step.is_row_filter():
        if predicate_is_pure_and_side_effect_free(
            reducing_step.expression
        ):
            return "SAFE"
        return "UNKNOWN"

    if reducing_step.is_column_reduction():
        if heavy_step.required_keys_preserved(
            reducing_step
        ):
            return "SAFE"
        return "UNSAFE"

    return "UNKNOWN"
```

---

## 6. Cas des appends

Pour `Table.Combine`, une réduction postérieure n'est distribuable vers les entrées que si l'équivalence peut être démontrée.

Exemple :

```text
Filter(Combine(A, B), P)
```

peut être remplacé par :

```text
Combine(Filter(A, P), Filter(B, P))
```

seulement si :

- `P` est applicable aux deux entrées ;
- les colonnes référencées existent avec une sémantique compatible ;
- aucun traitement intermédiaire ne change leur valeur.

Sans preuve :

```text
UNKNOWN
```

---

## 7. Position relative : diagnostic uniquement

La règle peut calculer :

```python
position_ratio = heavy_index / max(total_steps - 1, 1)
```

et produire par exemple :

```json
{
  "diagnostic_type": "EARLY_MERGE",
  "position_ratio": 0.18
}
```

Mais :

```text
position_ratio < 0.25
```

ne doit jamais produire `KO` à lui seul.

De même :

```text
merge dans la première moitié
```

reste un indicateur, pas une preuve.

---

## 8. Décision par requête

| Situation | Statut |
|---|---|
| aucune fusion / aucun append | `NA` |
| fusion/append présent, aucune réduction postérieure candidate | `OK` |
| réduction postérieure démontrée `SAFE` et pouvant réduire le coût avant la fusion | `KO` |
| réduction postérieure dépend du résultat de la fusion (`UNSAFE`) | `OK` pour ce sous-contrôle |
| réduction postérieure dont le déplacement est indéterminable (`UNKNOWN`) | `NA` |
| code M / dépendances illisibles | `NA` |

Un `OK` signifie uniquement :

> aucune occasion **démontrée** de pousser une réduction existante avant le merge/append.

Il ne signifie pas qu'aucune optimisation imaginable n'existe.

---

## 9. Pseudo-code

```python
def evaluate_query_order(query, context):
    if not query.parse_ok:
        return finding_na(
            object=query.name,
            reason="Code M non interprétable",
        )

    heavy_steps = [
        step
        for step in query.steps
        if step.calls_any(MERGE_APPEND_FUNCTIONS)
    ]

    if not heavy_steps:
        return finding_na(
            object=query.name,
            reason="Aucune fusion/append : règle non applicable",
            reason_code="OUT_OF_SCOPE",
        )

    ko_items = []
    unresolved = []

    for heavy in heavy_steps:
        later_reductions = find_later_reducing_steps(
            query,
            heavy,
        )

        for reduction in later_reductions:
            safety = determine_rewrite_safety(
                reducing_step=reduction,
                heavy_step=heavy,
                lineage=context.column_lineage,
            )

            if safety == "SAFE":
                ko_items.append({
                    "heavy_step": heavy.name,
                    "reducing_step": reduction.name,
                    "reason": (
                        "Réduction démontrée comme déplaçable "
                        "avant la fusion/append"
                    ),
                })

            elif safety == "UNKNOWN":
                unresolved.append({
                    "heavy_step": heavy.name,
                    "reducing_step": reduction.name,
                })

    if ko_items:
        return finding_ko(
            object=query.name,
            evidence={"movable_reductions": ko_items},
        )

    if unresolved:
        return finding_na(
            object=query.name,
            reason="Ordre optimal non démontrable pour certaines étapes",
            evidence={"unresolved": unresolved},
        )

    return finding_ok(
        object=query.name,
        evidence={
            "heavy_steps": [s.name for s in heavy_steps],
            "movable_reductions": [],
        },
    )
```

---

## 10. Statut global

Les requêtes hors périmètre (`aucun merge/append`) ne font pas basculer le statut global.

```python
evaluable = [
    r for r in results
    if r.reason_code != "OUT_OF_SCOPE"
]

if any(r.status == "KO" for r in evaluable):
    rule_status = "KO"

elif any(r.status == "NA" for r in evaluable):
    rule_status = "NA"

elif evaluable:
    rule_status = "OK"

else:
    rule_status = "NA"
```

Priorité :

```text
KO > NA > OK
```

---

## 11. Preuve obligatoire pour KO

```text
query
heavy_step
heavy_function
reducing_step
reducing_function
referenced_columns
lineage_before_heavy_step
rewrite_safety = SAFE
evidence
```

Sans preuve de déplacement sûr :

```text
NA
```

---

## 12. Résumé

```text
RÈGLE BP-13

POUR chaque requête M
    DÉTECTER merges/appends

    SI aucun
        -> NA hors périmètre

    POUR chaque réduction située après
        ANALYSER les dépendances

        SI déplacement sûr démontré
            -> KO

        SI déplacement impossible démontré
            -> aucun problème pour cette étape

        SI indéterminable
            -> NA
    FIN

    SI aucune réduction déplaçable et aucune ambiguïté
        -> OK
FIN
```

La position d'une fusion reste un diagnostic ; elle n'est jamais une preuve suffisante de non-conformité.
