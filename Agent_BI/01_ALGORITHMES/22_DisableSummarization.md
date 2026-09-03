# BP-22 (alias SEM-001) — Désactivation de l'autosummarization des colonnes

> **Statut d'implémentation : ✅ Implémenté** — moteur : [`03_PYTHON/rules/bp_22.py`](../03_PYTHON/rules/bp_22.py), tests : `03_PYTHON/tests/test_bp_22.py`.

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que toutes les colonnes du modèle sémantique Power BI sont configurées avec la propriété suivante :

```tmdl
summarizeBy: none
```

Cette configuration indique que Power BI ne doit pas appliquer automatiquement une agrégation par défaut à la colonne (ce qui produirait des « mesures implicites », cf. [BP-32](32_ExplicitMeasures.md)).

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables ;
- du nombre de colonnes ;
- du nom des tables et des colonnes ;
- du type de données des colonnes ;
- de l'ordre des propriétés dans les fichiers TMDL ;
- du caractère visible ou masqué des colonnes.

---

## 2. Emplacement du modèle sémantique

Pour un projet Power BI au format PBIP, l'agent doit rechercher les fichiers de tables dans le dossier suivant :

```text
<SEMANTIC_MODEL_PATH>\definition\tables\
```

Chaque table du modèle est généralement représentée par un fichier TMDL :

```text
AI_BAROMETER_BI-CDS.SemanticModel\
└── definition\
    └── tables\
        ├── D_CAMPAIGNS.tmdl
        ├── D_USERS.tmdl
        └── F_RESPONSES.tmdl
```

L'agent doit récupérer tous les fichiers portant l'extension `.tmdl` dans ce dossier.

---

## 3. Propriété à contrôler

Dans chaque fichier TMDL, l'agent doit identifier tous les blocs `column`.

Exemple :

```tmdl
table D_CAMPAIGNS
    lineageTag: 6bfd2601-0ebf-442a-8353-f9e5f53901ab

    column CAMPAIGN_ID
        dataType: string
        isHidden
        lineageTag: b30938a6-aa65-4080-bd83-dd84d12c599d
        summarizeBy: none
        sourceColumn: CAMPAIGN_ID

        changedProperty = IsHidden

        annotation SummarizationSetBy = Automatic
```

Pour cette règle, l'agent doit uniquement utiliser la valeur de :

```tmdl
summarizeBy: <VALUE>
```

L'annotation suivante peut être conservée comme information de contexte, mais elle ne doit jamais intervenir dans le verdict :

```tmdl
annotation SummarizationSetBy = Automatic
```

Dans l'exemple précédent, `CAMPAIGN_ID` est conforme, car sa valeur effective est `summarizeBy: none`.

---

## 4. Règle d'évaluation d'une colonne

Pour chaque colonne détectée, l'agent doit appliquer la logique suivante :

| Situation détectée | Statut de la colonne | Interprétation |
|---|---|---|
| `summarizeBy: none` | `OK` | L'agrégation automatique est désactivée. |
| `summarizeBy` est présent avec une autre valeur | `KO` | Une agrégation par défaut différente de `none` est configurée. |
| `summarizeBy` est absent | `NA` | La conformité ne peut pas être déterminée avec cette lecture. |
| La valeur est vide, illisible ou inconnue | `NA` | La propriété n'a pas pu être interprétée de manière fiable. |

Exemples :

| Table | Colonne | Valeur détectée | Statut |
|---|---|---|---|
| `D_CAMPAIGNS` | `CAMPAIGN_ID` | `none` | `OK` |
| `F_SALES` | `TOTAL_AMOUNT` | `sum` | `KO` |
| `F_SALES` | `AVERAGE_SCORE` | `average` | `KO` |
| `D_USERS` | `USER_ID` | propriété absente | `NA` |
| `F_ORDERS` | `QUANTITY` | valeur illisible | `NA` |

---

## 5. Parcours complet du modèle

L'agent doit parcourir l'intégralité du modèle sémantique sans s'arrêter après la première anomalie.

### Étape 1 — Localiser les tables
1. Accéder au dossier `<SEMANTIC_MODEL_PATH>\definition\tables\`.
2. Vérifier que le dossier existe et qu'il est accessible.
3. Récupérer la liste complète des fichiers `*.tmdl`.
4. Si aucun fichier n'est trouvé, arrêter l'évaluation et retourner `NA` (information indisponible pour conclure).

### Étape 2 — Lire chaque table
Pour chaque fichier TMDL : ouvrir le fichier ; identifier le nom réel de la table ; identifier tous les blocs `column` ; analyser chaque colonne détectée ; passer au fichier de table suivant.

### Étape 3 — Lire chaque colonne
Pour chaque bloc `column` : récupérer le nom de la colonne ; rechercher la propriété `summarizeBy` dans tout le bloc ; récupérer sa valeur brute ; normaliser la valeur ; attribuer le statut `OK`, `KO` ou `NA` ; enregistrer le résultat ; passer à la colonne suivante.

### Étape 4 — Terminer l'analyse
Lorsque la dernière colonne de la table a été analysée, l'agent passe à la table suivante, jusqu'à la dernière colonne de la dernière table.

Il produit ensuite : le nombre total de tables et de colonnes analysées ; le nombre de colonnes conformes (`OK`) ; le nombre de colonnes non conformes (`KO`) ; le nombre de colonnes `NA` ; la liste complète des colonnes `KO` ; la liste complète des colonnes `NA`.

---

## 6. Détection robuste des blocs de colonnes

L'agent ne doit pas supposer que les propriétés d'une colonne apparaissent toujours dans le même ordre. Les deux blocs suivants doivent être interprétés de la même manière :

```tmdl
column CAMPAIGN_ID
    dataType: string
    lineageTag: b30938a6-aa65-4080-bd83-dd84d12c599d
    summarizeBy: none
    sourceColumn: CAMPAIGN_ID
```

```tmdl
column CAMPAIGN_ID
    sourceColumn: CAMPAIGN_ID
    summarizeBy: none
    dataType: string
    lineageTag: b30938a6-aa65-4080-bd83-dd84d12c599d
```

Pour être générique, l'agent doit donc :
1. détecter le début du bloc avec le mot-clé `column` ;
2. déterminer la fin du bloc grâce à la structure ou à l'indentation TMDL ;
3. rechercher `summarizeBy` n'importe où dans ce bloc ;
4. ignorer les autres propriétés pour le calcul de cette règle ;
5. ne pas exiger la présence de l'annotation `SummarizationSetBy`.

L'agent doit analyser toutes les catégories de colonnes : textuelles, numériques, date/heure, booléennes, calculées, masquées, techniques, importées ou en DirectQuery.

Les mesures, hiérarchies, partitions et relations ne font pas partie du périmètre de cette règle.

---

## 7. Normalisation de la valeur

Avant la comparaison, l'agent doit : supprimer les espaces avant et après la valeur ; convertir la valeur en minuscules ; conserver la valeur brute dans la preuve technique.

```python
normalized_value = str(raw_value).strip().lower()
```

Ainsi, `none`, `None`, `NONE`, ` none ` sont tous interprétés comme `none`.

---

## 8. Pseudo-code détaillé

```python
conforming_columns = []
nonconforming_columns = []
na_columns = []

table_files = find_all_tmdl_files("<SEMANTIC_MODEL_PATH>/definition/tables/")

if not table_files:
    return {
        "execution_status": "ERROR",
        "rule_status": "NA",
        "reason": "Aucun fichier de table TMDL trouvé",
    }

for table_file in table_files:
    table = parse_tmdl_table(table_file)

    for column in table.columns:
        raw_value = column.get_property("summarizeBy")

        if raw_value is None:
            na_columns.append({
                "table": table.name, "column": column.name,
                "summarizeBy": None, "status": "NA",
                "reason": "Propriété summarizeBy absente",
            })
            continue

        normalized_value = str(raw_value).strip().lower()

        if normalized_value == "none":
            conforming_columns.append({
                "table": table.name, "column": column.name,
                "summarizeBy": normalized_value, "status": "OK",
            })
        elif normalized_value in {"sum", "average", "count", "distinctcount", "min", "max", "default"}:
            nonconforming_columns.append({
                "table": table.name, "column": column.name,
                "summarizeBy": normalized_value, "status": "KO",
                "reason": "Valeur différente de none",
            })
        else:
            na_columns.append({
                "table": table.name, "column": column.name,
                "summarizeBy": raw_value, "status": "NA",
                "reason": "Valeur summarizeBy inconnue ou illisible",
            })
```

---

## 9. Calcul du statut global de la bonne pratique

```python
if nonconforming_columns:
    rule_status = "KO"
elif na_columns:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les colonnes sont conformes | `OK` |
| Au moins une colonne est non conforme | `KO` |
| Aucun `KO`, mais au moins une colonne est invérifiable | `NA` |
| Des colonnes `KO` et `NA` sont présentes | `KO`, avec analyse partielle signalée |

Le statut global ne doit être `OK` que si toutes les colonnes ont été lues et possèdent explicitement la valeur `none`.

---

## 10. Structure du résultat

Exemple lorsque la bonne pratique est respectée (état actuel du projet audité) :

```json
{
  "rule_id": "BP-22",
  "alias": "SEM-001",
  "rule_name": "Désactivation de l'autosummarization",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_tables": 15,
  "total_columns": 69,
  "conforming_columns": 69,
  "nonconforming_columns": 0,
  "na_columns": 0,
  "ko_details": [],
  "na_details": []
}
```

Exemple avec colonnes non conformes et `NA` :

```json
{
  "rule_id": "BP-22",
  "alias": "SEM-001",
  "rule_name": "Désactivation de l'autosummarization",
  "execution_status": "PARTIAL",
  "rule_status": "KO",
  "total_tables": 4,
  "total_columns": 38,
  "conforming_columns": 35,
  "nonconforming_columns": 2,
  "na_columns": 1,
  "ko_details": [
    {"table": "F_SALES", "column": "TOTAL_AMOUNT", "summarizeBy": "sum"},
    {"table": "F_SALES", "column": "QUANTITY", "summarizeBy": "average"}
  ],
  "na_details": [
    {"table": "D_USERS", "column": "USER_ID", "summarizeBy": null, "reason": "Propriété summarizeBy absente"}
  ]
}
```

---

## 11. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-22 (SEM-001) — Désactivation de l'autosummarization : OK

Toutes les colonnes du modèle sémantique sont configurées avec
summarizeBy: none.

69 colonnes conformes sur 69 colonnes analysées (15 tables).
```

### Exemple `KO`

```text
BP-22 (SEM-001) — Désactivation de l'autosummarization : KO

35 colonnes conformes sur 38 colonnes analysées.

Colonnes non conformes :
- F_SALES[TOTAL_AMOUNT] : summarizeBy = sum
- F_SALES[QUANTITY] : summarizeBy = average

Colonne non évaluable :
- D_USERS[USER_ID] : propriété summarizeBy absente

Correction attendue :
configurer la propriété SummarizeBy sur None pour toutes les colonnes
non conformes.
```

---

## 12. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- le dossier du modèle sémantique a été identifié ;
- tous les fichiers de tables TMDL ont été récupérés ;
- chaque fichier a été lu correctement ;
- au moins une table a été trouvée ;
- au moins une colonne a été trouvée ;
- toutes les colonnes ont été parcourues ;
- chaque valeur `summarizeBy` a été interprétée ;
- aucune colonne ne possède une valeur différente de `none` ;
- aucune colonne n'est classée `NA`.

L'agent ne doit jamais produire `OK` lorsqu'un fichier est illisible, lorsqu'aucune colonne n'a été trouvée ou lorsqu'une partie du modèle n'a pas été analysée.

---

## 13. Résumé de la règle

```text
RÈGLE BP-22 (SEM-001)

POUR chaque table du modèle sémantique
    POUR chaque colonne de la table
        LIRE summarizeBy

        SI summarizeBy = none
            colonne = OK
        SINON SI summarizeBy est présent et interprétable
            colonne = KO
        SINON
            colonne = NA

        ENREGISTRER le résultat
    FIN POUR
FIN POUR

SI au moins une colonne est KO
    règle = KO
SINON SI au moins une colonne est NA
    règle = NA
SINON
    règle = OK

AFFICHER toutes les colonnes KO et toutes les colonnes NA
```

La propriété décisionnelle est exclusivement :

```tmdl
summarizeBy: <VALUE>
```

L'annotation suivante ne modifie jamais le verdict :

```tmdl
annotation SummarizationSetBy = <STATUS>
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-22 (alias SEM-001) — Désactivation de                     │
│ l'autosummarization des colonnes                                       │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ Localiser <SEMANTIC_MODEL_PATH>\             │
          │ definition\tables\*.tmdl                       │
          └────────────────┬───────────────────────────────┘
               ┌───────────┴───────────┐
               ▼                       ▼
         ╔═════════════╗       ┌──────────────────┐
         ║ Fichiers    ║       │ Aucun fichier ❌      │
         ║ trouvés ✅  ║       └─────────┬──────────┘
         ╚══════╤══════╝                 ▼
                │                ┌────────────────┐
                │                │ Retour :          │
                │                │ NA                │
                │                └────────────────┘
                ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque fichier de table (boucle)         │
     │  POUR chaque bloc column (boucle imbriquée)    │
     └────────────────┬───────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ Lire summarizeBy dans le bloc    │
        │ column (n'importe où)            │
        └──────────┬──────────────────────┘
                   ▼
        ┌───────────────────────────────┐
        │ Propriété présente ?             │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ┌──────────┐   ╔═══════════╗
       │ NON = NA │   ║ OUI          ║
       └──────────┘   ╚═════╤════════╝
                            ▼
                 ┌───────────────────────┐
                 │ NORMALISER (strip +       │
                 │ lower) la valeur           │
                 └──────────┬─────────────────┘
                            ▼
                 ┌───────────────────────┐
                 │ Valeur = "none" ?          │
                 └──────────┬─────────────────┘
                      ┌──────┴──────┐
                      ▼             ▼
                ╔═══════════╗ ┌───────────────────────┐
                ║ OUI = OK  ║ │ NON : valeur connue       │
                ╚═══════════╝ │ (sum/average/count/...)    │
                               │ ou illisible ?             │
                               └──────────┬─────────────────┘
                                    ┌──────┴──────┐
                                    ▼             ▼
                              ╔═══════════╗ ┌──────────┐
                              ║ connue     ║ │illisible   │
                              ║ = KO       ║ │= NA        │
                              ╚═══════════╝ └──────────┘
                                    │             │
                                    └──────┬──────┘
                                          ▼
                    FIN DE BOUCLE (colonne/table suivante)
                                          │
                                          ▼
        ┌────────────────────────────────────────────┐
        │ CALCUL DU RÉSULTAT FINAL                        │
        │ Au moins une colonne KO → règle = KO               │
        │ Sinon au moins une NA   → règle = NA               │
        │ Sinon                    → règle = OK              │
        └────────────────────┬───────────────────────────────┘
                             ▼
             RETOUR rule_status (OK/KO/NA)
```
