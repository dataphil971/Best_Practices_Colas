# BP-01 — Respect de la topologie en étoile

## 1. Objectif

Vérifier que le graphe relationnel du modèle respecte une topologie en étoile :

```text
DIMENSION (côté 1)
        ↓
FACT (côté *)
```

La règle ne doit jamais déterminer le rôle d'une table uniquement à partir de son nom :

```text
D_*
F_*
Dim*
Fact*
```

Ces conventions peuvent être conservées comme diagnostic, mais elles ne constituent pas une preuve.

Statuts :

```text
OK / KO / NA
```

---

## 2. Responsabilité de BP-01

BP-01 contrôle :

```text
cohérence globale FACT / DIMENSION dans le graphe
absence de chaîne dimension -> dimension -> fait lorsque la policy impose un star schema strict
absence de table analytique jouant simultanément les rôles "one side" et "many side"
cohérence entre un rôle déclaré et sa position relationnelle
```

BP-01 ne doit pas dupliquer les responsabilités de BP-03 :

```text
bidirectionnel       -> BP-03
many-to-many direct  -> BP-03
```

Une relation non exploitable par BP-01 peut être déléguée à BP-03 sans créer un second `KO` pour la même cause.

---

## 3. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Le checker consomme le contexte partagé :

```text
relationship_graph
table_index
table_role_index
company_policy
semantic_model_coverage
```

Il ne relit pas le projet pour chaque relation.

---

## 4. Cardinalité effective

Le parser TMDL/TOM doit produire pour chaque relation :

```text
ONE_TO_MANY
MANY_TO_ONE
ONE_TO_ONE
MANY_TO_MANY
UNKNOWN
```

Il expose également :

```text
one_end
many_end
```

lorsqu'ils sont déterminables.

Pseudo-code :

```python
def resolve_relationship_shape(
    relationship,
    context,
):
    return context.relationship_graph.resolve_shape(
        relationship.id
    )
```

La règle ne doit pas supposer dans son code métier que :

```text
from = many
to   = one
```

Le resolver central applique les valeurs effectives du modèle et les defaults du contrat TMDL/TOM utilisé.

---

## 5. Rôle structurel d'une table

Pour les relations `ONE_TO_MANY` / `MANY_TO_ONE`, chaque table reçoit un rôle structurel par relation :

```text
ONE_SIDE
MANY_SIDE
```

Puis le moteur agrège les rôles sur tout le graphe.

Valeurs globales :

```text
DIMENSION_ROLE     = toujours côté ONE
FACT_ROLE          = toujours côté MANY
MIXED_ROLE         = au moins une fois ONE et au moins une fois MANY
ISOLATED           = aucune relation analytique
UNKNOWN            = couverture ou cardinalité insuffisante
```

Pseudo-code :

```python
def infer_structural_role(
    table_name,
    relationship_graph,
):
    sides = relationship_graph.sides_for_table(
        table_name,
        regular_only=True,
    )

    if sides.incomplete:
        return "UNKNOWN"

    observed = set(sides.values)

    if not observed:
        return "ISOLATED"

    if observed == {"ONE_SIDE"}:
        return "DIMENSION_ROLE"

    if observed == {"MANY_SIDE"}:
        return "FACT_ROLE"

    if observed == {"ONE_SIDE", "MANY_SIDE"}:
        return "MIXED_ROLE"

    return "UNKNOWN"
```

---

## 6. Pourquoi `MIXED_ROLE` est important

Exemple de snowflake :

```text
Category (1)
    |
    *
Subcategory (1)
    |
    *
Product (1)
    |
    *
Sales
```

`Product` et `Subcategory` jouent à la fois :

```text
ONE_SIDE
MANY_SIDE
```

Ils sont donc :

```text
MIXED_ROLE
```

Dans une policy exigeant un **star schema strict**, ce pattern est non conforme.

Si l'entreprise autorise explicitement certains snowflakes :

```text
MIXED_ROLE autorisé par policy -> OK
```

---

## 7. Rôle déclaré

Le contexte peut contenir un rôle explicitement déclaré :

```text
FACT
DIMENSION
BRIDGE
TECHNICAL
PARAMETER
UNKNOWN
```

Sources possibles :

- policy ;
- métadonnée de gouvernance ;
- annotation projet ;
- classification validée en amont.

Les préfixes de nommage ne créent jamais seuls ce rôle.

---

## 8. Cohérence rôle déclaré / relation

Exemples :

```text
declared DIMENSION + toujours ONE_SIDE -> OK
declared FACT      + toujours MANY_SIDE -> OK

declared FACT      + ONE_SIDE           -> KO
declared DIMENSION + MANY_SIDE          -> KO
```

Une table `BRIDGE` peut être autorisée à se comporter comme une table de fait sans mesures.

---

## 9. Relations non one-to-many

### MANY_TO_MANY

```text
délégué à BP-03
```

BP-01 retourne :

```text
NA / DELEGATED
```

pour cette relation.

### ONE_TO_ONE

Une relation `1:1` n'est pas la forme attendue d'un star schema classique.

Décision :

```text
policy star_strict forbids_one_to_one = true -> KO
sinon -> NA
```

### UNKNOWN

```text
NA
```

---

## 10. Tables techniques / paramètres

Une table n'est hors périmètre que si son rôle est explicitement connu :

```text
TECHNICAL
PARAMETER
```

Le checker ne doit jamais faire :

```python
if table.name.startswith("T_"):
    skip()
```

ou :

```python
if table.name.startswith("P_"):
    skip()
```

---

## 11. Décision par table

| Situation | Statut |
|---|---|
| table analytique `DIMENSION_ROLE` | `OK` |
| table analytique `FACT_ROLE` | `OK` |
| `MIXED_ROLE` et star strict exigé | `KO` |
| `MIXED_ROLE` explicitement autorisé | `OK` |
| rôle structurel inconnu | `NA` |
| rôle déclaré incompatible avec rôle structurel | `KO` |
| table isolée | `NA` |
| table technique/paramètre explicitement hors scope | `NA` |

---

## 12. Pseudo-code

```python
def evaluate_table_topology(
    table,
    context,
):
    declared = context.table_role_index.get(
        table.name,
        "UNKNOWN",
    )

    if declared in {"TECHNICAL", "PARAMETER"}:
        return finding_na(
            object=table.name,
            reason="Table explicitement hors périmètre analytique",
            reason_code="OUT_OF_SCOPE",
        )

    structural = infer_structural_role(
        table.name,
        context.relationship_graph,
    )

    if structural in {"UNKNOWN", "ISOLATED"}:
        return finding_na(
            object=table.name,
            reason=f"Rôle structurel {structural}",
        )

    if declared == "FACT" and structural == "DIMENSION_ROLE":
        return finding_ko(
            object=table.name,
            reason="Table déclarée FACT mais utilisée exclusivement côté ONE",
        )

    if declared == "DIMENSION" and structural == "FACT_ROLE":
        return finding_ko(
            object=table.name,
            reason="Table déclarée DIMENSION mais utilisée côté MANY",
        )

    if structural == "MIXED_ROLE":
        if context.company_policy.bp01_allow_mixed_role(
            table.name
        ):
            return finding_ok(
                object=table.name,
                evidence={
                    "structural_role": structural,
                    "policy_exception": True,
                },
            )

        if context.company_policy.bp01_star_schema_strict:
            return finding_ko(
                object=table.name,
                reason=(
                    "Table utilisée à la fois côté ONE et côté MANY : "
                    "topologie snowflake/chaînée non conforme au star schema strict"
                ),
                evidence=context.relationship_graph.table_side_evidence(
                    table.name
                ),
            )

        return finding_na(
            object=table.name,
            reason="Topologie mixte nécessitant une décision de policy",
        )

    return finding_ok(
        object=table.name,
        evidence={
            "structural_role": structural,
        },
    )
```

---

## 13. Contrôle relationnel complémentaire

Pour chaque relation régulière :

```python
def evaluate_regular_relation(
    relation,
    context,
):
    shape = context.relationship_graph.resolve_shape(
        relation.id
    )

    if shape.kind == "MANY_TO_MANY":
        return finding_na(
            object=relation.id,
            reason="Cardinalité many-to-many évaluée par BP-03",
            reason_code="DELEGATED_BP03",
        )

    if shape.kind == "ONE_TO_ONE":
        if context.company_policy.bp01_forbid_one_to_one:
            return finding_ko(
                object=relation.id,
                reason="Relation 1:1 interdite par la policy star schema",
            )

        return finding_na(
            object=relation.id,
            reason="Relation 1:1 hors pattern star classique",
        )

    if shape.kind == "UNKNOWN":
        return finding_na(
            object=relation.id,
            reason="Cardinalité non résolue",
        )

    return finding_ok(
        object=relation.id,
        evidence={
            "one_end": shape.one_end,
            "many_end": shape.many_end,
        },
    )
```

---

## 14. Aucun lien

Si aucune relation n'existe :

```text
NA
```

et non :

```text
NON_EVALUE
```

Le moteur peut ajouter :

```text
execution_status = SUCCESS
```

avec :

```text
rule_status = NA
```

---

## 15. Statut global

Les éléments `OUT_OF_SCOPE` et `DELEGATED_BP03` ne comptent pas.

```python
evaluable = [
    r for r in results
    if r.reason_code not in {
        "OUT_OF_SCOPE",
        "DELEGATED_BP03",
    }
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

---

## 16. Preuve obligatoire

Pour un `KO` de topologie :

```text
table
declared_role si disponible
structural_role
one_side_relationships
many_side_relationships
policy
source_files
evidence
```

Le nom de la table n'est jamais une preuve.

---

## 17. Résumé

```text
RÈGLE BP-01

CONSTRUIRE le graphe des relations

POUR chaque table analytique
    DÉTERMINER :
        toujours côté ONE
        toujours côté MANY
        les deux
        inconnu

    toujours ONE  -> DIMENSION_ROLE
    toujours MANY -> FACT_ROLE

    MIXED
        SI star strict
            -> KO
        SI exception explicite
            -> OK
        SINON
            -> NA

    rôle déclaré incompatible
        -> KO
FIN

MANY_TO_MANY
    -> déléguer BP-03
```
