# BP-32 — Utiliser des mesures explicites plutôt que des agrégations implicites

## 1. Objectif

Détecter dans le rapport les **agrégations implicites explicitement sérialisées** dans le PBIR.

La règle ne doit pas déduire une agrégation uniquement à partir :

- du nom d'une zone (`Values`, `Y`, `Data`) ;
- du type de visuel ;
- de la présence d'une colonne dans une projection.

Le signal déterministe recherché est un nœud d'agrégation appliqué à une colonne.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<REPORT_PATH>/definition/pages/**/visual.json
```

Le moteur doit parcourir l'intégralité des structures de champs des visuels.

Il peut utiliser :

```text
pbir_parser
report_field_index
```

---

## 3. Signature d'une agrégation implicite

Exemple conceptuel :

```json
{
  "Aggregation": {
    "Expression": {
      "Column": {
        "Expression": {
          "SourceRef": {
            "Entity": "F_SALES"
          }
        },
        "Property": "AMOUNT"
      }
    },
    "Function": 0
  }
}
```

Ce motif signifie qu'une fonction d'agrégation est appliquée à une colonne.

Il constitue une preuve suffisante de :

```text
IMPLICIT_AGGREGATION
```

---

## 4. Référence à une mesure explicite

Exemple :

```json
{
  "Measure": {
    "Expression": {
      "SourceRef": {
        "Entity": "MEASURE"
      }
    },
    "Property": "Sales Amount"
  }
}
```

Classification :

```text
EXPLICIT_MEASURE
```

---

## 5. Colonne sans nœud d'agrégation

Exemple :

```json
{
  "Column": {
    "Expression": {
      "SourceRef": {
        "Entity": "D_DATE"
      }
    },
    "Property": "Year"
  }
}
```

Ce motif ne prouve pas une agrégation implicite.

Il peut correspondre à :

- un axe ;
- un slicer ;
- une ligne de tableau ;
- un filtre ;
- une projection non agrégée.

Résultat pour BP-32 :

```text
NEUTRAL
```

Le checker ne doit pas la classer `KO` seulement parce qu'elle apparaît dans une zone nommée `Values`.

---

## 6. Parcours récursif des champs

La structure PBIR peut varier selon le visuel.

Le moteur doit rechercher récursivement les nœuds `Aggregation`.

Pseudo-code :

```python
def classify_field_node(
    node,
):
    if not isinstance(node, dict):
        return []

    findings = []

    if "Aggregation" in node:
        aggregation = node["Aggregation"]

        if contains_column_reference(
            aggregation
        ):
            findings.append(
                "IMPLICIT_AGGREGATION"
            )
        else:
            findings.append(
                "UNKNOWN_AGGREGATION"
            )

    if "Measure" in node:
        findings.append(
            "EXPLICIT_MEASURE"
        )

    for value in node.values():
        if isinstance(value, dict):
            findings.extend(
                classify_field_node(value)
            )
        elif isinstance(value, list):
            for item in value:
                findings.extend(
                    classify_field_node(item)
                )

    return findings
```

Le parser doit éviter de compter deux fois le même nœud.

---

## 7. Structures inconnues

Si un visuel contient une structure de champ non reconnue et que le parseur ne peut pas garantir qu'aucune agrégation implicite n'est cachée dans cette structure :

```text
NA
```

Le fallback suivant est interdit :

```python
aggregation_zones = set(query_state.keys())
```

pour un `visualType` inconnu.

Un type de visuel inconnu ne transforme pas automatiquement toutes ses projections en agrégations.

---

## 8. Décision par projection / visuel

| Signal | Statut |
|---|---|
| `Aggregation` appliqué à `Column` | `KO` |
| `Measure` | conforme / aucune agrégation implicite sur cette projection |
| `Column` sans `Aggregation` | neutre |
| structure inconnue potentiellement décisionnelle | `NA` |
| visuel sans données | hors périmètre |

---

## 9. Décision globale

L'absence d'agrégation implicite peut être déclarée `OK` uniquement si la couverture de parsing est complète.

```python
def evaluate_bp32(
    report,
    context,
):
    implicit = []
    unresolved = []

    for visual in report.visuals:
        parsed = context.pbir_parser.parse_visual(
            visual
        )

        if not parsed.success:
            unresolved.append({
                "visual": visual.id,
                "reason": parsed.error,
            })
            continue

        for field_node in parsed.field_nodes:
            classification = classify_field_node(
                field_node
            )

            if "IMPLICIT_AGGREGATION" in classification:
                implicit.append({
                    "page": visual.page_name,
                    "visual": visual.id,
                    "field": field_node,
                })

            if "UNKNOWN_AGGREGATION" in classification:
                unresolved.append({
                    "visual": visual.id,
                    "reason": "Agrégation non résolue",
                })

    if implicit:
        return rule_ko(
            evidence={
                "implicit_aggregations": implicit,
            },
        )

    if unresolved:
        return rule_na(
            reason="Couverture PBIR incomplète",
            evidence={
                "unresolved": unresolved,
            },
        )

    return rule_ok(
        evidence={
            "implicit_aggregation_count": 0,
        },
    )
```

---

## 10. Statut technique

Un fichier illisible doit produire par exemple :

```json
{
  "execution_status": "PARTIAL",
  "rule_status": "NA"
}
```

et non :

```text
NON_EVALUE
```

comme quatrième statut métier.

---

## 11. Preuve obligatoire pour KO

```text
page
visual_id
source_file
table
column
aggregation_node
aggregation_function_raw
evidence
```

Le nom de la zone du visuel peut être conservé comme contexte, mais ne constitue pas la preuve principale.

---

## 12. Résumé

```text
RÈGLE BP-32

PARCOURIR tous les field nodes PBIR

SI Aggregation(Column) détecté
    -> KO

SI structure décisionnelle non lisible
    -> NA

SI analyse complète
   ET aucun Aggregation(Column)
    -> OK
```
