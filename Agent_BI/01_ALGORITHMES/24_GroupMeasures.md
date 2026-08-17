# BP-24 — Centraliser les mesures dans une ou plusieurs tables dédiées

## 1. Objectif

Vérifier que les mesures du modèle sont hébergées dans une ou plusieurs **tables dédiées aux mesures**, conformément à la bonne pratique du référentiel.

Cette règle est déterministe à condition de distinguer correctement :

```text
table de mesures
```

et :

```text
table de données contenant des mesures
```

Le nom de la table (`MEASURE`, `_Measures`, `KPI`...) ne doit jamais être utilisé comme preuve suffisante.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
```

Le `AnalysisContext` doit fournir :

```text
tables
columns
measures
partitions
relationships
usage_index
```

---

## 3. Définition d'une table dédiée aux mesures

Une table est `MEASURE_TABLE_CONFIRMED` si :

1. elle contient au moins une mesure ;
2. elle ne contient aucune colonne métier / donnée réelle ;
3. toute colonne éventuellement présente est démontrée comme **colonne technique de support**.

Une table peut donc contenir une colonne cachée servant uniquement à matérialiser une table calculée de support.

---

## 4. Colonne technique de support

Une colonne ne doit être exemptée que si son caractère technique est démontré.

Exemples de preuves convergentes :

```text
table calculée
colonne masquée
aucun usage direct dans le rapport
aucune relation
aucun usage métier dans DAX
colonne générée par une expression de support de la table
```

Pseudo-code :

```python
def classify_measure_support_column(
    table,
    column,
    context,
):
    if not column.is_hidden:
        return "DATA_COLUMN"

    usages = context.usage_index.get_column_usages(
        table.name,
        column.name,
    )

    if usages.has_semantic_or_report_usage:
        return "DATA_COLUMN"

    if context.relationship_graph.uses_column(
        table.name,
        column.name,
    ):
        return "DATA_COLUMN"

    if (
        table.is_calculated
        and column.is_generated_from_table_support_expression
    ):
        return "SUPPORT_COLUMN"

    return "UNKNOWN"
```

### Important

Les critères suivants ne suffisent pas seuls :

```text
nom = Column
isHidden
isNameInferred
```

Une colonne masquée réelle ne doit jamais être exemptée uniquement sur ces signaux.

---

## 5. Classification d'une table

Valeurs :

```text
MEASURE_TABLE_CONFIRMED
DATA_TABLE
UNKNOWN
EMPTY_OR_OUT_OF_SCOPE
```

Pseudo-code :

```python
def classify_table_for_measure_rule(
    table,
    context,
):
    measure_count = len(table.measures)

    if measure_count == 0:
        return "DATA_TABLE"

    support_states = [
        classify_measure_support_column(
            table,
            column,
            context,
        )
        for column in table.columns
    ]

    if any(state == "DATA_COLUMN" for state in support_states):
        return "DATA_TABLE"

    if any(state == "UNKNOWN" for state in support_states):
        return "UNKNOWN"

    return "MEASURE_TABLE_CONFIRMED"
```

---

## 6. Décision par mesure

Pour chaque mesure :

```text
mesure dans MEASURE_TABLE_CONFIRMED -> OK
mesure dans DATA_TABLE              -> KO
mesure dans UNKNOWN                 -> NA
```

Si le modèle ne contient aucune mesure :

```text
NA
```

---

## 7. Pseudo-code

```python
def evaluate_bp24(
    semantic_model,
    context,
):
    measures = semantic_model.all_measures()

    if not measures:
        return rule_na(
            reason="Aucune mesure dans le modèle"
        )

    table_roles = {
        table.name: classify_table_for_measure_rule(
            table,
            context,
        )
        for table in semantic_model.tables
    }

    results = []

    for measure in measures:
        role = table_roles[measure.table_name]

        if role == "MEASURE_TABLE_CONFIRMED":
            results.append(
                finding_ok(
                    object=measure.qualified_name,
                    evidence={
                        "host_table_role": role,
                    },
                )
            )

        elif role == "DATA_TABLE":
            results.append(
                finding_ko(
                    object=measure.qualified_name,
                    reason=(
                        "Mesure hébergée dans une table contenant "
                        "des colonnes de données réelles"
                    ),
                    evidence={
                        "host_table": measure.table_name,
                        "host_table_role": role,
                    },
                )
            )

        else:
            results.append(
                finding_na(
                    object=measure.qualified_name,
                    reason=(
                        "Impossible de confirmer que la table hôte "
                        "est dédiée aux mesures"
                    ),
                )
            )

    return aggregate_ok_ko_na(results)
```

---

## 8. Statut global

```python
if any(r.status == "KO" for r in results):
    rule_status = "KO"

elif any(r.status == "NA" for r in results):
    rule_status = "NA"

else:
    rule_status = "OK"
```

Priorité :

```text
KO > NA > OK
```

---

## 9. Taux de centralisation

Le taux peut être conservé comme indicateur :

```text
centralized_measure_count / total_measure_count
```

Mais il ne remplace pas le verdict objet par objet.

Une seule mesure démontrée comme hébergée dans une table de données reste :

```text
KO
```

même si le taux global est élevé.

---

## 10. Preuve obligatoire

Pour un `KO` :

```text
measure
host_table
host_table_role = DATA_TABLE
real_data_columns
evidence
```

Pour un `OK` :

```text
measure
host_table
host_table_role = MEASURE_TABLE_CONFIRMED
support_columns
support_evidence
```

---

## 11. Résumé

```text
RÈGLE BP-24

RECENSER toutes les mesures

SI aucune mesure
    -> NA

CLASSER chaque table contenant des mesures

POUR chaque mesure
    SI table dédiée confirmée
        -> OK

    SI table de données confirmée
        -> KO

    SI rôle de table incertain
        -> NA
FIN
```

Le checker ne doit jamais identifier une table de mesures uniquement à partir de son nom.
