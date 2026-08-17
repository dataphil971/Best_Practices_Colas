# BP-25 — Masquer les champs techniques démontrés

## 1. Objectif

Vérifier que les colonnes dont le rôle **purement technique** est démontré sont masquées avec :

```tmdl
isHidden
```

La difficulté de cette règle n'est pas de lire `isHidden`, mais de prouver qu'une colonne est réellement technique.

Une clé de relation, une colonne utilisée en DAX ou un nom terminant par `_ID` ne sont pas automatiquement des preuves suffisantes.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
<REPORT_PATH>/definition/**/*
```

Le moteur utilise notamment :

```text
usage_index
relationship_graph
sort_by_index
company_policy
technical_field_annotations
```

---

## 3. Rôle d'une colonne

Valeurs :

```text
TECHNICAL_CONFIRMED
BUSINESS_OR_USER_FACING
UNKNOWN
```

---

## 4. Preuves fortes d'un champ technique

### 4.1 Colonne exclusivement utilisée comme `sortByColumn`

Si une colonne :

- sert de cible `sortByColumn` ;
- n'a aucun autre usage sémantique direct ;
- n'est utilisée dans aucun visuel/slicer/filtre utilisateur ;

alors :

```text
TECHNICAL_CONFIRMED
```

### 4.2 Colonne de support explicitement déclarée

Exemples :

- métadonnée / annotation technique ;
- politique entreprise identifiant le champ ;
- colonne support d'une table de mesures ;
- champ de format/couleur explicitement configuré comme technique.

### 4.3 Clé de relation

Le simple fait d'être une clé de relation ne suffit pas.

Une clé comme :

```text
CustomerCode
ProductId
CountryCode
```

peut être utilisée directement par les utilisateurs.

Une clé de relation devient `TECHNICAL_CONFIRMED` seulement si une preuve supplémentaire existe :

```text
policy technical key
annotation
aucun usage utilisateur
champ de substitution explicitement disponible
```

---

## 5. Signaux faibles

Ces éléments ne produisent jamais à eux seuls un `KO` :

```text
nom en _ID
nom en _KEY
utilisée uniquement dans des mesures détectées
absence d'usage dans le rapport courant
relation key
```

Ils peuvent produire :

```text
diagnostic_level = INFO
```

ou contribuer à une revue contextuelle.

---

## 6. Usage utilisateur

Si la colonne est utilisée directement dans :

```text
visual
slicer
filter
drillthrough
tooltip
```

alors elle n'est pas prouvée purement technique.

Classification :

```text
BUSINESS_OR_USER_FACING
```

La règle BP-25 ne juge alors pas si elle devrait être masquée.

Résultat :

```text
NA / hors périmètre
```

---

## 7. Colonne métier masquée

Une colonne métier masquée n'est pas une non-conformité BP-25.

Le modèle peut volontairement masquer un champ :

- remplacé par une mesure ;
- exposé via une hiérarchie ;
- réservé à certains usages ;
- conservé pour compatibilité.

Donc :

```text
business field + isHidden
```

ne produit ni `WARN` ni `KO`.

Il est hors périmètre de cette règle.

---

## 8. Classification

```python
def classify_column_role(
    table,
    column,
    context,
):
    if context.company_policy.is_explicit_technical_field(
        table.name,
        column.name,
    ):
        return "TECHNICAL_CONFIRMED"

    if context.annotations.is_technical_field(
        table.name,
        column.name,
    ):
        return "TECHNICAL_CONFIRMED"

    usages = context.usage_index.get_column_usages(
        table.name,
        column.name,
    )

    if usages.has_user_facing_report_usage:
        return "BUSINESS_OR_USER_FACING"

    if context.sort_by_index.is_exclusive_sort_key(
        table.name,
        column.name,
        usages,
    ):
        return "TECHNICAL_CONFIRMED"

    if context.measure_table_support_index.is_support_column(
        table.name,
        column.name,
    ):
        return "TECHNICAL_CONFIRMED"

    return "UNKNOWN"
```

---

## 9. Décision

| Rôle | `isHidden` | Statut |
|---|---|---|
| `TECHNICAL_CONFIRMED` | présent | `OK` |
| `TECHNICAL_CONFIRMED` | absent | `KO` |
| `BUSINESS_OR_USER_FACING` | présent/absent | `NA` |
| `UNKNOWN` | présent/absent | `NA` |

---

## 10. Pseudo-code

```python
def evaluate_column(
    table,
    column,
    context,
):
    role = classify_column_role(
        table,
        column,
        context,
    )

    if role == "TECHNICAL_CONFIRMED":
        if column.is_hidden:
            return finding_ok(
                object=column.qualified_name,
                expected="isHidden",
                actual="isHidden",
                evidence={
                    "role": role,
                    "role_evidence": context.column_role_evidence(
                        table.name,
                        column.name,
                    ),
                },
            )

        return finding_ko(
            object=column.qualified_name,
            expected="isHidden",
            actual="visible",
            evidence={
                "role": role,
                "role_evidence": context.column_role_evidence(
                    table.name,
                    column.name,
                ),
            },
        )

    return finding_na(
        object=column.qualified_name,
        reason=(
            "La colonne n'est pas démontrée comme "
            "purement technique"
        ),
        reason_code="OUT_OF_SCOPE_OR_UNKNOWN",
    )
```

---

## 11. Statut global

Seules les colonnes `TECHNICAL_CONFIRMED` sont évaluables.

```python
evaluable = [
    r for r in results
    if r.reason_code != "OUT_OF_SCOPE_OR_UNKNOWN"
]

if any(r.status == "KO" for r in evaluable):
    rule_status = "KO"

elif evaluable:
    rule_status = "OK"

else:
    rule_status = "NA"
```

---

## 12. Preuve obligatoire

Un `KO` doit contenir :

```text
table
column
role = TECHNICAL_CONFIRMED
role_evidence
isHidden = false/absent
usage_summary
evidence
```

Une heuristique de nommage seule n'est jamais une preuve acceptable.

---

## 13. Résumé

```text
RÈGLE BP-25

POUR chaque colonne
    DÉTERMINER son rôle

    SI purement technique démontré
        SI isHidden
            -> OK
        SINON
            -> KO

    SINON
        -> NA
FIN
```
