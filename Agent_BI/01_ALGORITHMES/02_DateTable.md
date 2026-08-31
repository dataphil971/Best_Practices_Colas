# BP-02 — Table de dates dédiée et correctement configurée

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier qu'un modèle dispose d'une table de dates dédiée **lorsqu'une telle table est réellement requise**.

La règle doit éviter deux faux positifs majeurs :

1. conclure `KO` dans un modèle ne faisant aucune analyse temporelle ;
2. identifier une table de dates uniquement parce qu'elle s'appelle `D_DATE`, `Calendar` ou `Calendrier`.

Statuts :

```text
OK / KO / NA
```

---

## 2. Applicabilité

Valeurs :

```text
DATE_TABLE_REQUIRED
DATE_TABLE_NOT_REQUIRED
UNKNOWN
```

La requirement peut provenir de :

### Policy explicite

```yaml
bp_02:
  require_dedicated_date_table: true
```

### Usage temporel démontré

Exemples :

- fonctions DAX de time intelligence classique ;
- relations sur des colonnes temporelles utilisées dans le rapport ;
- policy de reporting imposant une dimension date.

Le backend doit utiliser un parseur DAX et un usage index.

---

## 3. Classic time intelligence vs calendar-based time intelligence

Power BI possède désormais plusieurs approches de time intelligence.

Le checker doit distinguer :

```text
CLASSIC_DATE_TABLE
CALENDAR_BASED_TIME_INTELLIGENCE
```

Si la policy impose explicitement :

```text
CLASSIC_DATE_TABLE
```

un calendar moderne n'est pas automatiquement considéré comme équivalent.

Si la policy autorise les deux :

```text
calendar valide -> peut satisfaire la requirement
```

---

## 4. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
```

Contexte :

```text
dax_ast
date_table_metadata
calendar_index
relationship_graph
column_statistics
usage_index
company_policy
```

---

## 5. Identification d'une date table

Le nom n'est qu'un diagnostic.

Preuves fortes possibles :

```text
marquage date table résolu par le parser TMDL/TOM
calendar object explicitement configuré
policy identifiant la table
métadonnée de gouvernance
```

Preuves secondaires :

```text
colonne Date/dateTime
one row per day
unique
no null
continuous date range
```

---

## 6. Résolution version-aware du marquage

Le checker ne doit pas rechercher naïvement une seule chaîne :

```text
isDateTable
```

dans le texte.

Le parser central expose :

```text
date_table_marking = MARKED | NOT_MARKED | UNKNOWN
```

selon le contrat TMDL/TOM applicable.

Pseudo-code :

```python
marking = context.date_table_metadata.get_marking(
    table.name
)
```

---

## 7. Colonne de date principale

Une candidate doit avoir une colonne temporelle résolue.

Valeurs :

```text
DATE_COLUMN_CONFIRMED
DATE_COLUMN_UNKNOWN
```

La colonne peut être déterminée par :

- métadonnée de date table ;
- calendar primary column ;
- policy ;
- analyse de données complète.

Le checker ne doit pas choisir automatiquement :

```text
la première colonne dateTime
```

s'il existe plusieurs colonnes temporelles.

---

## 8. Validation des données

Lorsque la règle dépend d'une table de dates classique, la colonne principale doit pouvoir être validée sur les critères applicables :

```text
valeurs uniques
pas de null
dates continues
timestamps cohérents si DateTime
```

Niveaux de preuve :

```text
FULL_DATA
DERIVED_FROM_CALENDAR_EXPRESSION
SAMPLE
NONE
```

Un échantillon ne peut pas prouver une continuité exhaustive.

Par défaut :

```text
SAMPLE -> NA
```

---

## 9. `formatString`

Le `formatString` est une propriété de présentation.

Son absence n'empêche pas une colonne d'être une date valide.

Donc :

```text
formatString absent -> pas de KO BP-02
```

Il peut être signalé par une autre règle de présentation.

---

## 10. `summarizeBy`

Le contrôle :

```text
summarizeBy: none
```

appartient déjà à BP-22.

BP-02 ne doit pas produire un second `KO` pour cette propriété.

Elle peut simplement référencer :

```text
related_rule = BP-22
```

---

## 11. Relation / usage de la date table

Si la policy exige que la date table filtre les faits :

```text
au moins une relation pertinente attendue
```

Le rôle des tables reliées doit provenir du `table_role_index` / graphe, pas de préfixes `F_`.

Une relation inactive peut être valide si elle est utilisée via `USERELATIONSHIP`.

---

## 12. Décision

### Requirement = `DATE_TABLE_NOT_REQUIRED`

```text
NA / OUT_OF_SCOPE
```

### Requirement = `UNKNOWN`

```text
NA
```

### Requirement = `DATE_TABLE_REQUIRED`

| Situation | Statut |
|---|---|
| aucune date table candidate fiable | `KO` |
| candidate mais marquage requis absent | `KO` |
| marquage inconnu | `NA` |
| colonne principale absente | `KO` |
| données invalides démontrées | `KO` |
| validation data impossible alors qu'elle est requise | `NA` |
| relation requise absente | `KO` |
| tous contrôles requis satisfaits | `OK` |

---

## 13. Pseudo-code

```python
def determine_requirement(
    context,
):
    explicit = context.company_policy.bp02_requirement

    if explicit is not None:
        return explicit

    if context.dax_ast.uses_classic_time_intelligence:
        return "DATE_TABLE_REQUIRED"

    if context.calendar_index.has_calendar_based_time_intelligence:
        if context.company_policy.bp02_calendar_based_allowed:
            return "DATE_TABLE_NOT_REQUIRED"

    return "UNKNOWN"
```

```python
def evaluate_date_table(
    context,
):
    requirement = determine_requirement(
        context
    )

    if requirement == "DATE_TABLE_NOT_REQUIRED":
        return rule_na(
            reason="Table de dates dédiée non requise",
        )

    if requirement == "UNKNOWN":
        return rule_na(
            reason="Besoin de table de dates non démontré",
        )

    candidates = context.date_table_metadata.candidates()

    if not candidates:
        return rule_ko(
            reason="Aucune table de dates candidate fiable"
        )

    results = []

    for table in candidates:
        marking = context.date_table_metadata.get_marking(
            table.name
        )

        if context.company_policy.bp02_require_marking:
            if marking == "NOT_MARKED":
                results.append(
                    finding_ko(
                        object=table.name,
                        reason="Table de dates non marquée",
                    )
                )
                continue

            if marking == "UNKNOWN":
                results.append(
                    finding_na(
                        object=table.name,
                        reason="Marquage date table non résolu",
                    )
                )
                continue

        date_column = context.date_table_metadata.primary_date_column(
            table.name
        )

        if date_column is None:
            results.append(
                finding_ko(
                    object=table.name,
                    reason="Colonne de date principale introuvable",
                )
            )
            continue

        validation = context.date_column_validation.get(
            table.name,
            date_column.name,
        )

        if validation.state == "INVALID":
            results.append(
                finding_ko(
                    object=f"{table.name}[{date_column.name}]",
                    reason="Colonne de date invalide",
                    evidence=validation.evidence,
                )
            )
            continue

        if validation.state == "UNKNOWN":
            results.append(
                finding_na(
                    object=f"{table.name}[{date_column.name}]",
                    reason="Validation exhaustive de la colonne date indisponible",
                )
            )
            continue

        if context.company_policy.bp02_require_relationship:
            usage = context.relationship_graph.date_table_usage(
                table.name
            )

            if usage.state == "NOT_USED":
                results.append(
                    finding_ko(
                        object=table.name,
                        reason="Table de dates requise mais non reliée aux tables analytiques attendues",
                    )
                )
                continue

            if usage.state == "UNKNOWN":
                results.append(
                    finding_na(
                        object=table.name,
                        reason="Usage relationnel de la table de dates non résolu",
                    )
                )
                continue

        results.append(
            finding_ok(
                object=table.name,
                evidence={
                    "primary_date_column": date_column.name,
                    "marking": marking,
                    "validation": validation.evidence,
                },
            )
        )

    return aggregate_candidate_date_tables(
        results
    )
```

---

## 14. Plusieurs tables de dates

Plusieurs date tables peuvent être légitimes.

Le checker ne doit pas :

```text
prendre celle avec le plus de relations
```

et ignorer les autres.

La policy peut définir :

```text
single_shared_date_dimension
multiple_role_playing_date_dimensions
calendar-based architecture
```

Sans policy permettant de choisir :

```text
NA
```

si plusieurs candidates incompatibles empêchent une conclusion fiable.

---

## 15. Statut global

```text
KO si une exigence obligatoire est violée
NA si la conclusion dépend d'une preuve indisponible
OK si la requirement est démontrée et entièrement satisfaite
```

Aucun quatrième statut.

---

## 16. Preuve obligatoire

Pour `KO` :

```text
requirement
requirement_source
table candidate(s)
marking state
primary date column
validation evidence
relationship/usage evidence si requis
source files
```

---

## 17. Références techniques

Les exigences de date table dépendent du mode de time intelligence utilisé.

Pour la time intelligence classique, la date table doit respecter les conditions de validité de la colonne date ; Power BI propose également des calendriers pour la time intelligence basée sur calendar.

---

## 18. Résumé

```text
RÈGLE BP-02

DÉTERMINER si une date table est requise

NOT_REQUIRED
    -> NA

UNKNOWN
    -> NA

REQUIRED
    IDENTIFIER une candidate fiable

    SI aucune
        -> KO

    VÉRIFIER marquage si requis
    VÉRIFIER colonne de date principale
    VÉRIFIER validité des données
    VÉRIFIER relation/usage si requis

    violation démontrée
        -> KO

    preuve insuffisante
        -> NA

    tout conforme
        -> OK
```
