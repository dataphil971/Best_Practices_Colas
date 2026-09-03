# BP-03 — Éviter les relations bidirectionnelles et many-to-many

> **Statut d'implémentation : ✅ Implémenté** — moteur : [`03_PYTHON/rules/bp_03.py`](../03_PYTHON/rules/bp_03.py), tests : `03_PYTHON/tests/test_bp_03.py`.

## 1. Objectif

Appliquer la bonne pratique :

> Éviter les relations bidirectionnelles et les relations many-to-many.
> Utiliser des relations one-to-many et une modélisation en étoile.

Cette règle est relationnelle, déterministe et indépendante du nom des tables.

Statuts :

```text
OK / KO / NA
```

---

## 2. Responsabilité

BP-03 contrôle :

```text
cross filtering bidirectionnel
cardinalité many-to-many directe
```

BP-01 contrôle la topologie globale du star schema.

---

## 3. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
```

Contexte :

```text
relationship_graph
relationship_schema_contract
company_policy
semantic_model_coverage
```

---

## 4. Scope

Par défaut, toutes les relations du modèle sont évaluées.

Une relation n'est exclue que par une policy explicite :

```yaml
bp_03:
  excluded_relationships: []
```

Le checker ne doit jamais exclure automatiquement :

```text
P_*
T_*
```

ou tout autre préfixe.

---

## 5. Cardinalité

Le resolver central retourne :

```text
ONE_TO_MANY
MANY_TO_ONE
ONE_TO_ONE
MANY_TO_MANY
UNKNOWN
```

### Direct many-to-many

Si :

```text
MANY_TO_MANY
```

et que la bonne pratique interdit les relations many-to-many directes :

```text
KO
```

Le checker ne doit pas chercher une autre table de bridge pour « justifier » la relation directe.

Une architecture avec bridge conforme se présente au contraire comme :

```text
Dimension A 1 -> * Bridge * <- 1 Dimension B
```

donc chaque relation individuelle reste :

```text
1:*
```

---

## 6. Filtrage croisé

Valeurs normalisées :

```text
ONE_DIRECTION
BOTH_DIRECTIONS
AUTOMATIC
UNKNOWN
```

La résolution est effectuée par le contrat TMDL/TOM applicable.

---

## 7. `BOTH_DIRECTIONS`

Si la policy Colas est stricte :

```yaml
bp_03:
  forbid_bidirectional: true
```

alors :

```text
BOTH_DIRECTIONS -> KO
```

La règle n'essaie pas de décider si le cas d'usage métier « mérite » une exception.

Une exception doit être déclarée explicitement dans la policy :

```yaml
allowed_bidirectional_relationships:
  - RELATIONSHIP_ID
```

---

## 8. `AUTOMATIC`

Le comportement `AUTOMATIC` laisse le moteur choisir.

Si la policy exige de démontrer un filtrage unidirectionnel :

```text
AUTOMATIC -> NA
```

sauf si le contrat/version permet de résoudre sans ambiguïté le comportement effectif.

Le checker ne doit pas transformer automatiquement `AUTOMATIC` en :

```text
ONE_DIRECTION
```

---

## 9. One-to-one

Power BI utilise un filtrage dans les deux sens pour les relations `1:1`.

Si la company policy interdit les relations bidirectionnelles :

```text
ONE_TO_ONE -> KO
```

ou la relation peut également être gérée par une policy spécifique interdisant `1:1`.

Le finding doit expliquer la cause réelle :

```text
1:1 implique un filtrage bidirectionnel
```

---

## 10. Décision

| Cardinalité | Cross filter | Statut |
|---|---|---|
| `1:*` / `*:1` | `ONE_DIRECTION` | `OK` |
| `1:*` / `*:1` | `BOTH_DIRECTIONS` | `KO` |
| `1:*` / `*:1` | `AUTOMATIC` non résolu | `NA` |
| `*:*` | quelconque | `KO` |
| `1:1` avec policy stricte | bidirectionnel | `KO` |
| valeur illisible | — | `NA` |

---

## 11. Pseudo-code

```python
def evaluate_relationship(
    relation,
    context,
):
    if context.company_policy.bp03_is_excluded(
        relation.id
    ):
        return finding_na(
            object=relation.id,
            reason="Relation explicitement exclue par policy",
            reason_code="OUT_OF_SCOPE",
        )

    shape = context.relationship_graph.resolve_shape(
        relation.id
    )

    if shape.kind == "UNKNOWN":
        return finding_na(
            object=relation.id,
            reason="Cardinalité non résolue",
        )

    if shape.kind == "MANY_TO_MANY":
        return finding_ko(
            object=relation.id,
            expected="ONE_TO_MANY / MANY_TO_ONE",
            actual="MANY_TO_MANY",
            evidence=shape.to_evidence(),
        )

    cross = context.relationship_graph.resolve_cross_filter(
        relation.id
    )

    if cross == "UNKNOWN":
        return finding_na(
            object=relation.id,
            reason="crossFilteringBehavior non résolu",
        )

    if shape.kind == "ONE_TO_ONE":
        if context.company_policy.bp03_forbid_bidirectional:
            return finding_ko(
                object=relation.id,
                reason="Relation 1:1 incompatible avec l'interdiction du filtrage bidirectionnel",
                evidence={
                    "shape": shape.kind,
                    "cross_filter": cross,
                },
            )

    if cross == "BOTH_DIRECTIONS":
        if context.company_policy.bp03_bidirectional_allowed(
            relation.id
        ):
            return finding_ok(
                object=relation.id,
                evidence={
                    "policy_exception": True,
                    "cross_filter": cross,
                },
            )

        return finding_ko(
            object=relation.id,
            expected="ONE_DIRECTION",
            actual="BOTH_DIRECTIONS",
        )

    if cross == "AUTOMATIC":
        resolved = context.relationship_graph.resolve_automatic_behavior(
            relation.id
        )

        if resolved == "ONE_DIRECTION":
            return finding_ok(
                object=relation.id,
                evidence={
                    "cross_filter": "AUTOMATIC",
                    "effective": resolved,
                },
            )

        if resolved == "BOTH_DIRECTIONS":
            return finding_ko(
                object=relation.id,
                expected="ONE_DIRECTION",
                actual="BOTH_DIRECTIONS via AUTOMATIC",
            )

        return finding_na(
            object=relation.id,
            reason="Comportement AUTOMATIC non déterminable",
        )

    return finding_ok(
        object=relation.id,
        evidence={
            "shape": shape.kind,
            "cross_filter": cross,
        },
    )
```

---

## 12. Absence de relation

Si aucune relation n'existe :

```text
NA
```

La règle n'a aucun objet à analyser.

---

## 13. Statut global

Les exclusions explicites ne comptent pas.

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

## 14. Preuve obligatoire

### Bidirectionnel

```text
relationship_id
from
to
cardinality
crossFilteringBehavior
effective_behavior si Automatic
policy
source_file
```

### Many-to-many

```text
relationship_id
from
to
fromCardinality
toCardinality
resolved_shape = MANY_TO_MANY
source_file
```

---

## 15. Références techniques

Power BI permet certains scénarios bidirectionnels et many-to-many.

La présente règle reste néanmoins stricte lorsque le référentiel d'entreprise les interdit : l'exception doit alors être portée par une policy versionnée, pas déduite par le checker.

---

## 16. Résumé

```text
RÈGLE BP-03

POUR chaque relation
    RÉSOUDRE la cardinalité

    MANY_TO_MANY
        -> KO

    RÉSOUDRE cross filtering

    BOTH_DIRECTIONS
        SI exception explicite
            -> OK
        SINON
            -> KO

    AUTOMATIC
        SI comportement effectif connu
            évaluer
        SINON
            -> NA

    ONE_DIRECTION + 1:*
        -> OK
FIN
```
