# BP-18 — Éviter les slicers à cardinalité excessive

## 1. Objectif

Vérifier qu'un champ utilisé dans un slicer de type liste / dropdown ne dépasse pas une limite de cardinalité **explicitement définie par la politique d'audit**.

Le checker ne doit pas inventer un seuil universel tel que :

```text
50 valeurs
20 % du nombre de lignes
```

Ces valeurs peuvent être utiles pour un diagnostic local, mais elles ne constituent pas une règle universelle de Power BI.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<REPORT_PATH>/definition/pages/**/visual.json
```

Contexte statistique :

```text
distinct_count
row_count (optionnel)
```

Politique :

```text
MAX_SLICER_DISTINCT_VALUES
```

Le seuil doit être fourni par :

```text
COMPANY_POLICY
```

ou une configuration explicite de la règle.

---

## 3. Périmètre des slicers

La règle porte principalement sur les slicers qui matérialisent un ensemble de valeurs discrètes :

```text
List
Dropdown
Basic
```

Les modes comme :

```text
Between
Relative date
Relative time
```

sont hors périmètre de ce contrôle de longueur de liste.

Ils sont classés :

```text
NA / OUT_OF_SCOPE
```

---

## 4. Extraction des champs

Le moteur doit utiliser un parseur PBIR structuré / tolérant aux versions.

Pseudo-code :

```python
def extract_slicer_fields(
    visual,
    context,
):
    if visual.visual_type != "slicer":
        return []

    return context.pbir_field_resolver.resolve_visual_fields(
        visual
    )
```

Une référence non résolue :

```text
NA
```

et jamais `OK`.

---

## 5. Cardinalité

La statistique décisionnelle principale est :

```text
distinct_count
```

Le ratio :

```text
distinct_count / row_count
```

peut être conservé comme diagnostic, mais ne doit pas produire `KO` par défaut.

Exemple :

```text
40 valeurs distinctes sur 40 lignes
```

donne un ratio de 1, mais ne prouve pas qu'une liste de 40 valeurs dépasse la politique UX.

---

## 6. Seuil

```python
threshold = context.company_policy.max_slicer_distinct_values
```

Si aucun seuil n'est configuré :

```text
NA
```

avec éventuellement :

```text
diagnostic_level = INFO
```

Le checker ne doit pas utiliser silencieusement une valeur par défaut.

---

## 7. Décision

| Situation | Statut |
|---|---|
| slicer liste/dropdown + cardinalité disponible + seuil configuré + `distinct_count <= threshold` | `OK` |
| slicer liste/dropdown + cardinalité disponible + seuil configuré + `distinct_count > threshold` | `KO` |
| seuil non configuré | `NA` |
| cardinalité non disponible | `NA` |
| champ non résolvable | `NA` |
| slicer en mode plage / relatif | `NA` hors périmètre |
| aucun slicer liste/dropdown | `NA` |

---

## 8. Pseudo-code

```python
def evaluate_slicer_field(
    field,
    usages,
    context,
):
    threshold = (
        context.company_policy
        .max_slicer_distinct_values
    )

    if threshold is None:
        return finding_na(
            object=field.qualified_name,
            reason="Seuil de cardinalité slicer non configuré",
        )

    stats = context.column_statistics.get(
        field.key
    )

    if stats is None:
        return finding_na(
            object=field.qualified_name,
            reason="Cardinalité non disponible",
        )

    if stats.distinct_count is None:
        return finding_na(
            object=field.qualified_name,
            reason="distinct_count non disponible",
        )

    evidence = {
        "distinct_count": stats.distinct_count,
        "threshold": threshold,
        "slicer_usages": usages,
    }

    if stats.row_count is not None and stats.row_count > 0:
        evidence["cardinality_ratio"] = (
            stats.distinct_count / stats.row_count
        )

    if stats.distinct_count > threshold:
        return finding_ko(
            object=field.qualified_name,
            expected=f"distinct_count <= {threshold}",
            actual=stats.distinct_count,
            evidence=evidence,
        )

    return finding_ok(
        object=field.qualified_name,
        expected=f"distinct_count <= {threshold}",
        actual=stats.distinct_count,
        evidence=evidence,
    )
```

---

## 9. Slicers synchronisés / dupliqués

Un même champ peut être utilisé dans plusieurs slicers.

Le verdict doit être calculé une seule fois par :

```text
(table, column, policy_scope)
```

et les différentes occurrences doivent être conservées comme preuves.

```python
usage_index[field].append({
    "page": page.name,
    "visual_id": visual.id,
    "mode": visual.slicer_mode,
})
```

---

## 10. Visuels masqués

Un slicer masqué n'est pas automatiquement actif dans l'expérience courante.

Le moteur peut le conserver dans l'inventaire, mais doit distinguer :

```text
active_visible_usage
hidden_usage
```

Une politique entreprise peut décider d'inclure ou non les visuels masqués.

Sans politique :

```text
hidden-only slicer -> NA + diagnostic
```

plutôt que `KO` automatique.

---

## 11. Statut global

Les slicers hors périmètre ne comptent pas.

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

## 12. Preuve obligatoire

Un `KO` doit contenir :

```text
table
column
slicer_mode
distinct_count
threshold
threshold_source
page / visual usages
evidence
```

Sans seuil explicite ou sans cardinalité :

```text
NA
```

---

## 13. Résumé

```text
RÈGLE BP-18

DÉTECTER les slicers liste/dropdown

POUR chaque champ utilisé
    SI champ non résolu
        -> NA

    SI seuil entreprise absent
        -> NA

    SI cardinalité absente
        -> NA

    SI distinct_count > seuil
        -> KO
    SINON
        -> OK
FIN
```

Le ratio de cardinalité reste un diagnostic et non un seuil universel.
