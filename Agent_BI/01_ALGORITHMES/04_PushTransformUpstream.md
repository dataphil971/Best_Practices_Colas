# BP-04 (alias SEM-003) — Pousser les transformations en amont

## 1. Objectif

Vérifier que les transformations lourdes sont exécutées le plus en amont possible lorsque cela peut être **démontré techniquement**.

Cette règle ne doit pas conclure qu'une transformation est locale uniquement parce qu'une fonction M lourde apparaît dans Power Query. Une opération écrite en M peut encore être exécutée côté source grâce au **query folding**.

Le verdict repose donc sur trois éléments observables :

1. la nature de la source racine ;
2. la nature des étapes M ;
3. la preuve disponible sur l'exécution locale ou repliée des étapes.

Statuts autorisés :

```text
OK / KO / NA
```

Les avertissements éventuels sont portés dans un champ séparé :

```text
diagnostic_level = INFO | WARNING | CRITICAL
```

`diagnostic_level` ne modifie jamais directement `rule_status`.

---

## 2. Sources analysées

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
```

Le moteur exploite le `AnalysisContext` construit une seule fois lors de la lecture du PBIP.

Il ne relit pas le projet complet pour chaque règle.

Pour chaque requête M atteignable depuis une table chargée, le contexte doit fournir si possible :

```text
query_name
query_kind
m_code
origin_file
referenced_queries
root_source
steps
folding_evidence
parse_status
```

---

## 3. Périmètre

La règle porte sur les tables et expressions contenant du code M réellement utilisé par le modèle.

Sont hors périmètre ou non évaluables :

- table calculée DAX sans partition M ;
- table DirectLake sans code M exploitable ;
- expression purement paramétrique ;
- requête non atteignable depuis une table chargée ;
- code M absent, tronqué ou non parsable.

Dans ces cas :

```text
NA
```

---

## 4. Construire le graphe des requêtes

Le moteur doit résoudre les dépendances entre tables et expressions partagées.

```python
queries = build_m_query_index(context)

reachable = collect_queries_reachable_from_loaded_tables(
    queries=queries,
    loaded_tables=context.loaded_tables,
)
```

Une référence circulaire ou non résolue ne doit jamais être assimilée à une source brute.

```text
référence circulaire / source non résolue -> NA
```

---

## 5. Classification de la source racine

Classification minimale :

```text
DATAFLOW
CURATED_OR_GOLD
DATABASE
FILE_OR_LIST
NATIVE_QUERY
UNKNOWN
CIRCULAR_REFERENCE
```

Exemples de signaux :

```python
def classify_root_source(expr):
    if is_dataflow_connector(expr):
        return "DATAFLOW"

    if is_explicit_curated_or_gold_source(expr):
        return "CURATED_OR_GOLD"

    if is_value_native_query(expr):
        return "NATIVE_QUERY"

    if is_database_connector(expr):
        return "DATABASE"

    if is_file_list_or_web_connector(expr):
        return "FILE_OR_LIST"

    return "UNKNOWN"
```

### Important

Le moteur ne doit pas déduire qu'une table est « gold » uniquement à partir d'un mot présent dans son nom.

Une source est `CURATED_OR_GOLD` seulement si cette information provient :

- d'une configuration projet ;
- d'une métadonnée fiable ;
- d'un chemin / schéma explicitement reconnu par la politique de l'entreprise ;
- ou d'une information déjà validée dans le contexte d'analyse.

Sinon :

```text
UNKNOWN
```

---

## 6. Classification des étapes M

Chaque étape M reçoit une classification :

```text
HEAVY
LIGHT
UNKNOWN
```

Exemples d'étapes généralement lourdes :

```text
Table.Group
Table.Pivot
Table.Unpivot
Table.UnpivotOtherColumns
Table.NestedJoin
Table.Join
Table.FuzzyNestedJoin
Table.FuzzyGroup
Table.Combine
Python.Execute
R.Execute
```

Certaines fonctions doivent être évaluées avec leur contexte :

```text
Table.AddColumn
Table.ExpandTableColumn
Table.ReplaceValue
Table.SplitColumn
```

Exemples d'étapes généralement légères :

```text
Table.TransformColumnTypes
Table.RenameColumns
Table.SelectColumns
Table.RemoveColumns
Table.Sort
navigation simple
filtre simple
```

Pseudo-code :

```python
def classify_step(step, previous_steps):
    fn = step.called_function

    if fn in HEAVY_FUNCTIONS:
        return "HEAVY"

    if fn in LIGHT_FUNCTIONS:
        return "LIGHT"

    if fn == "Table.AddColumn":
        if step.has_complex_multicolumn_or_conditional_logic():
            return "HEAVY"
        if step.is_simple_projection_or_concatenation():
            return "LIGHT"
        return "UNKNOWN"

    if fn == "Table.ExpandTableColumn":
        if previous_step_is_join(previous_steps):
            return "HEAVY"
        return "LIGHT"

    return "UNKNOWN"
```

### Règle essentielle

```text
UNKNOWN ≠ HEAVY
UNKNOWN ≠ LIGHT
```

Une fonction inconnue ne doit jamais être utilisée pour fabriquer un `OK` ou un `KO`.

Si une étape `UNKNOWN` peut changer la conclusion :

```text
NA
```

avec une preuve technique indiquant l'étape non classée.

---

## 7. Query folding

Une fonction M lourde n'est pas automatiquement une transformation exécutée localement.

Le moteur doit utiliser, lorsqu'elle existe, une preuve de folding issue par exemple :

- d'une métadonnée de diagnostic ;
- d'un test de folding ;
- d'une requête native ;
- d'une propriété source explicitement disponible ;
- d'une analyse structurée fiable de la chaîne M.

Valeurs possibles :

```text
FOLDED
NOT_FOLDED
UNKNOWN
NOT_APPLICABLE
```

### Cas fichier / SharePoint / CSV

Pour une source intrinsèquement non repliable :

```text
FILE_OR_LIST + étape lourde
    -> transformation locale démontrée
```

### Cas base de données

Pour une source base de données :

```text
DATABASE + étape lourde + FOLDED
    -> exécutée côté source

DATABASE + étape lourde + NOT_FOLDED
    -> exécutée localement

DATABASE + étape lourde + UNKNOWN
    -> impossible de conclure
```

---

## 8. Décision par requête

```python
def evaluate_query(query, context, cfg):
    if not query.has_m_code or not query.parse_ok:
        return finding_na(
            object=query.name,
            reason="Code M absent ou non interprétable",
        )

    source = query.root_source

    if source in {"UNKNOWN", "CIRCULAR_REFERENCE"}:
        return finding_na(
            object=query.name,
            reason="Source racine non déterminable de manière fiable",
            evidence={"root_source": source},
        )

    classifications = [
        classify_step(step, query.steps[:i])
        for i, step in enumerate(query.steps)
    ]

    unknown_steps = [
        step for step, c in zip(query.steps, classifications)
        if c == "UNKNOWN"
    ]

    heavy_steps = [
        step for step, c in zip(query.steps, classifications)
        if c == "HEAVY"
    ]

    if unknown_steps:
        return finding_na(
            object=query.name,
            reason="Étape(s) M non classable(s) de manière fiable",
            evidence={
                "unknown_steps": [s.name for s in unknown_steps],
                "root_source": source,
            },
        )

    if not heavy_steps:
        return finding_ok(
            object=query.name,
            evidence={
                "root_source": source,
                "heavy_steps": [],
            },
        )

    folding = determine_folding_status(
        query=query,
        context=context,
    )

    if source == "FILE_OR_LIST":
        return finding_ko(
            object=query.name,
            reason="Transformation lourde exécutée dans Power Query sur une source non repliable",
            evidence={
                "root_source": source,
                "heavy_steps": [s.name for s in heavy_steps],
                "folding_status": "NOT_APPLICABLE",
            },
        )

    if folding == "FOLDED":
        return finding_ok(
            object=query.name,
            evidence={
                "root_source": source,
                "heavy_steps": [s.name for s in heavy_steps],
                "folding_status": folding,
            },
        )

    if folding == "NOT_FOLDED":
        return finding_ko(
            object=query.name,
            reason="Transformation lourde démontrée comme exécutée localement",
            evidence={
                "root_source": source,
                "heavy_steps": [s.name for s in heavy_steps],
                "folding_status": folding,
            },
        )

    return finding_na(
        object=query.name,
        reason="Transformation lourde détectée mais lieu réel d'exécution non démontré",
        evidence={
            "root_source": source,
            "heavy_steps": [s.name for s in heavy_steps],
            "folding_status": "UNKNOWN",
        },
    )
```

---

## 9. Matrice de décision

| Source | Étape lourde | Folding | Statut |
|---|---:|---|---|
| source connue | non | — | `OK` |
| `FILE_OR_LIST` | oui | non applicable | `KO` |
| `DATABASE` / source foldable | oui | `FOLDED` | `OK` |
| `DATABASE` / source foldable | oui | `NOT_FOLDED` | `KO` |
| source foldable | oui | `UNKNOWN` | `NA` |
| source `UNKNOWN` | quelconque | quelconque | `NA` |
| étape `UNKNOWN` pouvant influencer la décision | — | — | `NA` |
| code M illisible | — | — | `NA` |

---

## 10. Statut global

Priorité :

```text
KO > NA > OK
```

```python
if any(r.status == "KO" for r in results):
    rule_status = "KO"
elif any(r.status == "NA" for r in results):
    rule_status = "NA"
else:
    rule_status = "OK"
```

Un `OK` global signifie que toutes les requêtes du périmètre ont été analysées suffisamment pour écarter une transformation lourde locale non conforme.

---

## 11. Preuve obligatoire

Chaque résultat doit contenir au minimum :

```text
rule_id
object
origin_file
root_source
heavy_steps
unknown_steps
folding_status
expected
actual
evidence
rule_status
```

Un `KO` doit toujours montrer :

1. la requête concernée ;
2. la ou les étapes lourdes ;
3. la nature de la source ;
4. la preuve que l'étape est locale ou non repliable.

Sans cette preuve :

```text
NA
```

---

## 12. Résumé

```text
RÈGLE BP-04

POUR chaque requête M atteignable
    SI code absent / illisible
        -> NA

    RÉSOUDRE la source racine

    SI source inconnue ou circulaire
        -> NA

    CLASSER toutes les étapes M

    SI une étape nécessaire à la décision est UNKNOWN
        -> NA

    SI aucune étape lourde
        -> OK

    SINON
        DÉTERMINER le folding

        SI source non repliable
            -> KO

        SINON SI folding prouvé
            -> OK

        SINON SI non-folding prouvé
            -> KO

        SINON
            -> NA
FIN
```
