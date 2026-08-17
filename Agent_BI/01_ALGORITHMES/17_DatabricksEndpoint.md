# BP-17 — Utiliser un SQL Warehouse pour Databricks en DirectQuery

## 1. Objectif

Vérifier que les partitions Power BI utilisant Databricks en mode `directQuery` s'appuient sur un **Databricks SQL Warehouse** plutôt que sur un compute cluster interactif.

Cette règle ne doit pas supposer le type d'endpoint à partir d'un nom de paramètre ou d'un identifiant incomplet.

Statuts :

```text
OK / KO / NA
```

---

## 2. Périmètre

La règle s'applique uniquement aux partitions réunissant les deux conditions :

```text
mode = directQuery
connecteur = Databricks
```

Les partitions `import` sont hors périmètre :

```text
NA
```

Les partitions hybrides sont évaluées partition par partition.

---

## 3. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
```

Le `AnalysisContext` doit fournir si possible :

```text
partition_mode
connector
server_hostname
http_path
parameter_resolution
endpoint_metadata
```

---

## 4. Classification de l'endpoint

Valeurs possibles :

```text
SQL_WAREHOUSE
COMPUTE_CLUSTER
UNKNOWN
```

La classification doit privilégier une métadonnée structurée lorsqu'elle existe.

À défaut, le `httpPath` peut être utilisé comme preuve.

### SQL Warehouse

Exemple de forme documentée :

```text
/sql/1.0/warehouses/<warehouse-id>
```

Cette forme est une preuve forte de :

```text
SQL_WAREHOUSE
```

### Compute cluster

Si le format du chemin est explicitement reconnu par le connecteur / la politique comme un endpoint de compute cluster :

```text
COMPUTE_CLUSTER
```

### Autre forme

Une forme inconnue ne doit pas être assimilée à un cluster.

```text
UNKNOWN
```

---

## 5. Résolution du `httpPath`

Le second argument de `Databricks.Catalogs` peut être :

- un littéral ;
- un paramètre ;
- une concaténation ;
- une expression dynamique.

Pseudo-code :

```python
def resolve_http_path(
    databricks_call,
    context,
):
    arg = databricks_call.arguments[1]

    if arg.is_string_literal:
        return Resolution(
            value=arg.value,
            status="RESOLVED",
        )

    resolved = context.m_constant_resolver.resolve(
        arg
    )

    if resolved.success:
        return Resolution(
            value=resolved.value,
            status="RESOLVED",
        )

    return Resolution(
        value=None,
        status="UNRESOLVED",
    )
```

Une valeur non résolue donne :

```text
NA
```

---

## 6. Classification robuste

```python
SQL_WAREHOUSE_PATH = re.compile(
    r"^/sql/1\.0/warehouses/[^/]+$",
    re.IGNORECASE,
)

def classify_databricks_endpoint(
    http_path,
    endpoint_metadata=None,
):
    if endpoint_metadata is not None:
        if endpoint_metadata.type == "SQL_WAREHOUSE":
            return "SQL_WAREHOUSE"

        if endpoint_metadata.type == "COMPUTE_CLUSTER":
            return "COMPUTE_CLUSTER"

    if http_path is None:
        return "UNKNOWN"

    normalized = http_path.strip()

    if SQL_WAREHOUSE_PATH.fullmatch(normalized):
        return "SQL_WAREHOUSE"

    cluster_type = classify_known_compute_path(
        normalized
    )

    if cluster_type == "COMPUTE_CLUSTER":
        return "COMPUTE_CLUSTER"

    return "UNKNOWN"
```

Le checker ne doit pas maintenir une regex supposée exhaustive de tous les formats historiques ou futurs d'endpoints Databricks.

---

## 7. Décision

| Situation | Statut |
|---|---|
| Databricks + `directQuery` + SQL Warehouse démontré | `OK` |
| Databricks + `directQuery` + compute cluster démontré | `KO` |
| Databricks + `directQuery` + endpoint indéterminable | `NA` |
| Databricks + `import` | `NA` hors périmètre |
| autre connecteur | `NA` hors périmètre |
| mode de partition illisible | `NA` |

---

## 8. Pseudo-code

```python
def evaluate_partition(
    table,
    partition,
    context,
):
    if partition.mode != "directQuery":
        return finding_na(
            object=f"{table.name}/{partition.name}",
            reason="Partition hors périmètre DirectQuery",
            reason_code="OUT_OF_SCOPE",
        )

    databricks_call = find_databricks_catalogs_call(
        partition,
        context.query_graph,
    )

    if databricks_call is None:
        return finding_na(
            object=f"{table.name}/{partition.name}",
            reason="Partition DirectQuery non Databricks",
            reason_code="OUT_OF_SCOPE",
        )

    path = resolve_http_path(
        databricks_call,
        context,
    )

    if path.status != "RESOLVED":
        return finding_na(
            object=f"{table.name}/{partition.name}",
            reason="HTTP Path Databricks non résolvable",
        )

    endpoint = classify_databricks_endpoint(
        path.value,
        endpoint_metadata=context.endpoint_metadata.get(
            path.value
        ),
    )

    if endpoint == "SQL_WAREHOUSE":
        return finding_ok(
            object=f"{table.name}/{partition.name}",
            expected="SQL_WAREHOUSE",
            actual=endpoint,
            evidence={
                "http_path": path.value,
            },
        )

    if endpoint == "COMPUTE_CLUSTER":
        return finding_ko(
            object=f"{table.name}/{partition.name}",
            expected="SQL_WAREHOUSE",
            actual=endpoint,
            evidence={
                "http_path": path.value,
            },
        )

    return finding_na(
        object=f"{table.name}/{partition.name}",
        reason="Type d'endpoint Databricks non déterminable",
        evidence={
            "http_path": path.value,
        },
    )
```

---

## 9. Statut global

Les objets hors périmètre ne font pas basculer le résultat.

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

## 10. Preuve obligatoire

Un `KO` doit contenir :

```text
table
partition
mode = directQuery
connector = Databricks
endpoint_type = COMPUTE_CLUSTER
http_path ou endpoint_metadata
evidence
```

Si l'endpoint n'est pas démontrable :

```text
NA
```

---

## 11. Références techniques

Les connecteurs Databricks pour Power BI prennent en charge Import et DirectQuery.

La documentation Microsoft / Databricks recommande l'utilisation d'un Databricks SQL Warehouse pour Power BI en DirectQuery.

---

## 12. Résumé

```text
RÈGLE BP-17

POUR chaque partition
    SI pas DirectQuery
        -> NA hors périmètre

    SI pas Databricks
        -> NA hors périmètre

    RÉSOUDRE le HTTP Path
    CLASSER l'endpoint

    SQL_WAREHOUSE
        -> OK

    COMPUTE_CLUSTER
        -> KO

    UNKNOWN
        -> NA
FIN
```
