# BP-31 — Détection des patrons DAX à risque de performance

## 1. Objectif

Identifier des mesures candidates à un profilage de performance.

Cette règle ne doit pas prétendre qu'un pattern syntaxique prouve à lui seul une mauvaise performance réelle.

Statuts :

```text
OK / KO / NA
```

Pour cette règle, la distinction essentielle est :

```text
aucun pattern détecté -> OK
pattern(s) détecté(s), performance non mesurée -> NA + diagnostic
performance réellement mesurée au-delà d'un seuil défini -> KO
```

---

## 2. Sources

Statique :

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Optionnel pour produire un `KO` :

- Server Timings ;
- métriques DAX Studio ;
- requête de benchmark contrôlée ;
- métrique équivalente explicitement définie par l'entreprise.

---

## 3. Patterns statiques recherchés

Exemples :

- `FILTER` sur table physique complète ;
- `CALCULATE` directement imbriqué ;
- `EARLIER` / `EARLIEST` ;
- itérateur sur table de faits complète ;
- `CROSSFILTER(..., BOTH)`.

La présence d'un ou plusieurs patterns produit :

```json
{
  "rule_status": "NA",
  "diagnostic_level": "WARNING",
  "profiling_required": true
}
```

et jamais un `KO` arbitraire fondé sur le nombre de patterns.

---

## 4. Suppression de l'ancienne règle « 3 patterns = KO »

L'ancienne logique :

```python
status = "KO" if len(set(patterns_found)) >= 3 else "WARN"
```

est supprimée.

Trois heuristiques ne deviennent pas une preuve simplement parce qu'elles sont trois.

---

## 5. Analyse statique

```python
def static_dax_risk_analysis(measure, context):
    dax = strip_dax_comments(measure.expression)
    patterns = set()

    for call in find_function_calls(dax, "FILTER"):
        if is_table_level_filter(call, context.fact_tables):
            patterns.add("FILTER_ON_FULL_TABLE")

    if has_nested_calculate(dax):
        patterns.add("NESTED_CALCULATE")

    if contains_function_call(dax, "EARLIER"):
        patterns.add("EARLIER_USAGE")

    if contains_function_call(dax, "EARLIEST"):
        patterns.add("EARLIEST_USAGE")

    if iterator_targets_full_fact_table(dax, context.fact_tables):
        patterns.add("ITERATOR_ON_FULL_FACT_TABLE")

    if has_crossfilter_both(dax):
        patterns.add("CROSSFILTER_BOTH")

    return sorted(patterns)
```

---

## 6. Décision

```python
def evaluate_measure_performance(measure, context, cfg):
    patterns = static_dax_risk_analysis(measure, context)

    if not patterns:
        return finding_ok(
            object=measure.qualified_name,
            evidence={"patterns": []},
        )

    metrics = context.performance_metrics.get(measure.qualified_name)

    if metrics is None:
        return finding_na(
            object=measure.qualified_name,
            reason="Patterns à risque détectés mais performance réelle non mesurée",
            evidence={
                "patterns": patterns,
                "profiling_required": True,
            },
        )

    if metrics.duration_ms > cfg.MAX_DURATION_MS:
        return finding_ko(
            object=measure.qualified_name,
            observed=metrics.duration_ms,
            expected=f"<= {cfg.MAX_DURATION_MS} ms",
            evidence={
                "patterns": patterns,
                "metrics_source": metrics.source,
            },
        )

    return finding_ok(
        object=measure.qualified_name,
        observed=metrics.duration_ms,
        evidence={"patterns": patterns},
    )
```

---

## 7. Statut global

```text
au moins un KO mesuré -> KO
sinon au moins un candidat non profilé -> NA
sinon -> OK
```

Cette règle ne retourne jamais `KO` uniquement à partir d'une heuristique syntaxique.
