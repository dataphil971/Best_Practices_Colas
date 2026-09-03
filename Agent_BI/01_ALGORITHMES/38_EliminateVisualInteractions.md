# BP-38 — Éliminer les interactions croisées inutiles

> **Statut d'implémentation : ✅ Implémenté** — moteur : [`03_PYTHON/rules/bp_38.py`](../03_PYTHON/rules/bp_38.py), tests : `03_PYTHON/tests/test_bp_38.py`.

## 1. Objectif

Vérifier les interactions entre visuels sans supposer qu'une interaction est inutile simplement parce qu'elle existe ou parce qu'elle n'a pas été sérialisée dans `visualInteractions`.

Cette règle comporte deux dimensions :

1. **cohérence technique** des références d'interactions ;
2. **pertinence fonctionnelle** des interactions.

La première est déterministe.

La seconde nécessite une politique ou une revue contextuelle.

Statuts :

```text
OK / KO / NA
```

---

## 2. Source

```text
<REPORT_PATH>/definition/pages/<pageId>/page.json
<REPORT_PATH>/definition/pages/<pageId>/visuals/**/visual.json
```

Le contexte fournit :

```text
visual_index
visual_interactions
company_policy
interaction_review_results
report_coverage
```

---

## 3. Ce que `visualInteractions` prouve

Une entrée sérialisée permet d'observer :

```text
source
target
type
```

Elle constitue une preuve de configuration pour ce couple.

En revanche, l'absence d'une entrée ne doit pas être interprétée automatiquement comme :

```text
"cette interaction n'a jamais été revue"
```

ou :

```text
"cette interaction est active et inutile"
```

Le format sérialisé et le comportement par défaut peuvent évoluer selon la version.

---

## 4. Références d'interaction

Pour chaque entrée :

```text
source -> visuel existant sur la page
target -> visuel existant sur la page
```

Si la couverture de la page est complète et qu'une référence pointe vers un visuel inexistant :

```text
KO
```

Si la couverture est incomplète :

```text
NA
```

---

## 5. Type d'interaction

Le moteur conserve la valeur brute :

```text
DataFilter
Highlight
None
...
```

Un type non reconnu par le parser :

```text
NA
```

Il ne doit pas être transformé silencieusement en `DataFilter`.

---

## 6. Pertinence d'une interaction

Décisions contextuelles :

```text
KEEP
DISABLE
UNKNOWN
```

Une interaction ne peut être déclarée « inutile » que si :

- une `COMPANY_POLICY` définit une matrice attendue ;
- ou un reviewer contextuel/humain la qualifie explicitement.

Exemple de policy :

```yaml
bp_38:
  expected_interactions:
    - source: Slicer_Country
      target: KPI_Global
      type: None
```

---

## 7. Pages denses

Le nombre de visuels peut produire un diagnostic :

```text
analytical_visual_count
interaction_count
```

Mais :

```text
> 4 visuels
```

n'est pas un seuil universel.

Sans policy :

```text
page dense -> diagnostic uniquement
```

---

## 8. Présence d'une interaction `None`

Une entrée `type: None` prouve qu'un couple précis a été désactivé.

Elle ne prouve pas que :

```text
toutes les interactions de la page ont été revues
```

Par conséquent, la présence d'un seul `None` ne suffit pas à produire `OK` global.

---

## 9. Slicers

Le fait qu'un slicer ne figure pas dans `visualInteractions` ne constitue pas une anomalie.

Cela peut produire un candidat de revue si la policy l'exige, mais jamais `WARN` ou `KO` par défaut.

---

## 10. Décision

### Cohérence structurelle

| Situation | Statut |
|---|---|
| interaction référence des visuels existants | `OK` pour ce sous-contrôle |
| source/target inexistant avec couverture complète | `KO` |
| couverture incomplète | `NA` |

### Pertinence fonctionnelle

| Situation | Statut |
|---|---|
| interaction conforme à une matrice de policy | `OK` |
| interaction violant une matrice explicite | `KO` |
| interaction confirmée inutile par reviewer | `KO` |
| absence de policy/review | `NA` |

---

## 11. Pseudo-code

```python
def evaluate_interaction(
    interaction,
    page,
    context,
):
    source = context.visual_index.get(
        page.id,
        interaction.source,
    )

    target = context.visual_index.get(
        page.id,
        interaction.target,
    )

    if source is None or target is None:
        if context.report_coverage.is_complete(page.id):
            return finding_ko(
                object=interaction.id,
                reason="Interaction référence un visuel inexistant",
                evidence={
                    "source": interaction.source,
                    "target": interaction.target,
                },
            )

        return finding_na(
            object=interaction.id,
            reason="Référence d'interaction non résolue avec couverture incomplète",
        )

    if not context.interaction_schema.is_known_type(
        interaction.type
    ):
        return finding_na(
            object=interaction.id,
            reason="Type d'interaction non reconnu",
            evidence={
                "raw_type": interaction.type,
            },
        )

    policy_result = context.company_policy.evaluate_interaction(
        page=page,
        interaction=interaction,
    )

    if policy_result == "VIOLATION":
        return finding_ko(
            object=interaction.id,
            reason="Interaction contraire à la politique",
        )

    if policy_result == "COMPLIANT":
        return finding_ok(
            object=interaction.id,
        )

    review = context.interaction_reviews.get(
        interaction.id
    )

    if review is None:
        return finding_na(
            object=interaction.id,
            reason="Pertinence fonctionnelle non qualifiée",
        )

    if review.decision == "DISABLE":
        return finding_ko(
            object=interaction.id,
            reason="Interaction confirmée inutile",
            evidence=review.evidence,
        )

    if review.decision == "KEEP":
        return finding_ok(
            object=interaction.id,
            evidence=review.evidence,
        )

    return finding_na(
        object=interaction.id,
        reason="Décision d'interaction non résolue",
    )
```

---

## 12. Aucune entrée `visualInteractions`

Si aucune interaction explicite n'est sérialisée :

```text
rule_status = NA
```

sauf si une policy permet de déterminer la conformité à partir d'autres informations.

Le checker ne doit pas produire `KO` uniquement à cause de cette absence.

---

## 13. Statut global

```python
if any(r.status == "KO" for r in results):
    rule_status = "KO"

elif any(r.status == "NA" for r in results):
    rule_status = "NA"

elif results:
    rule_status = "OK"

else:
    rule_status = "NA"
```

---

## 14. Preuve obligatoire pour KO

### Référence cassée

```text
page
source
target
known_visual_ids
report_coverage_complete
source_file
```

### Interaction inutile

```text
source
target
type
decision_source = COMPANY_POLICY | REVIEW
decision_evidence
```

---

## 15. Résumé

```text
RÈGLE BP-38

LIRE les interactions explicites

POUR chaque interaction
    VALIDER source et target

    SI référence cassée prouvée
        -> KO

    SINON
        ÉVALUER policy / reviewer

        KEEP
            -> OK

        DISABLE
            -> KO

        UNKNOWN
            -> NA
FIN

SI aucune interaction explicite
    -> NA par défaut
```
