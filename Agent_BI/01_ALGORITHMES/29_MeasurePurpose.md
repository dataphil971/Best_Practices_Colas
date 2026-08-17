# BP-29 — Documentation systématique de l'objectif métier de chaque mesure

## 1. Objectif

Vérifier que chaque mesure **visible** dispose d'une documentation exploitable.

Statuts :

```text
OK / KO / NA
```

---

## 2. Source

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Documentation reconnue :

- commentaires `///` consécutifs immédiatement au-dessus de la mesure ;
- propriété `description`.

---

## 3. Périmètre

### Mesure visible

La documentation est obligatoire.

### Mesure masquée / purement technique

Elle est hors du périmètre utilisateur de cette bonne pratique :

```text
NA
```

Une recommandation de documentation peut être ajoutée comme diagnostic, sans créer un statut `WARN`.

---

## 4. Validation de la présence

```python
PLACEHOLDERS = {
    "todo",
    "tbd",
    "n/a",
    "na",
    "kpi",
    "mesure",
    "measure",
}

def is_non_empty_description(text, min_length=15):
    if text is None:
        return False

    normalized = " ".join(text.split())

    if len(normalized) < min_length:
        return False

    if normalized.casefold() in PLACEHOLDERS:
        return False

    return True
```

Ce contrôle est **syntaxique** : il prouve qu'une documentation minimale est présente, pas qu'elle est sémantiquement excellente.

La qualité sémantique éventuelle de la description appartient au futur `Context Reviewer` et ne modifie pas automatiquement le verdict de cette règle déterministe.

---

## 5. Décision

| Situation | Statut |
|---|---|
| mesure visible avec description minimale exploitable | `OK` |
| mesure visible sans description | `KO` |
| mesure visible avec placeholder / description vide | `KO` |
| mesure masquée | `NA` |
| bloc de mesure illisible | `NA` |
| aucune mesure dans le modèle | `NA` |

---

## 6. Pseudo-code

```python
def evaluate_measure_documentation(tables):
    results = []

    for table in tables:
        raw_lines = table.raw_lines

        for measure in table.measures:
            if measure.has_flag("isHidden"):
                results.append(
                    finding_na(
                        object=f"{table.name}[{measure.name}]",
                        reason="Mesure masquée : hors périmètre utilisateur",
                        diagnostic="Documentation recommandée pour la maintenance",
                    )
                )
                continue

            description = get_measure_description(measure, raw_lines)

            if is_non_empty_description(description):
                results.append(
                    finding_ok(
                        object=f"{table.name}[{measure.name}]",
                        observed=description,
                    )
                )
            else:
                results.append(
                    finding_ko(
                        object=f"{table.name}[{measure.name}]",
                        expected="Description /// ou description: exploitable",
                        observed=description,
                    )
                )

    if not results:
        return rule_na("Aucune mesure")

    return aggregate_ok_ko_na(results)
```

---

## 7. Important

Cette règle ne doit pas utiliser un LLM pour décider si une description « semble bonne ».

Le checker détermine seulement :

```text
documentation minimale présente -> OK
documentation minimale absente/invalide -> KO
non évaluable / hors périmètre -> NA
```

Un futur skill contextuel pourra produire un conseil séparé sur la qualité rédactionnelle.
