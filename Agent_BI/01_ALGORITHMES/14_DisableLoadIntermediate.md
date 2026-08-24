# BP-14 — Désactiver le chargement des requêtes strictement intermédiaires

## 1. Objectif

Vérifier qu'une requête dont le rôle **strictement intermédiaire** est démontré n'est pas chargée inutilement comme table du modèle.

La règle doit éviter de classer automatiquement comme intermédiaire toute table qui :

```text
est référencée par une autre requête
+
n'a pas de relation
```

Une table chargée peut être volontairement :

- une table déconnectée ;
- une table de paramétrage ;
- une table utilisée directement par des mesures ;
- une table utilisée dans un visuel ;
- une table destinée au self-service ;
- une table consommée par une perspective.

L'absence de relation ne prouve donc pas qu'elle est intermédiaire.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/model.tmdl
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
<REPORT_PATH>/definition/**/*
```

La règle utilise surtout :

```text
query_dependency_graph
loaded_table_index
usage_index
company_policy
```

---

## 3. Définition d'une requête strictement intermédiaire

Une requête peut être déclarée `STRICT_INTERMEDIATE` seulement si toutes les conditions nécessaires sont satisfaites.

### Condition A — elle alimente une ou plusieurs requêtes

```text
referenced_by_count > 0
```

### Condition B — elle n'a aucun usage sémantique direct dans le périmètre analysé

Aucun usage résolu dans :

```text
relationships
DAX
report visuals
report filters
sorts
hierarchies
roles
perspectives
calculation groups
```

### Condition C — son intention intermédiaire est démontrée

Au moins une preuve forte parmi :

- expression non chargée dans `expressions.tmdl` ;
- métadonnée / convention explicite de staging définie par `COMPANY_POLICY` ;
- annotation projet indiquant le rôle intermédiaire ;
- classification structurée fiable produite par le contexte.

Un simple préfixe comme :

```text
STG_
TMP_
INT_
```

n'est qu'un indice tant que cette convention n'est pas configurée.

---

## 4. Classification du rôle

```text
STRICT_INTERMEDIATE
FINAL_OR_SEMANTIC
UNKNOWN
```

Pseudo-code :

```python
def classify_query_role(
    query,
    context,
):
    downstream = context.query_graph.referenced_by(
        query.name
    )

    if not downstream:
        return "FINAL_OR_SEMANTIC"

    semantic_usages = context.usage_index.get_table_usages(
        query.name
    )

    if semantic_usages:
        return "FINAL_OR_SEMANTIC"

    explicit_role = context.company_policy.get_query_role(
        query.name
    )

    if explicit_role == "INTERMEDIATE":
        return "STRICT_INTERMEDIATE"

    if query.kind == "EXPRESSION" and not query.is_loaded:
        return "STRICT_INTERMEDIATE"

    return "UNKNOWN"
```

---

## 5. Chargement

Valeurs :

```text
LOADED
NOT_LOADED
UNKNOWN
```

La présence d'une table dans `model.tmdl` / `tables/*.tmdl` peut être utilisée comme preuve de chargement.

Le moteur doit vérifier la cohérence entre :

```text
ref table
table file
query index
```

Si ces sources se contredisent :

```text
UNKNOWN
```

---

## 6. Décision

| Rôle | Chargement | Statut |
|---|---|---|
| `STRICT_INTERMEDIATE` | `NOT_LOADED` | `OK` |
| `STRICT_INTERMEDIATE` | `LOADED` | `KO` |
| `FINAL_OR_SEMANTIC` | quelconque | `NA` hors périmètre |
| `UNKNOWN` | `LOADED` | `NA` |
| `UNKNOWN` | `NOT_LOADED` | `NA` |
| chargement indéterminable | — | `NA` |

---

## 7. UsageIndex obligatoire avant KO

Avant de déclarer une table chargée comme intermédiaire, rechercher les usages directs.

Pseudo-code :

```python
def has_direct_semantic_usage(
    table_name,
    usage_index,
):
    usages = usage_index.get_table_usages(
        table_name
    )

    return bool(
        usages.relationships
        or usages.dax
        or usages.report_visuals
        or usages.report_filters
        or usages.sorts
        or usages.hierarchies
        or usages.roles
        or usages.perspectives
    )
```

Si une surface d'usage essentielle est absente du périmètre d'analyse :

```text
coverage_incomplete = true
```

et qu'elle pourrait changer la classification :

```text
NA
```

---

## 8. Pseudo-code

```python
def evaluate_query_load(
    query,
    context,
):
    role = classify_query_role(
        query,
        context,
    )

    load_state = context.loaded_table_index.get_state(
        query.name
    )

    if role == "FINAL_OR_SEMANTIC":
        return finding_na(
            object=query.name,
            reason="Requête finale ou sémantique : hors périmètre",
            reason_code="OUT_OF_SCOPE",
        )

    if role == "UNKNOWN":
        return finding_na(
            object=query.name,
            reason="Rôle intermédiaire non démontré",
        )

    if load_state == "UNKNOWN":
        return finding_na(
            object=query.name,
            reason="État de chargement non déterminable",
        )

    if load_state == "LOADED":
        return finding_ko(
            object=query.name,
            expected="NOT_LOADED",
            actual="LOADED",
            evidence={
                "referenced_by": context.query_graph.referenced_by(
                    query.name
                ),
                "semantic_usages": [],
                "role_evidence": context.query_role_evidence(
                    query.name
                ),
            },
        )

    return finding_ok(
        object=query.name,
        expected="NOT_LOADED",
        actual="NOT_LOADED",
    )
```

---

## 9. Statut global

Les objets `FINAL_OR_SEMANTIC` sont hors périmètre.

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

## 10. Preuve obligatoire pour KO

```text
query
role = STRICT_INTERMEDIATE
role_evidence
referenced_by
semantic_usage_count = 0
usage_coverage
load_state = LOADED
load_evidence
```

Sans preuve du rôle strictement intermédiaire :

```text
NA
```

---

## 11. Résumé

```text
RÈGLE BP-14

CONSTRUIRE le graphe des requêtes
CONSTRUIRE usage_index
DÉTERMINER l'état de chargement

POUR chaque requête
    DÉTERMINER son rôle

    SI finale / sémantique
        -> NA hors périmètre

    SI rôle inconnu
        -> NA

    SI strictement intermédiaire
        SI chargée
            -> KO
        SINON
            -> OK
FIN
```
