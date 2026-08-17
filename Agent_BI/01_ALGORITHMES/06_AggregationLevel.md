# BP-06 — Choisir le niveau d'agrégation adapté des tables de faits

## 1. Objectif

Vérifier que le grain d'une table de faits est cohérent avec le besoin d'analyse observable.

Cette règle ne doit **jamais inventer** une cardinalité, un `row_count`, un `distinct_count` ou un ratio lorsque ces données ne sont pas accessibles.

Statuts :

```text
OK / KO / NA
```

---

## 2. Entrées

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
<REPORT_PATH>/definition/pages/*/visuals/*/visual.json
```

Optionnel :

- statistiques VertiPaq ;
- échantillon de données fiable ;
- statistiques obtenues via XMLA ou une source explicitement accessible.

---

## 3. Identifier les tables de faits

La classification utilise un composant partagé (`table_role_index`) :

1. conventions projet si elles sont explicitement configurées ;
2. structure du graphe de relations ;
3. autres métadonnées disponibles.

La règle ne doit pas hardcoder `F_` comme vérité universelle.

---

## 4. Identifier une clé de grain candidate

Ordre de préférence :

1. métadonnée explicite de clé ;
2. colonnes participant aux relations et correspondant à la granularité observée ;
3. convention de nommage uniquement comme indice secondaire.

Si aucune clé de grain n'est identifiable de manière fiable :

```text
status = NA
```

---

## 5. Mesure du ratio

Le ratio n'est calculé que si les données nécessaires sont réellement disponibles :

```python
def compute_grain_ratio(rows, grain_key):
    if rows is None:
        return None

    values = [row[grain_key] for row in rows if grain_key in row]

    if not values:
        return None

    return len(set(values)) / len(values)
```

Résultat :

```json
{
  "ratio": 0.97,
  "ratio_source": "sampled"
}
```

ou :

```json
{
  "ratio": null,
  "ratio_source": "unavailable"
}
```

### Interdit

Le moteur ne doit jamais produire une valeur comme :

```python
0.95 if raw_grain else 0.30
```

Une heuristique structurelle n'est pas une mesure de cardinalité.

---

## 6. Pré-diagnostic sans accès aux données

Lorsque le ratio n'est pas mesurable, le moteur peut produire des indices :

- présence/absence de `Table.Group` ;
- présence/absence de `Table.Distinct` ;
- grain apparent de la partition ;
- usage ou non de la clé candidate dans les visuels ;
- nombre de relations ;
- présence de colonnes horodatées très fines.

Ces indices vont dans :

```json
{
  "diagnostic": {...},
  "rule_status": "NA"
}
```

Ils ne doivent jamais être convertis en ratio fictif.

---

## 7. Décision avec données disponibles

Configuration :

```text
RATIO_SUSPECT_THRESHOLD = 0.90
```

| Situation | Statut |
|---|---|
| aucune table de faits | `NA` |
| clé de grain non identifiable | `NA` |
| ratio non mesurable | `NA` |
| ratio élevé mais grain fin réellement exploité par le rapport | `OK` |
| ratio élevé et absence d'usage du grain fin démontrée | `KO` |
| ratio sous le seuil et aucun autre signal objectif | `OK` |

Un ratio élevé seul ne suffit pas à produire `KO`.

---

## 8. Pseudo-code

```python
def evaluate_fact_table(table, context, cfg):
    grain_key = identify_grain_key(table, context.relationships)

    if grain_key is None:
        return finding_na(
            table=table.name,
            reason="Clé de grain non identifiable de manière fiable",
        )

    ratio_info = get_measured_ratio(
        table=table,
        grain_key=grain_key,
        statistics=context.statistics,
        sample=context.samples.get(table.name),
    )

    if ratio_info.ratio is None:
        return finding_na(
            table=table.name,
            reason="Cardinalité réelle non accessible",
            evidence=build_structural_grain_diagnostic(table, context),
        )

    used_at_fine_grain = grain_key_used_in_report(
        table.name,
        grain_key,
        context.usage_index,
    )

    if ratio_info.ratio >= cfg.RATIO_SUSPECT_THRESHOLD and not used_at_fine_grain:
        return finding_ko(
            table=table.name,
            observed=ratio_info.ratio,
            expected=f"< {cfg.RATIO_SUSPECT_THRESHOLD} ou usage du grain fin démontré",
        )

    return finding_ok(
        table=table.name,
        observed=ratio_info.ratio,
    )
```

---

## 9. Preuve obligatoire

Un `KO` doit obligatoirement contenir :

- table ;
- clé de grain ;
- `row_count` ;
- `distinct_count` ;
- ratio ;
- origine des statistiques ;
- preuve d'absence d'usage du grain fin dans le périmètre analysé.

Sans ces éléments :

```text
NA
```
