# BP-16 — Actualisation incrémentielle des tables volumineuses éligibles

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier qu'une table explicitement considérée comme éligible à l'actualisation incrémentielle dispose d'une configuration cohérente.

La règle sépare deux questions :

1. **La table doit-elle utiliser l'actualisation incrémentielle ?**
2. **Si oui ou si une politique est déjà déclarée, la configuration est-elle correcte ?**

L'éligibilité ne doit jamais être devinée à partir :

- du préfixe `F_` ;
- du nom de la table ;
- d'un seuil codé en dur dans le checker.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
```

Contexte externe éventuel :

```text
row_count
model_size
refresh_duration
growth_rate
company_policy
table_role_index
```

---

## 3. Applicabilité

Une table devient `REQUIRED` pour BP-16 seulement si le contexte d'audit permet de le démontrer.

Exemples :

```text
COMPANY_POLICY
row_count >= seuil configuré
refresh_duration >= seuil configuré
growth_rate >= seuil configuré
classification explicite de la table
```

Pseudo-code :

```python
def incremental_refresh_requirement(
    table,
    context,
):
    explicit = context.company_policy.get_incremental_refresh_requirement(
        table.name
    )

    if explicit is not None:
        return explicit

    threshold = context.company_policy.large_table_row_threshold

    row_count = context.statistics.get_row_count(
        table.name
    )

    if threshold is not None and row_count is not None:
        return (
            "REQUIRED"
            if row_count >= threshold
            else "NOT_REQUIRED"
        )

    return "UNKNOWN"
```

Aucun seuil ne doit être inventé par le checker.

---

## 4. Modes de stockage

Une table entièrement DirectQuery n'est pas évaluée comme une table Import classique.

```text
DIRECTQUERY_ONLY -> NA / hors périmètre
```

Les modèles hybrides ou les politiques combinant Import et temps réel doivent être analysés selon leur configuration réelle, sans les assimiler à du DirectQuery pur.

---

## 5. Paramètres requis

Pour la configuration standard d'actualisation incrémentielle, vérifier les paramètres :

```text
RangeStart
RangeEnd
```

Les noms sont sensibles à la casse.

Leur type doit être compatible avec la configuration attendue, généralement :

```text
Date/Time
```

Le moteur doit conserver :

```text
parameter_name
parameter_type
parameter_value
source_location
```

---

## 6. Filtre temporel

La simple présence textuelle de :

```text
RangeStart
RangeEnd
```

dans la partition ne suffit pas.

Le checker doit démontrer :

1. qu'ils participent à un filtre de lignes ;
2. qu'ils encadrent la **même colonne** de partition ;
3. que la borne inférieure et la borne supérieure sont cohérentes ;
4. que l'égalité n'est utilisée que sur l'une des deux bornes, pas sur les deux.

Exemples valides :

```m
[OrderDate] >= RangeStart
and
[OrderDate] < RangeEnd
```

ou :

```m
[OrderDate] > RangeStart
and
[OrderDate] <= RangeEnd
```

Exemple invalide :

```m
[OrderDate] >= RangeStart
and
[OrderDate] <= RangeEnd
```

car les deux bornes sont inclusives.

---

## 7. Résolution structurée du filtre

```python
def analyze_incremental_filter(
    partition,
    context,
):
    filters = context.m_ast.find_table_select_rows(
        partition
    )

    candidates = []

    for filter_step in filters:
        predicates = parse_predicates(
            filter_step.predicate
        )

        lower = find_range_boundary(
            predicates,
            parameter="RangeStart",
        )

        upper = find_range_boundary(
            predicates,
            parameter="RangeEnd",
        )

        if lower is None or upper is None:
            continue

        if lower.column != upper.column:
            candidates.append({
                "valid": False,
                "reason": "RangeStart et RangeEnd filtrent des colonnes différentes",
            })
            continue

        inclusive_count = int(
            lower.operator in {">=", "<="}
        ) + int(
            upper.operator in {">=", "<="}
        )

        valid_operators = (
            lower.operator in {">", ">="}
            and upper.operator in {"<", "<="}
            and inclusive_count == 1
        )

        candidates.append({
            "valid": valid_operators,
            "column": lower.column,
            "lower_operator": lower.operator,
            "upper_operator": upper.operator,
            "step": filter_step.name,
        })

    return candidates
```

---

## 8. Politique incrémentielle

Le moteur doit lire le bloc de politique TMDL structuré et vérifier qu'il est parsable.

Il conserve notamment :

```text
policyType
incrementalPeriod
incrementalPeriodType
rollingWindowPeriod
rollingWindowGranularity
detectDataChanges
```

Une valeur illisible ou un bloc partiellement parsé :

```text
NA
```

sauf si une incohérence objective est démontrée.

---

## 9. Query folding du filtre

La documentation Power BI recommande que le filtre utilisant `RangeStart` et `RangeEnd` puisse être replié vers la source pour éviter un chargement inefficace.

Mais BP-16 ne doit pas dupliquer BP-15.

Donc :

```text
folding_status
```

est ajouté comme diagnostic / référence croisée.

Si une preuve runtime indique que le filtre ne fold pas :

```text
diagnostic_level = WARNING
related_rule = BP-15
```

Le statut BP-16 reste centré sur la configuration de l'actualisation incrémentielle.

---

## 10. Décision

### Cas A — politique présente

Si `incrementalPolicy` existe, la configuration doit être cohérente indépendamment du seuil.

| Situation | Statut |
|---|---|
| politique présente + paramètres corrects + filtre correct | `OK` |
| politique présente + `RangeStart` ou `RangeEnd` absent | `KO` |
| politique présente + filtre absent | `KO` |
| politique présente + colonnes de filtre différentes | `KO` |
| politique présente + bornes toutes deux inclusives | `KO` |
| politique illisible | `NA` |

### Cas B — politique absente

| Applicabilité | Statut |
|---|---|
| `REQUIRED` | `KO` |
| `NOT_REQUIRED` | `NA` |
| `UNKNOWN` | `NA` |

Une table sous le seuil n'est pas `OK` pour cette règle : elle est simplement hors obligation.

---

## 11. Pseudo-code

```python
def evaluate_incremental_refresh(
    table,
    context,
):
    if table.storage_mode == "DIRECTQUERY_ONLY":
        return finding_na(
            object=table.name,
            reason="Table DirectQuery : hors périmètre",
            reason_code="OUT_OF_SCOPE",
        )

    policy = table.incremental_policy

    if policy is not None:
        if not policy.parse_ok:
            return finding_na(
                object=table.name,
                reason="Politique incrémentielle illisible",
            )

        range_start = context.parameters.get(
            "RangeStart"
        )

        range_end = context.parameters.get(
            "RangeEnd"
        )

        if range_start is None or range_end is None:
            return finding_ko(
                object=table.name,
                reason="Paramètres RangeStart/RangeEnd manquants",
            )

        if not range_parameter_types_are_valid(
            range_start,
            range_end,
        ):
            return finding_ko(
                object=table.name,
                reason="Type RangeStart/RangeEnd incompatible",
            )

        filters = analyze_incremental_filter(
            table.import_partition,
            context,
        )

        valid_filters = [
            f for f in filters
            if f["valid"]
        ]

        if not valid_filters:
            return finding_ko(
                object=table.name,
                reason="Filtre incrémentiel RangeStart/RangeEnd invalide ou absent",
                evidence={"filters": filters},
            )

        return finding_ok(
            object=table.name,
            evidence={
                "policy": policy.to_evidence(),
                "valid_filters": valid_filters,
            },
        )

    requirement = incremental_refresh_requirement(
        table,
        context,
    )

    if requirement == "REQUIRED":
        return finding_ko(
            object=table.name,
            reason="Table explicitement éligible sans incrementalPolicy",
            evidence=context.incremental_requirement_evidence(
                table.name
            ),
        )

    if requirement == "NOT_REQUIRED":
        return finding_na(
            object=table.name,
            reason="Actualisation incrémentielle non requise",
            reason_code="OUT_OF_SCOPE",
        )

    return finding_na(
        object=table.name,
        reason="Applicabilité non déterminable avec les données disponibles",
    )
```

---

## 12. Statut global

Les tables `NOT_REQUIRED` et DirectQuery pur sont hors périmètre.

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

---

## 13. Preuve obligatoire

Pour un `KO` dû à l'absence de politique :

```text
table
requirement = REQUIRED
requirement_source
threshold_if_used
observed_metric
evidence
```

Pour un `KO` dû à une politique mal configurée :

```text
table
incrementalPolicy
RangeStart
RangeEnd
filter_step
filtered_column
lower_operator
upper_operator
evidence
```

---

## 14. Références techniques

Cette logique suit les principes Microsoft Learn relatifs à l'actualisation incrémentielle :

- paramètres réservés et sensibles à la casse `RangeStart` et `RangeEnd` ;
- filtrage de la colonne temporelle avec les deux paramètres ;
- égalité sur une seule des deux bornes pour éviter les doublons entre partitions ;
- définition d'une politique après mise en place du filtre.

---

## 15. Résumé

```text
RÈGLE BP-16

POUR chaque table
    SI DirectQuery pur
        -> NA hors périmètre

    SI incrementalPolicy présente
        VÉRIFIER RangeStart
        VÉRIFIER RangeEnd
        VÉRIFIER type des paramètres
        VÉRIFIER filtre sur la même colonne
        VÉRIFIER bornes cohérentes
        VÉRIFIER une seule borne inclusive

        SI configuration correcte
            -> OK
        SI incohérence prouvée
            -> KO
        SINON
            -> NA

    SINON
        DÉTERMINER si la politique est requise

        REQUIRED -> KO
        NOT_REQUIRED -> NA
        UNKNOWN -> NA
FIN
```
