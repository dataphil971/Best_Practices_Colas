# BP-02 (alias SEM-002) — Table de dates dédiée, marquée et correctement configurée

## 1. Objectif de la bonne pratique

Un modèle Power BI qui exploite la time intelligence (`TOTALYTD`, `SAMEPERIODLASTYEAR`, comparaisons N/N-1, dérives de dates relatives, etc.) doit s'appuyer sur une **table de dates dédiée**, physiquement présente dans le modèle, **marquée comme table de dates** (`isDateTable` / marquage via `Mark as date table`) et **reliée aux tables de faits** par une clé de date.

L'agent doit vérifier deux volets complémentaires :

1. **Existence et statut de la table** : une table candidate à un rôle de dimension date existe, est correctement marquée, contient une colonne clé de type date/heure continue et sans trou, et est reliée à au moins une table de faits.
2. **Configuration de la colonne clé de date** : la colonne servant de clé (généralement nommée `DATE`) respecte un typage et un format cohérents avec un usage de time intelligence.

La règle doit être générique et fonctionner indépendamment :

- du nom exact du rapport ou du modèle ;
- du nom réel donné à la table de dates (`D_DATES`, `D_DATE`, `DimDate`, `Calendar`, `Calendrier`...) ;
- du nombre de tables de faits reliées à cette dimension ;
- de l'ordre des propriétés dans les fichiers TMDL ;
- du fait que la table soit visible ou masquée dans le volet des champs.

---

## 2. Emplacement du modèle sémantique

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\
AI_BAROMETER_BI-CDS.SemanticModel\definition\relationships.tmdl
```

L'agent doit charger :

1. l'ensemble des fichiers `tables/*.tmdl`, pour repérer la table candidate et sa colonne clé ;
2. `relationships.tmdl`, pour vérifier qu'elle est bien reliée à au moins une table de faits.

---

## 3. Repérer la table candidate

Une table est candidate au rôle de dimension date si **au moins un** des signaux suivants est présent :

```text
Signal A — Nom          : le nom de la table matche /^(D_)?DATE(S)?$|^Dim_?Date$|^Calendar$|^Calendrier$/i
Signal B — Propriété     : la définition de table contient la propriété `isDateTable` (marquage explicite
                            "Mark as date table" effectué dans Power BI Desktop)
Signal C — Colonne clé   : la table contient une colonne de type `dateTime`/`date` couvrant une plage
                            continue de dates (une ligne par jour, sans doublon), généralement nommée DATE
```

```python
def find_date_table_candidates(tables):
    candidates = []
    for table in tables:
        name_match = re.match(r"^(D_)?DATE(S)?$|^Dim_?Date$|^Calendar$|^Calendrier$", table.name, re.I)
        has_flag = table.has_property("isDateTable")
        date_column = find_column_by_type(table, {"dateTime", "date"})
        if name_match or has_flag or date_column:
            candidates.append({
                "table": table.name,
                "name_match": bool(name_match),
                "is_marked": has_flag,
                "date_column": date_column.name if date_column else None,
            })
    return candidates
```

Si **aucune** table candidate n'est trouvée, la règle est évaluée `KO` : le modèle ne dispose d'aucune dimension temporelle, ce qui empêche toute time intelligence fiable (Power BI retombe alors sur les tables de dates cachées auto-générées, cf. [BP-09](09_DisableAutoDateTime.md)).

---

## 4. Vérifier le marquage et la relation aux faits

Pour la table candidate retenue (celle qui cumule le plus de signaux ; en cas d'égalité, prendre celle référencée par le plus de relations) :

```python
def check_date_table_role(table, relationships, fact_tables):
    is_marked = table.has_property("isDateTable")
    linked_facts = [
        r for r in relationships
        if (r.to_table == table.name and r.from_table in fact_tables)
        or (r.from_table == table.name and r.to_table in fact_tables)
    ]
    return {
        "is_marked": is_marked,
        "linked_fact_count": len(linked_facts),
        "linked_facts": [r.from_table if r.to_table == table.name else r.to_table for r in linked_facts],
    }
```

| Situation | Statut |
|---|---|
| Table marquée `isDateTable` **et** reliée à ≥1 table de faits | `OK` (poursuivre section 5) |
| Table présente et reliée mais **non marquée** `isDateTable` | `WARN` → `KO` (time intelligence non garantie sans marquage explicite) |
| Table présente et marquée mais **non reliée** à une table de faits | `KO` (dimension orpheline, inutilisable en filtrage croisé) |
| Aucune table candidate trouvée | `KO` |

---

## 5. Vérifier la configuration de la colonne clé de date

Une fois la table confirmée, l'agent localise la colonne clé (signal C ci-dessus, généralement `DATE`) et contrôle trois propriétés dans son bloc `column` :

```tmdl
column DATE
    dataType: dateTime
    isKey
    formatString: Long Date
    lineageTag: 24c66528-5e93-4718-bb71-57aa077b9b35
    summarizeBy: none
    sourceColumn: DATE

    annotation SummarizationSetBy = Automatic
```

| Propriété | Valeur attendue | Résultat si absente | Résultat si différente |
|---|---|---|---|
| `dataType` | `dateTime` (ou `date`) | `NA` | `KO` |
| `formatString` | un format de date reconnu (`Long Date`, `Short Date`, `dd/mm/yyyy`...) — jamais un format numérique brut | `KO` (obligatoire pour un usage correct en visuel) | `KO` |
| `summarizeBy` | `none` | `NA` | `KO` |

```python
def check_date_key_column(column):
    raw_type = column.get_property("dataType")
    raw_format = column.get_property("formatString")
    raw_summarize = column.get_property("summarizeBy")

    type_status = "NA" if raw_type is None else (
        "OK" if str(raw_type).strip().lower() in {"datetime", "date"} else "KO"
    )
    format_status = "KO" if not raw_format or not is_date_format(raw_format) else "OK"
    summarize_status = "NA" if raw_summarize is None else (
        "OK" if str(raw_summarize).strip().lower() == "none" else "KO"
    )

    return {"dataType": type_status, "formatString": format_status, "summarizeBy": summarize_status}
```

---

## 6. Vérifier la continuité de la plage de dates (optionnel mais recommandé)

Si un échantillon de données est accessible (partition M ou table calculée DAX de type `CALENDAR`/`CALENDARAUTO`), l'agent peut renforcer le contrôle :

```python
def check_date_continuity(sample_dates):
    if not sample_dates:
        return "NA"
    ordered = sorted(sample_dates)
    expected_days = (ordered[-1] - ordered[0]).days + 1
    has_duplicates = len(ordered) != len(set(ordered))
    return "OK" if len(ordered) == expected_days and not has_duplicates else "KO"
```

Ce contrôle reste secondaire : son absence de résultat (`NA`, échantillon inaccessible) ne doit jamais faire échouer la règle à elle seule.

---

## 7. Règle d'évaluation globale

```python
def evaluate_date_table(tables, relationships, fact_tables):
    candidates = find_date_table_candidates(tables)
    if not candidates:
        return {"rule_status": "KO", "reason": "Aucune table de dates candidate trouvée"}

    table = pick_best_candidate(candidates)
    role = check_date_table_role(table, relationships, fact_tables)

    if role["linked_fact_count"] == 0:
        return {"rule_status": "KO", "table": table.name, "reason": "Table de dates non reliée à une table de faits"}
    if not role["is_marked"]:
        return {"rule_status": "KO", "table": table.name, "reason": "Table non marquée isDateTable"}

    key_column = find_column_by_type(table, {"dateTime", "date"})
    if key_column is None:
        return {"rule_status": "KO", "table": table.name, "reason": "Colonne clé de date introuvable"}

    props = check_date_key_column(key_column)
    if "KO" in props.values():
        return {"rule_status": "KO", "table": table.name, "column": key_column.name, "details": props}
    if "NA" in props.values():
        return {"rule_status": "NA", "table": table.name, "column": key_column.name, "details": props}

    return {"rule_status": "OK", "table": table.name, "column": key_column.name,
            "linked_facts": role["linked_facts"]}
```

Priorité des statuts, identique aux autres règles du référentiel : `KO > NA > OK`.

---

## 8. Parcours complet du modèle

### Étape 1 — Localiser les tables et les relations
1. Lister tous les fichiers `tables/*.tmdl` et charger `relationships.tmdl`.
2. Si le dossier `tables/` est introuvable ou vide, retourner `NON_EVALUE`.

### Étape 2 — Identifier la ou les tables candidates
1. Appliquer les 3 signaux (nom, `isDateTable`, colonne de type date) à chaque table.
2. Retenir la table qui cumule le plus de signaux ; documenter les autres candidates écartées.

### Étape 3 — Vérifier le rôle de dimension
1. Contrôler le marquage `isDateTable`.
2. Contrôler la présence d'au moins une relation vers une table de faits (préfixe `F_` dans ce projet).

### Étape 4 — Vérifier la colonne clé
1. Localiser la colonne de type date/heure.
2. Contrôler `dataType`, `formatString`, `summarizeBy`.

### Étape 5 — Terminer l'analyse
Produire :
- le nom de la table retenue (ou l'absence de candidate) ;
- le statut de marquage et le nombre de tables de faits liées ;
- le détail des 3 propriétés de la colonne clé ;
- le statut global `OK` / `KO` / `NA`.

---

## 9. Structure du résultat

```json
{
  "rule_id": "BP-02",
  "alias": "SEM-002",
  "rule_name": "Table de dates dédiée, marquée et correctement configurée",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "candidate_tables_found": 0,
  "table": null,
  "reason": "Aucune table de dates candidate trouvée dans le modèle sémantique"
}
```

Exemple avec table trouvée mais mal configurée :

```json
{
  "rule_id": "BP-02",
  "alias": "SEM-002",
  "rule_name": "Table de dates dédiée, marquée et correctement configurée",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "table": "D_DATES",
  "is_marked": true,
  "linked_fact_count": 2,
  "linked_facts": ["F_RESPONSES", "F_ADOPTION_QUESTION"],
  "column": "DATE",
  "details": {
    "dataType": "OK",
    "formatString": "KO",
    "summarizeBy": "OK"
  },
  "reason": "formatString absent ou non reconnu comme un format de date"
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `KO` (table absente — cas actuel du projet audité)

```text
BP-02 (SEM-002) — Table de dates dédiée : KO

Aucune table de dates candidate n'a été trouvée dans
AI_BAROMETER_BI-CDS.SemanticModel/definition/tables/.

Tables de dimension présentes : D_CAMPAIGNS, D_CHOICE,
D_USAGE_FREQUENCY_LEVELS, D_USERS — aucune ne correspond à un rôle
de dimension date (nom, marquage isDateTable ou colonne de type date).

Correction attendue :
créer une table D_DATES avec une colonne DATE (dataType: dateTime,
formatString: Long Date, summarizeBy: none), la marquer comme table
de dates ("Mark as date table") et la relier aux tables de faits
F_RESPONSES et F_ADOPTION_QUESTION via une clé de date.
```

### Exemple `OK`

```text
BP-02 (SEM-002) — Table de dates dédiée : OK

Table D_DATES identifiée, marquée comme table de dates et reliée à
2 table(s) de faits (F_RESPONSES, F_ADOPTION_QUESTION).
Colonne clé DATE conforme : dataType=dateTime, formatString=Long Date,
summarizeBy=none.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la règle `OK` que si toutes les conditions suivantes sont réunies :

- au moins une table candidate a été identifiée par au moins un signal fiable (marquage ou colonne de type date — le nom seul ne suffit pas) ;
- la table est explicitement marquée `isDateTable` ;
- au moins une relation la relie à une table de faits ;
- la colonne clé a été localisée et ses trois propriétés (`dataType`, `formatString`, `summarizeBy`) ont été lues et validées ;
- aucune des trois propriétés n'est en `KO`.

L'agent ne doit jamais produire `OK` sur la seule base d'un nom de table évocateur (`D_DATES`) sans vérifier le marquage effectif et la relation aux faits.

---

## 12. Résumé de la règle

```text
RÈGLE BP-02 (SEM-002)

IDENTIFIER les tables candidates (nom, isDateTable, colonne de type date)
SI aucune candidate
    règle = KO

RETENIR la meilleure candidate
SI non reliée à une table de faits
    règle = KO
SI non marquée isDateTable
    règle = KO

LOCALISER la colonne clé de date
POUR dataType, formatString, summarizeBy
    LIRE la propriété et comparer à la valeur attendue
    SI absente → NA ; SI différente → KO

SI au moins une propriété KO
    règle = KO
SINON SI au moins une propriété NA
    règle = NA
SINON
    règle = OK
```

La propriété décisionnelle est la combinaison de :
```tmdl
isDateTable                 (marquage de la table)
relationship fromColumn/toColumn   (relation vers une table de faits, relationships.tmdl)
dataType / formatString / summarizeBy   (colonne clé de date)
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-02 (SEM-002) — Table de dates dédiée, marquée        │
│         et correctement configurée                              │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │ Lister tables/*.tmdl          │
          │ Charger relationships.tmdl    │
          └──────────────┬────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ Trouvé ✅   ║    │ Dossier tables/       │
         ╚════╤════════╝    │ introuvable/vide ❌   │
              │              └──────────┬────────────┘
              │                         ▼
              │                 ┌───────────────────┐
              │                 │ Retour : NON_EVALUE│
              │                 └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque table (boucle)                 │
   │ Appliquer 3 signaux candidats :            │
   │  A. Nom (D_DATES/DimDate/Calendar...)      │
   │  B. Propriété isDateTable                  │
   │  C. Colonne de type date/dateTime continue │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌──────────────────────────────┐
        │ Au moins une candidate ?     │
        └───────┬──────────────┬────────┘
             non│               │oui
                ▼               ▼
        ╔═══════════════╗  ┌────────────────────────┐
        ║ règle = KO    ║  │ Retenir la meilleure    │
        ║ (aucune table ║  │ candidate (+ de signaux)│
        ║  de dates)    ║  └───────────┬──────────────┘
        ╚═══════════════╝              ▼
                          ┌────────────────────────────┐
                          │ Reliée à ≥1 table de faits ?│
                          └──────┬──────────────┬────────┘
                                non│              │oui
                                   ▼              ▼
                        ╔═══════════════╗ ┌─────────────────────┐
                        ║ règle = KO    ║ │ Marquée isDateTable ?│
                        ╚═══════════════╝ └──────┬────────┬───────┘
                                                non│         │oui
                                                   ▼         ▼
                                        ╔═══════════════╗ ┌───────────────────────┐
                                        ║ règle = KO    ║ │ Colonne clé de date    │
                                        ╚═══════════════╝ │ (type date/dateTime)   │
                                                           │ trouvée ?              │
                                                           └──────┬────────┬────────┘
                                                                non│         │oui
                                                                   ▼         ▼
                                                        ╔═══════════════╗ ┌─────────────────────────────┐
                                                        ║ règle = KO    ║ │ POUR chaque propriété :      │
                                                        ╚═══════════════╝ │ dataType / formatString /    │
                                                                          │ summarizeBy (boucle 3 items) │
                                                                          │ LIRE et COMPARER à l'attendu │
                                                                          │ SI absente → NA ; SI ≠ → KO  │
                                                                          └──────────────┬────────────────┘
                                                                                         ▼
                                                                     ┌──────────────────────────────────┐
                                                                     │ CALCUL DU RÉSULTAT FINAL          │
                                                                     │ SI ≥1 propriété KO   → règle = KO │
                                                                     │ SINON SI ≥1 NA        → règle = NA│
                                                                     │ SINON                  → règle = OK│
                                                                     └──────────────────┬─────────────────┘
                                                                                        ▼
                                                                        RETOUR rule_status (OK/KO/NA)
```
