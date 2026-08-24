# BP-11 — Vérifier les types de données et la précision numérique

## 1. Objectif

Vérifier qu'un type numérique déclaré dans le modèle est cohérent avec une **intention de type démontrable**.

La règle doit éviter de déduire le besoin métier uniquement à partir :

- du nom d'une colonne ;
- d'un suffixe comme `_AMOUNT`, `_SCORE`, `_YEAR` ;
- d'un petit échantillon de valeurs ;
- d'une intuition sur le métier.

Statuts :

```text
OK / KO / NA
```

Les recommandations non prouvées sont portées par :

```text
diagnostic_level
```

et jamais par `rule_status = WARN`.

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
```

Sources complémentaires possibles :

```text
source_schema
company_policy
data_contract
column_statistics
```

Le `AnalysisContext` peut fournir pour chaque colonne :

```text
model_data_type
upstream_m_type
source_data_type
company_expected_type
statistics
usage
```

---

## 3. Types numériques

Exemples de types TMDL considérés :

```text
int64
double
decimal
```

Le moteur doit conserver la valeur brute et une version normalisée.

```python
NUMERIC_TYPES = {
    "int64",
    "double",
    "decimal",
}
```

---

## 4. Hiérarchie des preuves

Pour déterminer le type attendu, utiliser par ordre de fiabilité :

1. `COMPANY_POLICY` ou data contract explicitement associé à la colonne ;
2. schéma source fiable ;
3. conversion M explicite et résolue pour cette colonne ;
4. métadonnée technique équivalente validée ;
5. statistiques complètes, uniquement comme information complémentaire.

Les signaux suivants ne constituent pas une preuve suffisante à eux seuls :

```text
nom de colonne
suffixe
préfixe
échantillon partiel
```

---

## 5. Résolution de l'intention de type

```python
def resolve_expected_numeric_type(
    table,
    column,
    context,
):
    policy_type = context.company_policy.get_expected_type(
        table.name,
        column.name,
    )

    if policy_type is not None:
        return TypeExpectation(
            expected=policy_type,
            source="COMPANY_POLICY",
            confidence="EXPLICIT",
        )

    source_type = context.source_schema.get_type(
        table.name,
        column.source_column,
    )

    if source_type is not None:
        return TypeExpectation(
            expected=map_source_type_to_model_type(
                source_type
            ),
            source="SOURCE_SCHEMA",
            confidence="EXPLICIT",
        )

    upstream_type = context.m_type_index.get(
        (
            table.name,
            column.source_column or column.name,
        )
    )

    if upstream_type is not None:
        return TypeExpectation(
            expected=map_m_type_to_model_type(
                upstream_type
            ),
            source="POWER_QUERY",
            confidence="EXPLICIT",
        )

    return None
```

---

## 6. Signaux heuristiques

Les noms peuvent être utilisés uniquement pour produire un diagnostic.

Exemple :

```python
INTEGER_NAME_HINTS = (
    "_COUNT",
    "_NUMBER",
    "_ORDER",
    "_YEAR",
    "_RANK",
)

FIXED_DECIMAL_HINTS = (
    "_PRICE",
    "_AMOUNT",
    "_COST",
    "_RATE",
    "_PCT",
)
```

Si :

```text
column = TOTAL_AMOUNT
dataType = double
```

mais aucune politique, aucun schéma source et aucune intention de type fiable n'est disponible :

```text
rule_status = NA
diagnostic_level = INFO
```

et non :

```text
WARN
KO
```

---

## 7. Échantillons et statistiques

Un échantillon dans lequel toutes les valeurs sont entières ne prouve pas que la colonne doit toujours être entière.

Exemple :

```text
[1.0, 2.0, 3.0]
```

ne permet pas de conclure que des valeurs décimales ne peuvent jamais apparaître.

Donc :

```text
sample_all_integer = diagnostic
```

et non preuve de `KO`.

Des statistiques exhaustives peuvent renforcer un diagnostic, mais ne remplacent pas un contrat de type métier si la colonne peut évoluer.

---

## 8. Décision par colonne

```python
def evaluate_numeric_column(
    table,
    column,
    context,
):
    actual = normalize_model_type(
        column.data_type
    )

    if actual not in NUMERIC_TYPES:
        return finding_na(
            object=column.qualified_name,
            reason="Colonne hors périmètre numérique",
            reason_code="OUT_OF_SCOPE",
        )

    expectation = resolve_expected_numeric_type(
        table,
        column,
        context,
    )

    if expectation is None:
        diagnostics = build_numeric_type_diagnostics(
            table,
            column,
            context,
        )

        return finding_na(
            object=column.qualified_name,
            reason="Type métier attendu non démontrable",
            diagnostics=diagnostics,
        )

    expected = normalize_model_type(
        expectation.expected
    )

    if expected is None:
        return finding_na(
            object=column.qualified_name,
            reason="Type attendu non convertible vers le contrat TMDL",
        )

    if actual == expected:
        return finding_ok(
            object=column.qualified_name,
            expected=expected,
            actual=actual,
            evidence={
                "expectation_source": expectation.source,
            },
        )

    return finding_ko(
        object=column.qualified_name,
        expected=expected,
        actual=actual,
        evidence={
            "expectation_source": expectation.source,
        },
    )
```

---

## 9. Cas particuliers

### 9.1 `double` pour une valeur explicitement entière

Si Power Query ou un contrat source démontre :

```text
expected = int64
actual = double
```

alors :

```text
KO
```

### 9.2 `double` pour une valeur explicitement monétaire à précision fixe

Si une politique ou un schéma fiable démontre :

```text
expected = decimal
actual = double
```

alors :

```text
KO
```

### 9.3 nom `*_AMOUNT` sans autre preuve

```text
NA + diagnostic
```

### 9.4 nom `*_YEAR` sans autre preuve

```text
NA + diagnostic
```

### 9.5 `dataType` absent ou illisible

```text
NA
```

---

## 10. Matrice de décision

| Situation | Statut |
|---|---|
| type attendu explicitement démontré et identique au type modèle | `OK` |
| type attendu explicitement démontré et différent du type modèle | `KO` |
| uniquement indice de nommage | `NA` + diagnostic |
| uniquement échantillon partiel | `NA` + diagnostic |
| aucune preuve du type attendu | `NA` |
| type déclaré illisible | `NA` |
| colonne non numérique | `NA` hors périmètre |

---

## 11. Statut global

Les colonnes hors périmètre numérique ne doivent pas faire basculer le statut global.

```python
evaluable = [
    result
    for result in results
    if result.reason_code != "OUT_OF_SCOPE"
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

## 12. Preuve obligatoire

Un `KO` doit contenir :

```text
table
column
actual_type
expected_type
expectation_source
source_location
evidence
```

Exemples de `expectation_source` acceptables :

```text
COMPANY_POLICY
DATA_CONTRACT
SOURCE_SCHEMA
POWER_QUERY
```

Un suffixe de nom ne doit jamais apparaître comme seule preuve d'un `KO`.

---

## 13. Exemple

```json
{
  "rule_id": "BP-11",
  "rule_status": "KO",
  "ko_items": [
    {
      "table": "F_RESPONSES",
      "column": "SCORE_TOTAL",
      "actual_type": "double",
      "expected_type": "int64",
      "expectation_source": "POWER_QUERY",
      "evidence": {
        "m_type": "Int64.Type"
      }
    }
  ],
  "na_items": [
    {
      "table": "F_SALES",
      "column": "TOTAL_AMOUNT",
      "actual_type": "double",
      "reason": "Aucune preuve explicite du type métier attendu",
      "diagnostic_level": "INFO"
    }
  ]
}
```

---

## 14. Résumé

```text
RÈGLE BP-11

POUR chaque colonne numérique
    LIRE le type modèle

    RÉSOUDRE le type attendu depuis :
        politique
        contrat
        schéma source
        conversion M

    SI aucune preuve fiable
        -> NA + diagnostic éventuel

    SINON SI type modèle = type attendu
        -> OK

    SINON
        -> KO
FIN
```

La règle ne doit jamais transformer une convention de nommage ou un petit échantillon en preuve de non-conformité.
