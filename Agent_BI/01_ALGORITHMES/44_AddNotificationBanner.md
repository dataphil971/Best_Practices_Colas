# BP-44 — Bandeau de notification piloté par configuration

## 1. Objectif

Vérifier la cohérence d'un mécanisme de notification utilisateur **lorsque ce mécanisme fait partie du contrat de gouvernance du projet**.

Contrairement à une fonctionnalité Power BI standard comme une relation ou un slicer, un bandeau alimenté par :

```text
T_NOTIFICATION
T_NOTIFICATION_TEXT
SharePoint
mesures DAX
textbox dynamique
```

est une architecture spécifique au projet ou à l'entreprise.

Le checker générique ne doit donc pas déduire l'existence d'un système de notification à partir de mots contenus dans des noms de tables ou de colonnes.

Statuts :

```text
OK / KO / NA
```

---

## 2. Contrat de notification

La règle doit recevoir un contrat explicite.

Exemple :

```yaml
bp_44:
  enabled: true

  content_source:
    table: T_NOTIFICATION_TEXT
    message_field: Message
    status_field: Status
    page_field: PageNb

  style_source:
    table: T_NOTIFICATION
    type_field: TYPE
    foreground_field: COLOR
    background_field: BACKGROUND_COLOR
    icon_field: ICON

  pages:
    mode: dynamic_by_page_field

  report_output:
    require_at_least_one_notification_visual: true
```

Le nom des tables n'est donc jamais hardcodé dans le checker.

---

## 3. Applicabilité

Valeurs :

```text
NOTIFICATION_REQUIRED
NOTIFICATION_NOT_REQUIRED
UNKNOWN
```

Décision :

```text
contract enabled=true  -> REQUIRED
contract enabled=false -> NOT_REQUIRED
contract absent         -> UNKNOWN
```

Sans contrat :

```text
NA
```

---

## 4. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<REPORT_PATH>/definition/pages/**/visual.json
```

Contexte runtime optionnel :

```text
notification_data
refresh_state
active_message_rows
```

---

## 5. Validation du modèle

Le moteur vérifie les objets définis par le contrat.

Exemple :

```python
def validate_notification_model(
    contract,
    context,
):
    required_fields = [
        (
            contract.content_source.table,
            contract.content_source.message_field,
        ),
        (
            contract.content_source.table,
            contract.content_source.status_field,
        ),
    ]

    if contract.content_source.page_field:
        required_fields.append(
            (
                contract.content_source.table,
                contract.content_source.page_field,
            )
        )

    return validate_model_objects(
        required_fields,
        context.model_object_index,
    )
```

Si un objet contractuel est absent et que la couverture du modèle est complète :

```text
KO
```

Si la couverture est incomplète :

```text
NA
```

---

## 6. Détection côté rapport

Le moteur ne cherche pas :

```text
notif
banner
message
```

dans les noms de visuels.

Il utilise le `usage_index`.

Un visuel de notification peut consommer :

- une colonne ;
- une mesure ;
- une expression de texte dynamique ;
- un champ indirect dépendant de la table de notification.

Le moteur doit donc suivre la lineage :

```text
notification source
-> measure
-> visual
```

---

## 7. Usage direct ou indirect

Exemple :

```text
T_NOTIFICATION_TEXT[Message]
-> [Current Notification]
-> Textbox dynamique
```

Le visuel ne référence pas nécessairement directement la table.

Pseudo-code :

```python
def notification_visual_usages(
    contract,
    context,
):
    source_objects = contract.notification_source_objects()

    impacted_measures = context.lineage.expand_downstream(
        source_objects,
        kinds={"MEASURE"},
    )

    report_objects = context.usage_index.report_usages_of(
        source_objects | impacted_measures
    )

    return report_objects
```

---

## 8. Validation statique

### Cas conforme

```text
contrat requis
+
objets modèle présents
+
usage rapport attendu présent
-> OK pour la cohérence structurelle
```

### Source contractuelle absente

```text
KO
```

### Aucun visuel consommateur alors que le contrat en impose un

```text
KO
```

### Lineage ou PBIR non résolvable

```text
NA
```

---

## 9. Statut runtime du message

La propriété :

```text
Status
```

est une donnée, pas une métadonnée TMDL.

Le checker statique ne peut pas conclure :

```text
message actif
message inactif
contenu correct
message à jour
```

sans accès aux données.

Valeurs :

```text
ACTIVE
INACTIVE
UNKNOWN
```

Sans data access :

```text
UNKNOWN
```

---

## 10. Couverture par page

Si le contrat impose un bandeau sur certaines pages :

```yaml
pages:
  required:
    - Overview
    - Adoption
```

le moteur doit vérifier que chaque page requise possède un usage compatible.

Si le contrat utilise un champ dynamique de page :

```text
PageNb
```

la présence d'un seul visuel peut être suffisante uniquement si la structure du rapport démontre que ce visuel existe sur toutes les pages concernées ou que le mécanisme de rendu couvre effectivement ces pages.

Le moteur ne doit pas supposer qu'un visuel présent sur une page est « global » à tout le rapport.

---

## 11. Décision

### Contrat absent

```text
NA
```

### Contrat désactivé

```text
NA / hors périmètre
```

### Contrat actif

| Situation | Statut |
|---|---|
| objets contractuels présents + sorties rapport requises présentes | `OK` |
| objet modèle requis absent, couverture complète | `KO` |
| sortie visuelle requise absente | `KO` |
| référence rapport cassée | `KO` |
| parsing/lineage incomplet | `NA` |
| statut runtime non disponible mais structure statique conforme | `OK` statique + diagnostic runtime `UNKNOWN` |

---

## 12. Pseudo-code

```python
def evaluate_bp44(
    context,
):
    contract = context.company_policy.notification_contract

    if contract is None:
        return rule_na(
            reason="Aucun contrat de notification configuré"
        )

    if not contract.enabled:
        return rule_na(
            reason="Mécanisme de notification non requis",
        )

    validation = validate_notification_model(
        contract,
        context,
    )

    if validation.has_missing_objects:
        if context.semantic_model_coverage_complete:
            return rule_ko(
                reason="Objet contractuel de notification absent",
                evidence={
                    "missing": validation.missing,
                },
            )

        return rule_na(
            reason="Objets de notification non résolus avec couverture incomplète",
        )

    usages = notification_visual_usages(
        contract,
        context,
    )

    if usages.unresolved:
        return rule_na(
            reason="Lineage notification -> rapport incomplète",
            evidence={
                "unresolved": usages.unresolved,
            },
        )

    coverage = evaluate_required_page_coverage(
        contract,
        usages,
        context,
    )

    if coverage.state == "NON_COMPLIANT":
        return rule_ko(
            reason="Couverture visuelle de notification incomplète",
            evidence=coverage.evidence,
        )

    if coverage.state == "UNKNOWN":
        return rule_na(
            reason="Couverture de notification non déterminable",
        )

    runtime = evaluate_notification_runtime(
        contract,
        context.data_access,
    )

    return rule_ok(
        evidence={
            "model_contract": validation.evidence,
            "report_usage": usages.evidence,
            "page_coverage": coverage.evidence,
            "runtime_status": runtime.state,
        },
        diagnostic_level=(
            "INFO"
            if runtime.state == "UNKNOWN"
            else None
        ),
    )
```

---

## 13. Détection heuristique interdite

Le checker ne doit pas faire :

```python
if "notif" in table.name.lower():
    notification_table = table
```

ni :

```python
if {"message", "status"} <= column_names:
    notification_table = table
```

Ces signaux peuvent servir à un outil de découverte ou à une proposition de configuration, mais pas au verdict.

---

## 14. Preuve obligatoire pour KO

### Objet contractuel manquant

```text
contract_id
expected_table
expected_field
model_coverage_complete
source_files
```

### Restitution absente

```text
contract_id
source_objects
lineage
required_pages
observed_visual_usages
report_coverage_complete
```

---

## 15. Exemple de résultat

```json
{
  "rule_id": "BP-44",
  "rule_status": "OK",
  "contract": "COLAS_NOTIFICATION_V1",
  "content_source": "T_NOTIFICATION_TEXT",
  "style_source": "T_NOTIFICATION",
  "displaying_visuals": [
    {
      "page": "Overview",
      "visual_id": "abc123"
    }
  ],
  "runtime_status": "UNKNOWN"
}
```

---

## 16. Résumé

```text
RÈGLE BP-44

CHARGER le contrat de notification

SI contrat absent
    -> NA

SI mécanisme non requis
    -> NA

VALIDER les tables / champs contractuels

SI objet requis absent
    -> KO

CONSTRUIRE la lineage
    source notification
    -> mesures
    -> visuels

SI sortie requise absente
    -> KO

SI lineage / parsing incomplet
    -> NA

SINON
    -> OK

STATUT runtime du message
    -> diagnostic séparé
```
