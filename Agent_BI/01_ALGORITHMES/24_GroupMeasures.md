# BP-24 — Centralisation des mesures dans une ou des tables dédiées

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que les mesures DAX du modèle sémantique sont centralisées dans une ou plusieurs tables dédiées (souvent nommées `MEASURE`, `_Measures`, `KPIs`...) ne contenant aucune colonne de données métier, plutôt que dispersées à travers les tables de faits et de dimensions. Cette pratique améliore la réutilisabilité (un développeur sait immédiatement où chercher/ajouter une mesure), la lisibilité du volet des champs (les tables de faits/dimensions n'affichent que des colonnes, les mesures sont regroupées ailleurs) et limite les risques de confusion entre colonnes physiques et mesures calculées lors de la maintenance du modèle.

Une table de mesures dédiée est reconnaissable structurellement : elle ne possède pas de colonnes issues d'une source de données (`sourceColumn`), pas de relation entrante/sortante porteuse de sens métier, et sa partition est généralement une table calculée technique (`= calculated`, `Row("Column", BLANK())`) servant uniquement de support à l'affichage des mesures dans le volet des champs.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nom exact donné à la ou aux tables de mesures (`MEASURE`, `_Measures`, `KPI`...) ;
- du nombre total de mesures dans le modèle ;
- du nombre de tables de faits et de dimensions ;
- de l'ordre des propriétés dans les fichiers TMDL.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_ADOPTION_QUESTION.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_CAMPAIGNS.tmdl
```

L'agent doit lire l'intégralité des fichiers du dossier `tables\`, car il doit établir la distribution complète des mesures par table avant de pouvoir juger de la centralisation.

---

## 3. Élément(s) / propriété(s) à contrôler

Pour chaque table, l'agent doit dénombrer :
1. le nombre de blocs `measure` ;
2. le nombre de blocs `column` porteurs de données (colonnes avec `sourceColumn` pointant vers une source réelle, hors colonne technique de support).

Exemple de table de mesures dédiée conforme, observée dans le projet :

```tmdl
table MEASURE
    lineageTag: b57b7d33-f0e2-4901-960e-dd3acbdd73cf

    measure pct_RespondentsPerUsage = ```...```
        displayFolder: USAGE

    measure Nb_Responses = COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN])
        displayFolder: CAMPAIGNS STATS

    column Column
        isHidden
        formatString: 0
        lineageTag: 2f82f6ae-2195-45d8-a738-beee9b45accc
        summarizeBy: none
        isNameInferred
        sourceColumn: [Column]

    partition MEASURE = calculated
        mode: import
        source = Row("Column", BLANK())
```

Ici, `MEASURE` contient un très grand nombre de mesures et une seule colonne (`Column`), qui est une colonne technique de support (masquée, générée automatiquement par la table calculée `Row("Column", BLANK())`) et non une colonne métier issue d'une source de données.

Exemple d'une mesure DAX présente dans une table de faits (situation à détecter comme non conforme si elle se généralise) :

```tmdl
table F_RESPONSES
    lineageTag: fde52b64-673f-4a83-bb84-6579745a9591

    column WORRY_LEVEL
        dataType: string
        sourceColumn: WORRY_LEVEL

    measure Total_Worry_Score = SUM(F_RESPONSES[WORRY_SCORE])
        formatString: 0
```

Dans cet exemple hypothétique, la mesure `Total_Worry_Score` est définie directement dans la table de faits `F_RESPONSES`, qui contient par ailleurs de vraies colonnes de données (`WORRY_LEVEL`, issue de `sourceColumn`).

---

## 4. Règle(s) d'évaluation

L'évaluation se fait à deux niveaux : par table (dispersion locale), puis globalement (taux de centralisation).

| Situation détectée | Statut | Interprétation |
|---|---|---|
| La table ne contient aucune colonne de données (uniquement la colonne technique de support) et regroupe des mesures | `OK` (table « mesures ») | Table dédiée conforme à la bonne pratique. |
| La table contient uniquement des colonnes de données et aucune mesure | `OK` (table « données ») | Séparation correcte entre données et calculs. |
| La table contient à la fois des colonnes de données réelles et une ou plusieurs mesures | `KO` | Mesure(s) dispersée(s) dans une table de faits/dimension au lieu d'être centralisée(s). |
| Le modèle ne comporte aucune mesure nulle part | `NA` | La règle ne s'applique pas (aucune mesure à organiser). |
| Le modèle comporte plusieurs tables « mesures » légitimement séparées par domaine (ex. `MEASURE_FINANCE`, `MEASURE_RH`) sans colonnes de données | `OK` | La centralisation n'impose pas une table unique, seulement l'absence de mélange mesures/données. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Si aucun fichier n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Construire l'inventaire par table
Pour chaque table : compter les mesures ; compter les colonnes de données réelles (exclure la colonne technique de support des tables calculées de type `Row("Column", BLANK())` lorsqu'elle est unique, masquée et sans usage en aval) ; enregistrer le couple `(nb_mesures, nb_colonnes_donnees)`.

### Étape 3 — Classifier chaque table
Pour chaque table, appliquer la règle de la section 4 : `KO` si `nb_mesures > 0` ET `nb_colonnes_donnees > 0` ; `OK` sinon.

### Étape 4 — Calculer les indicateurs globaux
Ne pas s'arrêter à la première table non conforme : parcourir la totalité des tables, produire la liste complète des tables `KO` avec, pour chacune, la liste des mesures concernées, et calculer le taux global de centralisation (`nombre de mesures situées dans une table dédiée / nombre total de mesures du modèle`).

### Étape 5 — Terminer l'analyse
Produire le nombre total de tables, de mesures, de tables `KO`, et le taux de centralisation global.

---

## 6. Détection robuste / normalisation

- Une table peut contenir des mesures définies sur une seule ligne ou encadrées de triples backticks : l'agent doit détecter les deux formats pour ne manquer aucune mesure.
- La colonne technique de support d'une table calculée de type mesures (`Row("Column", BLANK())`) doit être reconnue par un faisceau d'indices convergents, jamais par le seul nom : elle est `isHidden`, sa partition parente est de type `calculated` avec une source `Row(...)`, et elle porte l'annotation `isNameInferred`. Une colonne nommée `Column` mais réellement alimentée par une source de données (`sourceColumn` correspondant à une colonne physique dans une table `import`/`directQuery`) ne doit jamais être exemptée.
- Le nom de la ou des tables de mesures n'est jamais présupposé (`MEASURE`, `_Measures`, `KPI`, `Mesures`...) : la classification repose exclusivement sur la structure (présence de colonnes de données vs mesures), pas sur une convention de nommage.
- L'ordre des blocs `measure` et `column` dans le fichier TMDL est indifférent : l'agent doit les recenser tous, indépendamment de leur position.
- Les tables sans aucune mesure ni colonne de données (table vide, table paramètre pur) sont classées `NA` pour cette règle et ne comptent ni comme conformes ni comme non conformes.

```python
def is_technical_support_column(column, table):
    return (
        column.has_flag("isHidden")
        and column.has_flag("isNameInferred")
        and table.partition is not None
        and table.partition.kind == "calculated"
        and "Row(" in table.partition.source_expression
    )

def count_real_data_columns(table):
    return sum(
        1 for c in table.columns
        if not is_technical_support_column(c, table)
    )
```

---

## 7. Pseudo-code détaillé

```python
def analyze_measure_centralization(table_files):
    per_table_stats = []
    ko_tables = []
    total_measures = 0
    centralized_measures = 0

    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        nb_measures = len(table.measures)
        nb_data_columns = count_real_data_columns(table)

        total_measures += nb_measures

        if nb_measures == 0 and nb_data_columns == 0:
            status = "NA"
        elif nb_measures > 0 and nb_data_columns > 0:
            status = "KO"
            ko_tables.append({
                "table": table.name,
                "measures": [m.name for m in table.measures],
                "nb_data_columns": nb_data_columns,
                "reason": "Mesures mêlées à des colonnes de données réelles",
            })
        else:
            status = "OK"
            if nb_measures > 0:
                centralized_measures += nb_measures

        per_table_stats.append({
            "table": table.name, "nb_measures": nb_measures,
            "nb_data_columns": nb_data_columns, "status": status,
        })

    if total_measures == 0:
        return {"rule_status": "NA", "reason": "Aucune mesure dans le modèle"}

    centralization_rate = centralized_measures / total_measures

    return {
        "per_table_stats": per_table_stats,
        "ko_tables": ko_tables,
        "total_measures": total_measures,
        "centralized_measures": centralized_measures,
        "centralization_rate": centralization_rate,
    }
```

---

## 8. Calcul du statut global

```python
if ko_tables:
    rule_status = "KO"
elif total_measures == 0:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK`. Une seule table mélangeant mesures et colonnes de données suffit à faire basculer la règle en `KO`, quel que soit le taux global de centralisation, car chaque mesure mal placée constitue une non-conformité individuellement actionnable.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les mesures sont dans une ou plusieurs tables sans colonnes de données | `OK` |
| Au moins une table mélange mesures et colonnes de données | `KO` |
| Aucune mesure dans tout le modèle | `NA` |

---

## 9. Structure du résultat

Exemple `OK` (état actuel du projet audité) :

```json
{
  "rule_id": "BP-24",
  "rule_name": "Centralisation des mesures dans une ou des tables dédiées",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_tables": 15,
  "total_measures": 34,
  "centralized_measures": 34,
  "centralization_rate": 1.0,
  "ko_tables": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-24",
  "rule_name": "Centralisation des mesures dans une ou des tables dédiées",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_tables": 15,
  "total_measures": 36,
  "centralized_measures": 34,
  "centralization_rate": 0.944,
  "ko_tables": [
    {
      "table": "F_RESPONSES",
      "measures": ["Total_Worry_Score", "Avg_Interest_Score"],
      "nb_data_columns": 22,
      "reason": "Mesures mêlées à des colonnes de données réelles"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-24 — Centralisation des mesures dans une ou des tables dédiées : OK

34 mesures détectées dans le modèle, toutes centralisées dans la table MEASURE
qui ne contient aucune colonne de données métier. Taux de centralisation : 100 %.
```

### Exemple `KO`

```text
BP-24 — Centralisation des mesures dans une ou des tables dédiées : KO

34 mesures sur 36 sont correctement centralisées dans MEASURE (taux 94,4 %).

Table non conforme :
- F_RESPONSES contient 2 mesures (Total_Worry_Score, Avg_Interest_Score) alors
  qu'elle porte 22 colonnes de données réelles issues de la source.

Correction attendue :
déplacer les mesures Total_Worry_Score et Avg_Interest_Score depuis
F_RESPONSES vers la table MEASURE (ou toute autre table dédiée sans colonnes
de données), en conservant leur définition DAX, leur formatString et leur
displayFolder.
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus ;
- chaque mesure du modèle, quel que soit son format d'écriture (ligne unique ou triple backticks), a été comptabilisée dans sa table d'origine ;
- chaque colonne de chaque table a été examinée pour distinguer colonne de données réelle et colonne technique de support ;
- la colonne technique de support n'a été exemptée qu'après vérification du faisceau d'indices complet (masquée, `isNameInferred`, partition calculée `Row(...)`), jamais sur la seule base de son nom ;
- aucune table n'a été omise de l'inventaire, y compris les tables sans mesure ;
- le taux de centralisation a été calculé sur l'ensemble des mesures du modèle, pas sur un sous-ensemble.

---

## 12. Résumé de la règle

```text
RÈGLE BP-24

POUR chaque table du modèle sémantique
    COMPTER les mesures (measure)
    COMPTER les colonnes de données réelles (exclure colonne technique de support)

    SI nb_mesures > 0 ET nb_colonnes_donnees > 0
        table = KO (mesures dispersées)
    SINON SI nb_mesures = 0 ET nb_colonnes_donnees = 0
        table = NA
    SINON
        table = OK
    ENREGISTRER le résultat
FIN POUR

SI aucune mesure dans tout le modèle
    règle = NA
SINON SI au moins une table KO
    règle = KO
SINON
    règle = OK

AFFICHER toutes les tables KO avec la liste des mesures à déplacer
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-24 — Centralisation des mesures dans une ou        │
│         des tables dédiées                                    │
└────────────────────────┬───────────────────────────────────────┘
                          ▼
           ┌───────────────────────────────┐
           │ Lister tables\*.tmdl            │
           └───────────────┬─────────────────┘
                ┌────────────┴────────────┐
                ▼                          ▼
          ╔═════════════╗          ┌───────────────┐
          ║ Fichiers    ║          │ Aucun fichier  │
          ║ trouvés ✅  ║          │ trouvé ❌       │
          ╚══════╤══════╝          └───────┬────────┘
                 │                          ▼
                 │                  ┌────────────────┐
                 │                  │ Retour :        │
                 │                  │ NON_EVALUE      │
                 │                  └────────────────┘
                 ▼
     ┌───────────────────────────────────────────┐
     │ POUR chaque table du modèle                 │
     │  (boucle sur toutes les tables)              │
     └───────────────────────┬───────────────────────┘
                             ▼
            ┌────────────────────────────────────┐
            │ COMPTER nb_mesures (measure)         │
            │ COMPTER nb_colonnes_données réelles   │
            │ (exclure colonne technique support)   │
            └──────────────────┬────────────────────┘
                               ▼
                 ┌──────────────────────────────┐
                 │ nb_mesures > 0 ET              │
                 │ nb_colonnes_données > 0 ?      │
                 └───────────────┬────────────────┘
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
        ╔═════════╗        ┌────────────┐       ┌────────────┐
        ║ OUI ❌  ║        │ Les deux   │       │ Un seul    │
        ╚════╤════╝        │ = 0        │       │ > 0        │
             ▼              └─────┬──────┘       └─────┬──────┘
    ┌────────────────┐            ▼                    ▼
    │ table = KO       │    ┌────────────┐       ┌────────────┐
    │ (mesures         │    │ table = NA │       │ table = OK │
    │  dispersées)      │    └────────────┘       └────────────┘
    └────────────────┘
                 │ (répéter pour chaque table, sans s'arrêter)
                 ▼
     ┌────────────────────────────────────────┐
     │ Fin du parcours : toutes les tables      │
     │ classées, total_measures cumulé          │
     └───────────────────┬───────────────────────┘
                         ▼
            ┌──────────────────────────┐
            │ Au moins une table KO ?   │
            └──────────────┬─────────────┘
              ┌──────────────┴──────────────┐
              ▼                              ▼
        ╔═════════╗                    ┌────────────┐
        ║ OUI ❌  ║                    │ NON        │
        ╚════╤════╝                    └──────┬─────┘
             ▼                                 ▼
      ┌─────────────┐              ┌────────────────────────┐
      │ règle = KO   │              │ total_measures = 0 ?     │
      └─────────────┘              └────────────┬──────────────┘
                                    ┌──────────────┴──────────────┐
                                    ▼                              ▼
                              ╔═════════╗                    ┌────────────┐
                              ║ OUI     ║                    │ NON ✅     │
                              ╚════╤════╝                    └──────┬─────┘
                                   ▼                                ▼
                            ┌─────────────┐                 ┌─────────────┐
                            │ règle = NA   │                 │ règle = OK   │
                            └─────────────┘                 └─────────────┘
                                        │
                                        ▼
                              RETOUR rule_status
                              (OK / KO / NA)
```
