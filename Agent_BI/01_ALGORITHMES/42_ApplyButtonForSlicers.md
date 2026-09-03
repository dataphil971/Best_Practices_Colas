# BP-42 — Utiliser un mécanisme d'application différée des slicers lorsque nécessaire

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier qu'une page utilise un mécanisme de réduction des requêtes liées aux slicers **lorsque ce mécanisme est explicitement requis** par la politique du projet ou par une preuve de performance.

La règle ne doit pas conclure qu'une page est non conforme uniquement parce qu'elle contient :

```text
4 slicers
5 slicers
ou tout autre nombre arbitraire
```

Le nombre de slicers est un signal de diagnostic, pas une preuve de besoin.

Statuts :

```text
OK / KO / NA
```

---

## 2. Fonctionnalités Power BI concernées

Power BI propose plusieurs mécanismes liés à l'application différée des filtres/slicers.

### 2.1 Apply all slicers

Un bouton :

```text
Apply all slicers
```

permet à l'utilisateur de modifier plusieurs slicers puis d'appliquer les changements en une seule fois.

Ce bouton agit sur les slicers de la page.

### 2.2 Apply sur les slicers

Les options d'optimisation de Power BI peuvent également configurer les slicers pour attendre une validation explicite avant d'envoyer les requêtes.

Le checker doit donc raisonner en termes de :

```text
QUERY_REDUCTION_MECHANISM
```

et non supposer une propriété unique appelée :

```text
isApplyModeEnabled
```

---

## 3. Sources

```text
<REPORT_PATH>/definition/pages/**/visual.json
<REPORT_PATH>/definition/pages/**/page.json
<REPORT_PATH>/definition/report.json
```

Contexte optionnel :

```text
performance_evidence
company_policy
pbir_schema_contract
button_action_index
slicer_query_reduction_index
```

---

## 4. Applicabilité

Valeurs :

```text
APPLY_MODE_REQUIRED
APPLY_MODE_NOT_REQUIRED
UNKNOWN
```

La décision peut provenir de :

### Politique explicite

Exemple :

```yaml
bp_42:
  pages:
    Adoption:
      require_query_reduction_for_slicers: true
```

### Preuve de performance

Exemple :

```text
Performance Analyzer
DirectQuery
nombre élevé de requêtes de visuels
temps d'attente utilisateur mesuré
```

Le simple nombre de slicers ne suffit pas.

---

## 5. Détection des mécanismes

Valeurs :

```text
APPLY_ALL_SLICERS
PER_SLICER_APPLY
NONE_CONFIRMED
UNKNOWN
```

Le backend doit utiliser un parseur PBIR/schema-aware.

Il ne doit pas faire :

```python
if "apply" in property_name.lower():
    ...
```

car une propriété contenant le mot `apply` peut avoir une autre sémantique.

---

## 6. Apply all slicers

Un bouton de type :

```text
Apply all slicers
```

doit être identifié à partir de la configuration d'action du bouton selon le contrat PBIR applicable.

Pseudo-code conceptuel :

```python
def detect_apply_all_slicers_button(
    page,
    context,
):
    buttons = context.button_action_index.for_page(
        page.id
    )

    matches = [
        button
        for button in buttons
        if button.action_kind == "APPLY_ALL_SLICERS"
    ]

    return matches
```

Si le parseur ne sait pas identifier l'action de manière fiable :

```text
UNKNOWN
```

---

## 7. Apply individuel des slicers

Si la version Power BI/PBIR analysée sérialise un mode Apply sur les slicers, le backend peut l'exploiter seulement si :

```text
schema_contract.supported = true
```

Sans contrat fiable :

```text
UNKNOWN
```

Le moteur ne doit pas traiter l'absence d'une propriété inconnue comme :

```text
mode instantané prouvé
```

---

## 8. Visibilité du bouton

Un bouton Apply all slicers masqué peut ne pas contrôler les slicers comme lorsqu'il est visible.

Le moteur doit donc tenir compte de l'état effectif du bouton lorsque cette information est disponible :

```text
VISIBLE
HIDDEN
UNKNOWN
```

Si l'état effectif dépend de bookmarks et ne peut pas être résolu statiquement :

```text
NA
```

pour la partie correspondante.

---

## 9. Décision

### Requirement = `APPLY_MODE_REQUIRED`

| Mécanisme observé | Statut |
|---|---|
| Apply all slicers actif démontré | `OK` |
| Apply individuel conforme démontré | `OK` |
| absence de mécanisme démontrée avec contrat complet | `KO` |
| état/mécanisme non déterminable | `NA` |

### Requirement = `APPLY_MODE_NOT_REQUIRED`

```text
NA / hors périmètre
```

### Requirement = `UNKNOWN`

```text
NA
```

---

## 10. Pseudo-code

```python
def evaluate_page(
    page,
    context,
):
    requirement = context.bp42_requirement.get(
        page.id,
        "UNKNOWN",
    )

    if requirement == "APPLY_MODE_NOT_REQUIRED":
        return finding_na(
            object=page.id,
            reason="Application différée non requise",
            reason_code="OUT_OF_SCOPE",
        )

    if requirement == "UNKNOWN":
        return finding_na(
            object=page.id,
            reason="Besoin d'application différée non démontré",
            diagnostics={
                "slicer_count": context.slicer_index.count_for_page(
                    page.id
                ),
            },
        )

    apply_all = detect_apply_all_slicers_button(
        page,
        context,
    )

    per_slicer = context.slicer_query_reduction_index.get(
        page.id
    )

    if apply_all.state == "ACTIVE_CONFIRMED":
        return finding_ok(
            object=page.id,
            evidence={
                "mechanism": "APPLY_ALL_SLICERS",
                "buttons": apply_all.buttons,
            },
        )

    if per_slicer.state == "ACTIVE_CONFIRMED":
        return finding_ok(
            object=page.id,
            evidence={
                "mechanism": "PER_SLICER_APPLY",
                "slicers": per_slicer.slicers,
            },
        )

    if (
        apply_all.state == "ABSENT_CONFIRMED"
        and per_slicer.state == "ABSENT_CONFIRMED"
    ):
        return finding_ko(
            object=page.id,
            expected="mécanisme d'application différée",
            actual="aucun mécanisme détecté",
            evidence={
                "requirement": "APPLY_MODE_REQUIRED",
            },
        )

    return finding_na(
        object=page.id,
        reason="État du mécanisme Apply non déterminable",
    )
```

---

## 11. Statut global

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

## 12. Diagnostic de volumétrie

Le moteur peut conserver :

```text
slicer_count
visual_count
storage_mode
measured_query_count
measured_duration
```

mais ces informations ne deviennent décisionnelles que si une policy le précise.

---

## 13. Preuve obligatoire pour KO

```text
page
requirement = APPLY_MODE_REQUIRED
requirement_source
slicer_count
pbir_schema_version
apply_all_state = ABSENT_CONFIRMED
per_slicer_apply_state = ABSENT_CONFIRMED
coverage_complete
evidence
```

Sans preuve complète :

```text
NA
```

---

## 14. Références techniques

Microsoft documente :

- le bouton `Apply all slicers`, qui permet d'appliquer plusieurs sélections en une seule fois ;
- les options d'optimisation permettant d'ajouter des boutons Apply aux slicers ;
- l'objectif de réduction des requêtes de visuels.

La règle Agent BI doit donc reconnaître plusieurs mécanismes possibles et rester schema-aware.

---

## 15. Résumé

```text
RÈGLE BP-42

DÉTERMINER si l'application différée est requise

SI besoin inconnu
    -> NA

SI non requise
    -> NA

SI requise
    RECHERCHER :
        Apply all slicers
        OU Apply individuel

    SI mécanisme actif démontré
        -> OK

    SI absence démontrée avec couverture complète
        -> KO

    SINON
        -> NA
```
