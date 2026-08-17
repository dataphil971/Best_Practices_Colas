# BP-23 — Organisation des mesures et colonnes dans des dossiers d'affichage

## 1. Objectif

Vérifier que les éléments visibles destinés au volet des champs sont organisés dans des `displayFolder` valides et cohérents.

Statuts autorisés :

```text
OK / KO / NA
```

---

## 2. Source

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Pour chaque `measure` et `column`, lire :

- `isHidden` ;
- `displayFolder`.

---

## 3. Décision par élément

| Situation | Statut |
|---|---|
| élément masqué (`isHidden`) | `NA` |
| élément visible avec `displayFolder` non vide et valide | `OK` |
| élément visible sans `displayFolder` | `KO` |
| `displayFolder` vide | `KO` |
| séparateur mal formé (`\FILTERS`, `FILTERS\`, `FILTERS\\REMINDER`) | `KO` |
| variantes de casse créant plusieurs dossiers logiquement équivalents (`USAGE`, `Usage`, `usage`) dans le même périmètre | `KO` si l'incohérence est démontrée |
| structure non lisible | `NA` |

`WARN` n'est pas un statut de conformité Agent BI.

Une information non bloquante peut être ajoutée via :

```json
"diagnostic_level": "INFO"
```

sans modifier le statut.

---

## 4. Normalisation

```python
def normalize_folder(raw):
    if raw is None:
        return None
    return raw.strip()

def is_malformed_folder(folder):
    return (
        folder.startswith("\\")
        or folder.endswith("\\")
        or "\\\\" in folder
    )
```

La comparaison de cohérence de casse doit conserver la valeur brute comme preuve.

```python
canonical_key = folder.casefold()
```

Si plusieurs variantes brutes existent pour la même clé canonique dans un même espace logique :

```text
KO
```

---

## 5. Pseudo-code

```python
def evaluate_display_folders(tables):
    results = []
    variants = {}

    for table in tables:
        for element in [*table.measures, *table.columns]:
            if element.has_flag("isHidden"):
                results.append(na(element, "Élément masqué"))
                continue

            raw = element.get_property("displayFolder")
            folder = normalize_folder(raw)

            if not folder:
                results.append(ko(element, "displayFolder absent ou vide"))
                continue

            if is_malformed_folder(folder):
                results.append(ko(element, f"displayFolder mal formé: {raw!r}"))
                continue

            results.append(ok(element, observed=raw))
            variants.setdefault((table.name, folder.casefold()), set()).add(folder)

    for (table_name, _), raw_variants in variants.items():
        if len(raw_variants) > 1:
            mark_related_items_ko(
                results,
                table_name=table_name,
                reason=f"Incohérence de casse entre dossiers: {sorted(raw_variants)}",
            )

    return aggregate_ok_ko_na(results)
```

---

## 6. Statut global

```text
au moins un KO -> KO
sinon au moins un élément du périmètre NA et aucun élément évaluable -> NA
sinon -> OK
```
