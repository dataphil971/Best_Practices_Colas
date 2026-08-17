# BP-37 — Organiser les visuels et les signets

## 1. Objectif

Vérifier que l'organisation des visuels et des signets respecte une politique de maintenabilité explicite, sans transformer des choix de conception en non-conformités automatiques.

Cette règle doit distinguer :

```text
structure objectivement invalide
noms explicitement interdits par une politique
opportunité de regroupement
```

Statuts autorisés :

```text
OK / KO / NA
```

Les recommandations d'organisation sont exposées séparément via :

```text
diagnostic_level
```

---

## 2. Sources

```text
<REPORT_PATH>/definition/pages/**/visual.json
<REPORT_PATH>/definition/bookmarks/bookmarks.json
<REPORT_PATH>/definition/bookmarks/*.bookmark.json
```

Le moteur consomme le `AnalysisContext` :

```text
report_pages
visual_index
visual_group_index
bookmark_index
bookmark_hierarchy
company_policy
```

---

## 3. Groupes de visuels

Un groupe de visuels peut être identifié structurellement par la présence de :

```json
{
  "visualGroup": {
    "displayName": "..."
  }
}
```

Les membres peuvent référencer le groupe via :

```text
parentGroupName
```

Le checker doit vérifier la cohérence des références :

```text
parentGroupName -> groupe existant sur la page
```

Si le rapport est complètement parsé et qu'un visuel référence un groupe inexistant :

```text
KO
```

Si la couverture du rapport est incomplète :

```text
NA
```

---

## 4. Nommage des groupes

La qualité sémantique d'un nom n'est pas déterminable de manière générique.

Un nom tel que :

```text
Group1
Group 2
```

peut être identifié comme nom par défaut uniquement si le projet dispose :

- d'une liste de motifs validés ;
- d'une politique d'entreprise ;
- ou d'un contrat associé à la version de Power BI utilisée.

Exemple :

```yaml
bp_37:
  forbidden_default_names:
    visual_group:
      - "^Group\\s*\\d*$"
```

Sans cette configuration :

```text
nom présent mais qualité inconnue -> NA / diagnostic
```

Une valeur `displayName` vide alors que la politique exige un nom explicite peut produire :

```text
KO
```

---

## 5. Visuels non groupés

L'absence de groupe n'est pas une non-conformité automatique.

Une page peut volontairement contenir :

- quelques visuels indépendants ;
- une mise en page simple ;
- des objets décoratifs ;
- des visuels dont le regroupement n'apporte aucune valeur.

Donc :

```text
nombre de visuels non groupés > 5
```

ne doit jamais produire `WARN`, `KO` ou modifier `rule_status` par défaut.

Le moteur peut produire un candidat :

```json
{
  "diagnostic_type": "UNGROUPED_VISUALS",
  "page": "Overview",
  "count": 8
}
```

La recommandation éventuelle relève d'une policy ou d'une revue contextuelle.

---

## 6. Signets

Le moteur doit construire la hiérarchie des signets à partir de :

```text
bookmarks.json
*.bookmark.json
```

Il vérifie :

1. la validité des identifiants ;
2. l'absence de références cassées ;
3. les cycles éventuels ;
4. la cohérence entre métadonnées et fichiers présents.

---

## 7. Références de signets invalides

Si `bookmarks.json` référence un identifiant qui ne correspond à aucun signet ou groupe connu, et que la couverture est complète :

```text
KO
```

Si `bookmarks.json` est absent ou illisible alors que des fichiers de signets existent :

```text
NA
```

Le moteur ne doit pas supposer la hiérarchie.

---

## 8. Signet non référencé dans la hiérarchie

Un fichier de signet non retrouvé dans la hiérarchie peut être :

- un reste obsolète ;
- un format/version PBIR différent ;
- un cas de sérialisation non couvert.

Par défaut :

```text
NA + diagnostic
```

Il ne devient `KO` que si une policy ou un contrat de schéma applicable garantit qu'il doit obligatoirement être référencé dans la hiérarchie.

---

## 9. Nommage des signets

La détection de noms comme :

```text
Bookmark 1
Bookmark 2
```

est pilotée par configuration.

```python
def is_forbidden_name(
    display_name,
    kind,
    policy,
):
    patterns = policy.forbidden_default_names.get(
        kind,
        []
    )

    return any(
        pattern.fullmatch(display_name or "")
        for pattern in patterns
    )
```

Sans motifs configurés :

```text
NA / diagnostic
```

---

## 10. Décision

### Éléments structurels

| Situation | Statut |
|---|---|
| `parentGroupName` pointe vers un groupe inexistant, couverture complète | `KO` |
| signet/groupe référencé mais inexistant, couverture complète | `KO` |
| cycle de hiérarchie démontré | `KO` |
| structure illisible/incomplète | `NA` |
| structure cohérente | `OK` pour le sous-contrôle structurel |

### Organisation / nommage

| Situation | Statut |
|---|---|
| nom interdit par `COMPANY_POLICY` | `KO` |
| nom conforme à la policy | `OK` |
| aucune policy de nommage | `NA` |
| visuels non groupés sans obligation explicite | `NA` + diagnostic |

---

## 11. Pseudo-code

```python
def evaluate_bp37(
    report,
    context,
):
    results = []

    for visual in report.visuals:
        if not visual.parent_group_name:
            continue

        group = context.visual_group_index.resolve(
            visual.page_id,
            visual.parent_group_name,
        )

        if group is None:
            if context.report_coverage_complete:
                results.append(
                    finding_ko(
                        object=visual.id,
                        reason="parentGroupName référence un groupe inexistant",
                    )
                )
            else:
                results.append(
                    finding_na(
                        object=visual.id,
                        reason="Groupe parent non résolu avec couverture incomplète",
                    )
                )

    bookmark_validation = validate_bookmark_hierarchy(
        context.bookmark_hierarchy,
        context.bookmark_index,
    )

    results.extend(
        bookmark_validation.findings
    )

    policy = context.company_policy.bp37

    for group in report.visual_groups:
        if policy and policy.forbidden_default_names:
            if is_forbidden_name(
                group.display_name,
                "visual_group",
                policy,
            ):
                results.append(
                    finding_ko(
                        object=group.id,
                        reason="Nom de groupe interdit par la politique",
                    )
                )
            else:
                results.append(
                    finding_ok(
                        object=group.id,
                    )
                )

    for bookmark in context.bookmark_index.all():
        if policy and policy.forbidden_default_names:
            if is_forbidden_name(
                bookmark.display_name,
                "bookmark",
                policy,
            ):
                results.append(
                    finding_ko(
                        object=bookmark.id,
                        reason="Nom de signet interdit par la politique",
                    )
                )

    diagnostics = build_ungrouped_visual_diagnostics(
        report
    )

    return aggregate_bp37(
        results=results,
        diagnostics=diagnostics,
    )
```

---

## 12. Statut global

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

Une simple recommandation de regroupement ne modifie jamais ce statut.

---

## 13. Preuve obligatoire pour KO

```text
object_type
object_id
page
expected
actual
policy_id / schema_contract si applicable
source_file
evidence
```

---

## 14. Résumé

```text
RÈGLE BP-37

VALIDER les groupes et références
VALIDER la hiérarchie des signets

SI référence cassée démontrée
    -> KO

POUR le nommage
    SI policy explicite
        nom interdit -> KO
        nom conforme -> OK
    SINON
        -> NA

VISUELS non groupés
    -> diagnostic uniquement
```
