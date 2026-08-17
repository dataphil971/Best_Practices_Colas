# BP-25 — Masquage des champs techniques (isHidden)

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que les colonnes purement techniques du modèle sémantique — clés techniques utilisées seulement pour établir des relations, colonnes de tri (`sortByColumn`) exploitées en arrière-plan, colonnes intermédiaires consommées uniquement par des mesures DAX, colonnes de couleur/format destinées à l'affichage dynamique — sont masquées (`isHidden` en TMDL) afin de ne pas apparaître dans le volet des champs présenté à l'utilisateur final. Un volet des champs encombré de colonnes sans valeur d'analyse directe complique la recherche du bon champ, augmente le risque d'utilisation erronée d'une colonne technique dans un visuel, et nuit à la perception de qualité du modèle.

Cette règle est le pendant « visibilité » de [BP-23](23_OrganizeDAXAndFields.md) (organisation en dossiers) et de [BP-24](24_GroupMeasures.md) (centralisation des mesures) : un champ correctement masqué n'a pas besoin d'être organisé, puisqu'il n'apparaît jamais dans le volet des champs.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables et de colonnes ;
- du nom des tables et des colonnes ;
- du type de données de la colonne ;
- de l'ordre des propriétés dans les fichiers TMDL.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\T_NOTIFICATION.tmdl
```

Pour qualifier l'usage réel d'une colonne (utilisée uniquement par des mesures ou des relations, ou réellement exposée à l'analyse), l'agent doit croiser :

1. la définition de la colonne elle-même (`tables\*.tmdl`) ;
2. les relations du modèle (`<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl`), pour savoir si la colonne sert de clé de relation ;
3. les expressions DAX des mesures (`tables\MEASURE.tmdl` ou toute table portant des mesures), pour savoir si la colonne n'est référencée que par des mesures et jamais destinée à un usage direct en visuel.

---

## 3. Élément(s) / propriété(s) à contrôler

La propriété décisive est :

```tmdl
isHidden
```

Il s'agit d'une propriété booléenne sans valeur : sa simple présence dans le bloc `column` signifie que la colonne est masquée ; son absence signifie qu'elle est visible.

Exemple réel de colonne technique correctement masquée (`F_RESPONSES.tmdl`) :

```tmdl
column INTEREST_LEGEND_ORDER
    dataType: int64
    isHidden
    formatString: 0
    lineageTag: 7ad3919d-b889-4363-b02d-b5a86c368c75
    summarizeBy: none
    sourceColumn: INTEREST_LEGEND_ORDER

    changedProperty = IsHidden

    annotation SummarizationSetBy = User
```

Cette colonne `INTEREST_LEGEND_ORDER` sert uniquement de colonne de tri (`sortByColumn`) pour la colonne métier `INTEREST_LEVEL` :

```tmdl
column INTEREST_LEVEL
    dataType: string
    lineageTag: 1609386e-7433-4da9-8d72-604b4a0317a8
    summarizeBy: none
    sourceColumn: INTEREST_LEVEL
    sortByColumn: INTEREST_LEGEND_ORDER
```

Exemple de colonne technique **non conforme** (visible alors qu'elle ne devrait pas l'être) — cas hypothétique de clé technique de jointure :

```tmdl
column CAMPAIGN_USER_LOGIN_KEY
    dataType: string
    lineageTag: aaaa1111-bbbb-2222-cccc-3333dddd4444
    summarizeBy: none
    sourceColumn: CAMPAIGN_USER_LOGIN_KEY
```

Aucune propriété `isHidden` : la colonne apparaîtrait dans le volet des champs alors qu'elle ne sert qu'à une relation technique.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Colonne identifiée comme technique (clé de relation sans intitulé métier, colonne `*_ORDER`/`*_LEGEND_ORDER` utilisée en `sortByColumn`, colonne référencée uniquement par des mesures DAX) ET `isHidden` présent | `OK` | La colonne technique est correctement masquée. |
| Colonne identifiée comme technique ET `isHidden` absent | `KO` | Une colonne sans valeur d'analyse directe encombre le volet des champs. |
| Colonne métier (destinée à être glissée dans un visuel, un slicer ou un axe) sans `isHidden` | `OK` | Comportement attendu : la colonne est visible car elle est utile à l'analyse. |
| Colonne métier avec `isHidden` présent | `WARN` | Une colonne potentiellement utile à l'analyse est masquée ; à confirmer que ce masquage est intentionnel (ex. remplacée par une mesure ou une hiérarchie). |
| Colonne dont l'usage ne peut pas être déterminé de façon fiable (aucune relation, aucune référence DAX trouvée, nom ambigu) | `NA` | Le statut technique/métier ne peut pas être tranché automatiquement avec certitude. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Charger `relationships.tmdl` pour connaître les colonnes utilisées comme clés de relation.
3. Charger l'ensemble des expressions DAX des mesures pour construire l'index des colonnes référencées.
4. Si aucun fichier de table n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Qualifier chaque colonne
Pour chaque colonne de chaque table : déterminer si elle est une clé de relation (présente dans `relationships.tmdl` comme `fromColumn`/`toColumn`) ; déterminer si elle sert de `sortByColumn` pour une autre colonne ; déterminer si elle est référencée dans au moins une expression DAX de mesure ; déterminer si elle est référencée dans au moins un visuel du rapport comme champ d'axe/légende/slicer/valeur directe (hors référence uniquement en filtre technique).

### Étape 3 — Classer la colonne technique ou métier
Une colonne est classée **technique** si elle remplit au moins l'une des conditions suivantes et **aucune** des conditions d'usage métier direct :
- elle est utilisée comme `sortByColumn` par une autre colonne ;
- elle est une clé de relation et son nom ne correspond à aucun intitulé métier lisible (heuristique de nommage : suffixe `_ID`, `_KEY`, `_KEY_TECH`) ;
- elle n'est référencée que dans des expressions DAX de mesures et jamais directement dans un visuel du rapport.

### Étape 4 — Appliquer la règle d'évaluation
Appliquer la logique de la section 4 à chaque colonne. Ne pas s'arrêter à la première colonne non conforme : parcourir la totalité des colonnes de toutes les tables.

### Étape 5 — Terminer l'analyse
Produire le nombre total de colonnes analysées, le détail des colonnes `OK`, `KO`, `WARN`, `NA`, avec pour chacune la preuve de classification (clé de relation, `sortByColumn`, référence DAX uniquement, etc.).

---

## 6. Détection robuste / normalisation

- `isHidden` est une propriété sans valeur explicite (contrairement à `summarizeBy: none`) : sa détection se fait par présence/absence de la ligne dans le bloc, pas par comparaison de valeur.
- L'ordre des propriétés dans le bloc `column` est variable : l'agent doit rechercher `isHidden` n'importe où dans le bloc.
- Le bloc `changedProperty = IsHidden` qui suit parfois la déclaration de la colonne est un artefact de suivi de modification TMDL ; il confirme que le masquage a été appliqué manuellement dans l'éditeur, mais ne doit jamais être utilisé seul pour déduire l'état masqué : seule la présence de `isHidden` dans le bloc `column` fait foi.
- La colonne `sortByColumn: INTEREST_LEGEND_ORDER` d'une colonne référence une autre colonne par son nom nu (sans préfixe de table) : l'agent doit résoudre ce nom dans la même table pour identifier la colonne technique associée.
- Une colonne peut être référencée dans une expression DAX multi-lignes (triple backticks) : l'agent doit rechercher les références `Table[Colonne]` dans l'intégralité du corps de chaque mesure, quel que soit son format d'écriture.
- La recherche de références dans les visuels du rapport (`<REPORT_PATH>\definition\pages\*\visuals\*\visual.json`) doit porter sur le champ `"Property"` associé à un `"Column"` (et non `"Measure"`) dans les blocs `queryRef`/`projections`.

```python
def is_hidden(column):
    return column.has_flag("isHidden")

def is_sort_by_target(column, table):
    return any(c.get_property("sortByColumn") == column.name for c in table.columns)

def is_relationship_key(column, table, relationships):
    return any(
        (r.from_table == table.name and r.from_column == column.name)
        or (r.to_table == table.name and r.to_column == column.name)
        for r in relationships
    )

def is_referenced_only_in_dax(column, table, measures_dax_index, report_column_refs):
    qualified = f"{table.name}[{column.name}]"
    used_in_dax = qualified in measures_dax_index
    used_in_report = (table.name, column.name) in report_column_refs
    return used_in_dax and not used_in_report
```

---

## 7. Pseudo-code détaillé

```python
def analyze_hidden_technical_fields(table_files, relationships_file, report_pages):
    relationships = parse_relationships(relationships_file)
    measures_dax_index = build_dax_column_reference_index(table_files)  # {"Table[Col]": [measure_names]}
    report_column_refs = build_report_column_reference_index(report_pages)  # {(table, column)}

    ok_items, ko_items, warn_items, na_items = [], [], [], []

    for table_file in table_files:
        table = parse_tmdl_table(table_file)

        for column in table.columns:
            hidden = is_hidden(column)

            is_technical = (
                is_sort_by_target(column, table)
                or is_relationship_key(column, table, relationships)
                or is_referenced_only_in_dax(column, table, measures_dax_index, report_column_refs)
            )
            is_business_visible = (table.name, column.name) in report_column_refs

            if is_technical and not is_business_visible:
                if hidden:
                    ok_items.append({"table": table.name, "column": column.name, "status": "OK"})
                else:
                    ko_items.append({
                        "table": table.name, "column": column.name, "status": "KO",
                        "reason": "Colonne technique visible dans le volet des champs",
                    })
            elif is_business_visible:
                if hidden:
                    warn_items.append({
                        "table": table.name, "column": column.name, "status": "WARN",
                        "reason": "Colonne utilisée dans un visuel mais masquée : à confirmer",
                    })
                else:
                    ok_items.append({"table": table.name, "column": column.name, "status": "OK"})
            else:
                na_items.append({
                    "table": table.name, "column": column.name, "status": "NA",
                    "reason": "Usage indéterminé (aucune relation, aucune référence DAX ou visuelle trouvée)",
                })

    return ok_items, ko_items, warn_items, na_items
```

---

## 8. Calcul du statut global

```python
if ko_items:
    rule_status = "KO"
elif na_items:
    rule_status = "NA"
elif warn_items:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > WARN > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les colonnes techniques sont masquées et toutes les colonnes métier sont visibles | `OK` |
| Au moins une colonne technique est visible | `KO` |
| Aucun `KO`, mais au moins une colonne à l'usage indéterminé | `NA` |
| Aucun `KO`/`NA`, mais au moins une colonne métier masquée à confirmer | `WARN` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-25",
  "rule_name": "Masquage des champs techniques",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_columns": 69,
  "technical_columns_hidden": 18,
  "business_columns_visible": 47,
  "ko_details": [],
  "warn_details": [],
  "na_details": [
    {"table": "D_USERS", "column": "USER_COMMENT", "reason": "Usage indéterminé"}
  ]
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-25",
  "rule_name": "Masquage des champs techniques",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_columns": 69,
  "ko_details": [
    {
      "table": "F_RESPONSES",
      "column": "CAMPAIGN_USER_LOGIN_KEY",
      "reason": "Clé de relation technique visible dans le volet des champs"
    }
  ],
  "warn_details": [],
  "na_details": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-25 — Masquage des champs techniques : OK

69 colonnes analysées. Les 18 colonnes techniques identifiées (clés de
relation, colonnes de tri *_LEGEND_ORDER, colonnes exploitées uniquement par
des mesures) sont toutes masquées (isHidden). Les 47 colonnes métier restent
visibles pour l'analyse.
```

### Exemple `KO`

```text
BP-25 — Masquage des champs techniques : KO

Colonne technique visible détectée :
- F_RESPONSES[CAMPAIGN_USER_LOGIN_KEY] : clé technique utilisée uniquement
  pour la relation avec D_USERS, sans intitulé métier, actuellement visible
  dans le volet des champs.

Correction attendue :
ajouter la propriété isHidden au bloc column CAMPAIGN_USER_LOGIN_KEY dans
F_RESPONSES.tmdl.
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus ;
- `relationships.tmdl` a été chargé pour identifier les clés de relation ;
- l'index des références DAX a été construit sur l'ensemble des mesures du modèle, quel que soit leur format d'écriture ;
- l'index des références dans les visuels du rapport a été construit sur l'ensemble des pages et visuels, en distinguant explicitement les références de type `"Column"` des références de type `"Measure"` ;
- chaque colonne a été classée technique ou métier avant d'évaluer son état `isHidden` ;
- aucune colonne n'a été omise de l'analyse, y compris dans les tables paramètres et les tables de dimension secondaires.

---

## 12. Résumé de la règle

```text
RÈGLE BP-25

CONSTRUIRE l'index des relations (relationships.tmdl)
CONSTRUIRE l'index des références DAX (toutes les mesures)
CONSTRUIRE l'index des références dans les visuels du rapport

POUR chaque table du modèle sémantique
    POUR chaque colonne de la table
        DÉTERMINER si la colonne est technique (sortByColumn, clé de relation
                     technique, ou référencée uniquement en DAX)
        DÉTERMINER si la colonne est visible dans au moins un visuel (usage métier)

        SI technique ET NON visible dans un visuel
            SI isHidden présent -> OK
            SINON -> KO
        SINON SI visible dans un visuel
            SI isHidden présent -> WARN (à confirmer)
            SINON -> OK
        SINON
            -> NA (usage indéterminé)

        ENREGISTRER le résultat
    FIN POUR
FIN POUR

SI au moins une colonne KO -> règle = KO
SINON SI au moins une colonne NA -> règle = NA
SINON SI au moins une colonne WARN -> règle = WARN
SINON -> règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-25 — Masquage des champs techniques (isHidden)    │
└────────────────────────┬───────────────────────────────────────┘
                          ▼
        ┌───────────────────────────────────────────┐
        │ Charger tables\*.tmdl                        │
        │ Charger relationships.tmdl                   │
        │ Construire l'index des références DAX        │
        │ Construire l'index des références visuelles   │
        └───────────────────┬───────────────────────────┘
                ┌─────────────┴─────────────┐
                ▼                            ▼
          ╔═════════════╗            ┌───────────────┐
          ║ Fichiers    ║            │ Aucun fichier  │
          ║ trouvés ✅  ║            │ de table ❌     │
          ╚══════╤══════╝            └───────┬────────┘
                 │                            ▼
                 │                    ┌────────────────┐
                 │                    │ Retour :        │
                 │                    │ NON_EVALUE      │
                 │                    └────────────────┘
                 ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque table                           │
   │  POUR chaque colonne                         │
   │  (boucle sur toutes les colonnes du modèle)  │
   └───────────────────────┬─────────────────────────┘
                           ▼
        ┌────────────────────────────────────────┐
        │ DÉTERMINER : sortByColumn cible ?        │
        │              clé de relation technique ? │
        │              référencée seulement en DAX?│
        │              référencée dans un visuel ?  │
        └────────────────────┬─────────────────────┘
                             ▼
              ┌──────────────────────────────┐
              │ Technique ET pas visible       │
              │ dans un visuel ?               │
              └───────────────┬────────────────┘
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                      ▼
  ╔═════════╗           ┌────────────┐         ┌────────────┐
  ║ OUI     ║           │ NON, mais  │         │ NON, usage │
  ╚════╤════╝           │ visible    │         │ indéterminé│
       ▼                │ (métier)   │         └─────┬──────┘
 ┌──────────────┐       └─────┬──────┘               ▼
 │ isHidden      │             ▼                ┌────────────┐
 │ présent ?     │      ┌──────────────┐        │ colonne=NA │
 └──────┬─────────┘      │ isHidden      │        └────────────┘
   ┌─────┴─────┐         │ présent ?     │
   ▼           ▼         └──────┬─────────┘
╔══════╗  ┌──────────┐     ┌─────┴─────┐
║ OUI  ║  │ NON       │     ▼           ▼
╚══╤═══╝  └────┬──────┘  ╔══════╗  ┌──────────┐
   ▼            ▼         ║ OUI  ║  │ NON       │
┌───────┐  ┌───────┐      ╚══╤═══╝  └────┬──────┘
│col=OK  │  │col=KO  │         ▼            ▼
└───────┘  └───────┘     ┌───────────┐ ┌───────┐
                          │col=WARN    │ │col=OK  │
                          │(à confirmer)│ └───────┘
                          └───────────┘
                 │ (répéter pour toutes les colonnes de toutes les tables)
                 ▼
     ┌──────────────────────────────────────┐
     │ CALCUL DU STATUT GLOBAL                │
     │ KO présent ?        -> règle = KO      │
     │ Sinon NA présent ?  -> règle = NA      │
     │ Sinon WARN présent ?-> règle = WARN    │
     │ Sinon               -> règle = OK      │
     └────────────────────┬─────────────────────┘
                          ▼
                RETOUR rule_status
                (OK / KO / NA / WARN)
```
