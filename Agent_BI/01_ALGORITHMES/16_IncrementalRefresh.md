# BP-16 — Actualisation incrémentielle des tables de faits volumineuses

## 1. Objectif de la bonne pratique

L'actualisation incrémentielle (« incremental refresh ») permet de ne recharger, à chaque cycle d'actualisation, que les partitions récentes d'une table volumineuse (par exemple les 30 derniers jours), au lieu de retraiter l'intégralité de l'historique à chaque exécution. Dans un projet PBIP au format TMDL, cette politique est décrite par un bloc `incrementalPolicy` attaché à la table, combiné à deux paramètres M spéciaux nommés `RangeStart` et `RangeEnd` utilisés comme bornes de filtrage dans la requête source de la table.

L'objectif de cette règle est de vérifier que les **tables de faits volumineuses** du modèle (généralement préfixées `F_` dans les conventions de nommage de ce projet, cf. [BP-21](21_ConciseNames.md)) disposent d'une politique d'actualisation incrémentielle configurée, plutôt que d'un rechargement complet à chaque actualisation, dès lors que leur volume de données le justifie.

Un point essentiel doit être souligné : **le volume d'une table (nombre de lignes, taille) n'est pas une information disponible dans les fichiers TMDL statiques**. Le modèle sémantique décrit la structure (colonnes, relations, code M), pas les données elles-mêmes. Cette règle doit donc s'appuyer sur une source de volumétrie externe (export de cardinalité, requête `COUNTROWS` exécutée via XMLA/ADOMD, historique de durée d'actualisation, ou seuil déclaré par l'équipe data) fournie en complément des fichiers TMDL. Sans cette information, l'agent ne peut pas conclure de façon fiable qu'une table est « volumineuse » et doit le signaler explicitement plutôt que de deviner.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables de faits du modèle ;
- du connecteur source (SQL, Databricks, fichier plat...) — l'actualisation incrémentielle nécessite toutefois un mode `import` (ou `hybride`/`directLake` avec partitions gérées), elle ne s'applique pas à une table entièrement en `directQuery` ;
- du seuil de volumétrie retenu, qui doit être un paramètre configurable et non une valeur codée en dur.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl          (bloc incrementalPolicy, mode de la table)
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl        (paramètres RangeStart / RangeEnd)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_ADOPTION_QUESTION.tmdl
```

En complément, l'agent doit recevoir en entrée un **extrait de volumétrie** (fourni par l'équipe d'audit, hors périmètre des fichiers TMDL), par exemple sous la forme suivante :

```json
{
  "F_RESPONSES": {"row_count": 4830, "growth_rate_per_month": "faible"},
  "F_ADOPTION_QUESTION": {"row_count": 12100, "growth_rate_per_month": "faible"}
}
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1 Bloc `incrementalPolicy` attendu sur une table conforme

```tmdl
table F_SALES
    lineageTag: ...

    column ORDER_DATE
        dataType: dateTime
        ...

    partition F_SALES = m
        mode: import
        source =
                let
                    Source = Sql.Database("server", "database"),
                    #"Filtered Rows" = Table.SelectRows(Source,
                        each [ORDER_DATE] >= RangeStart and [ORDER_DATE] < RangeEnd)
                in
                    #"Filtered Rows"

    incrementalPolicy
        policyType: basic
        incrementalPeriod: 1
        incrementalPeriodType: years
        rollingWindowPeriod: 3
        rollingWindowGranularity: years
        detectDataChanges: false
```

### 3.2 Paramètres M `RangeStart` / `RangeEnd`

```tmdl
expression RangeStart = #datetime(2023, 1, 1, 0, 0, 0) meta [IsParameterQuery=true, Type="DateTime", IsParameterQueryRequired=true]
expression RangeEnd = #datetime(2024, 1, 1, 0, 0, 0) meta [IsParameterQuery=true, Type="DateTime", IsParameterQueryRequired=true]
```

Ces deux paramètres doivent impérativement porter exactement ces noms (`RangeStart` et `RangeEnd`, sensibles à la casse) pour que Power BI reconnaisse la politique d'actualisation incrémentielle, et doivent être utilisés comme bornes de filtrage sur une colonne de type date/heure dans la requête source de la table concernée (`Table.SelectRows(Source, each [DATE_COL] >= RangeStart and [DATE_COL] < RangeEnd)`).

### 3.3 État réel du projet audité

Les fichiers `F_RESPONSES.tmdl` et `F_ADOPTION_QUESTION.tmdl` de ce projet ne comportent, à ce jour, ni bloc `incrementalPolicy`, ni référence à `RangeStart`/`RangeEnd` dans leur partition M. Sans extrait de volumétrie externe confirmant que ces tables dépassent le seuil justifiant une actualisation incrémentielle, l'agent ne peut conclure ni `OK` ni `KO` de façon fiable sur ce projet : le statut correct est `NA`, avec la raison explicite « information de volumétrie non fournie ».

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Table de mode `import`, volumétrie fournie et **supérieure** au seuil, `incrementalPolicy` présent et paramètres `RangeStart`/`RangeEnd` correctement utilisés dans la partition | `OK` | Actualisation incrémentielle correctement configurée pour une table volumineuse. |
| Table de mode `import`, volumétrie fournie et supérieure au seuil, `incrementalPolicy` absent | `KO` | Table volumineuse rechargée intégralement à chaque actualisation. |
| Table de mode `import`, `incrementalPolicy` présent mais `RangeStart`/`RangeEnd` absents ou non utilisés dans le filtre de la partition | `KO` | Politique déclarée mais non fonctionnelle (incohérence de configuration). |
| Table de mode `import`, volumétrie fournie et **inférieure** au seuil | `NA` | Le volume ne justifie pas une actualisation incrémentielle ; le rechargement complet reste acceptable. |
| Table en `directQuery` intégral (aucune partition `import`) | `NA` | L'actualisation incrémentielle ne s'applique pas à ce mode de stockage. |
| Volumétrie non fournie pour la table analysée | `NA` | Impossible de déterminer si le seuil est dépassé ; la règle ne peut pas être évaluée sans deviner. |

Exemple avec un seuil de volumétrie fixé à 5 000 000 de lignes (paramètre configurable) :

| Table | Mode | Lignes (fourni) | `incrementalPolicy` | `RangeStart`/`RangeEnd` utilisés | Statut |
|---|---|---|---|---|---|
| `F_RESPONSES` | import | 4 830 | absent | — | `NA` (sous le seuil) |
| `F_ADOPTION_QUESTION` | import | 12 100 | absent | — | `NA` (sous le seuil) |
| *(hypothèse)* `F_SALES` | import | 42 000 000 | absent | — | `KO` |
| *(hypothèse)* `F_SALES_V2` | import | 42 000 000 | présent | oui | `OK` |
| *(hypothèse)* `F_EVENTS` | directQuery | non applicable | — | — | `NA` |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Charger `expressions.tmdl` s'il existe, pour identifier les paramètres `RangeStart`/`RangeEnd` déclarés au niveau du modèle.
3. Charger l'extrait de volumétrie externe fourni en entrée d'audit. Si cet extrait est totalement absent, l'agent doit terminer l'exécution avec un statut global `NA` documenté pour l'ensemble des tables, plutôt que de supposer un volume.

### Étape 2 — Filtrer les tables candidates
Ne retenir que les tables dont le mode de partition contient au moins une partition `import` (les tables 100 % `directQuery` sont écartées avec `NA` immédiat).

### Étape 3 — Croiser avec la volumétrie
Pour chaque table candidate, rechercher son volume dans l'extrait fourni. Si absent, marquer `NA` avec la raison « volumétrie non fournie » et passer à la table suivante — sans arrêter l'analyse des autres tables.

### Étape 4 — Vérifier la configuration de la politique
Pour chaque table dont le volume dépasse le seuil : rechercher le bloc `incrementalPolicy` ; si présent, vérifier que la partition M utilise bien `RangeStart` et `RangeEnd` comme bornes de filtre sur une colonne date ; appliquer la règle de décision de la section 4.

### Étape 5 — Terminer l'analyse
Produire, pour toutes les tables de faits analysées : le statut individuel, le volume utilisé pour la décision, la présence ou l'absence du bloc `incrementalPolicy`, et la liste complète des tables `KO`.

---

## 6. Détection robuste / normalisation

- Le bloc `incrementalPolicy` peut apparaître à différents endroits dans le fichier de table TMDL (avant ou après les définitions de colonnes ou de partitions) : l'agent doit le rechercher dans l'ensemble du fichier `table <NOM>.tmdl`, pas uniquement à la fin.
- Les propriétés internes du bloc (`policyType`, `incrementalPeriod`, `incrementalPeriodType`, `rollingWindowPeriod`, `rollingWindowGranularity`, `detectDataChanges`) peuvent apparaître dans un ordre quelconque : seule la présence du bloc et sa cohérence fonctionnelle avec `RangeStart`/`RangeEnd` comptent pour cette règle, pas l'ordre de ses sous-propriétés.
- Les noms `RangeStart` et `RangeEnd` sont sensibles à la casse et ne doivent jamais être confondus avec des noms de colonnes métier similaires (`START_DATE`, `RANGE_START_DATE`...) : seule la correspondance exacte de nom compte.
- Une table peut comporter plusieurs partitions M (partitions historiques matérialisées en plus de la partition incrémentielle) : la présence de plusieurs blocs `partition <NOM> = m` sous une même table, combinée à un bloc `incrementalPolicy`, est le signe attendu d'une politique active et ne doit pas être interprétée comme une anomalie de duplication.
- Le seuil de volumétrie doit toujours être traité comme un paramètre configurable de l'audit (`LARGE_TABLE_ROW_THRESHOLD`), jamais comme une constante figée dans le pseudo-code, car il varie selon le contexte (matériel, licence Power BI, tolérance métier au temps d'actualisation).
- Si l'extrait de volumétrie fourni est partiel (certaines tables absentes), seules les tables couvertes sont évaluées ; les autres sont marquées `NA` avec la raison explicite, sans jamais être comptées comme `OK` par défaut.

---

## 7. Pseudo-code détaillé

```python
LARGE_TABLE_ROW_THRESHOLD = 5_000_000  # paramètre configurable, fourni par le contexte d'audit

def table_has_only_directquery(table):
    return all(p.mode == "directQuery" for p in table.partitions)

def has_incremental_policy(table):
    return table.get_block("incrementalPolicy") is not None

def uses_range_parameters_correctly(table):
    for partition in table.partitions:
        if partition.mode != "import":
            continue
        filter_steps = find_steps_using_identifiers(partition.source_expression, {"RangeStart", "RangeEnd"})
        if filter_steps:
            return True
    return False

def evaluate_table_incremental_refresh(table, volumetry_extract, threshold):
    if table_has_only_directquery(table):
        return {"table": table.name, "status": "NA", "reason": "Table entièrement en DirectQuery"}

    volume = volumetry_extract.get(table.name)
    if volume is None:
        return {"table": table.name, "status": "NA", "reason": "Volumétrie non fournie pour cette table"}

    row_count = volume["row_count"]
    if row_count < threshold:
        return {"table": table.name, "status": "NA", "row_count": row_count,
                "reason": f"Volume ({row_count}) sous le seuil ({threshold})"}

    if not has_incremental_policy(table):
        return {"table": table.name, "status": "KO", "row_count": row_count,
                "reason": "Table volumineuse sans politique d'actualisation incrémentielle"}

    if not uses_range_parameters_correctly(table):
        return {"table": table.name, "status": "KO", "row_count": row_count,
                "reason": "incrementalPolicy présent mais RangeStart/RangeEnd non utilisés dans le filtre de partition"}

    return {"table": table.name, "status": "OK", "row_count": row_count}


ok_results, ko_results, na_results = [], [], []

table_files = find_all_tmdl_files("<SEMANTIC_MODEL_PATH>/definition/tables/")
if not table_files:
    return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
            "reason": "Aucun fichier de table TMDL trouvé"}

volumetry_extract = load_external_volumetry_extract()   # fourni par le contexte d'audit
if volumetry_extract is None:
    return {"execution_status": "PARTIAL", "rule_status": "NA",
            "reason": "Aucun extrait de volumétrie fourni : impossible d'évaluer cette règle sans deviner"}

for table_file in table_files:
    table = parse_tmdl_table(table_file)
    result = evaluate_table_incremental_refresh(table, volumetry_extract, LARGE_TABLE_ROW_THRESHOLD)
    {"OK": ok_results, "KO": ko_results, "NA": na_results}[result["status"]].append(result)
```

---

## 8. Calcul du statut global

```python
if ko_results:
    rule_status = "KO"
elif na_results and not ok_results:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les tables volumineuses ont une politique incrémentielle fonctionnelle | `OK` |
| Au moins une table volumineuse n'a pas de politique, ou une politique mal câblée | `KO` |
| Aucune table ne dépasse le seuil, ou volumétrie non fournie | `NA` |

---

## 9. Structure du résultat

Exemple `NA` (état actuel du projet audité, sans extrait de volumétrie confirmé dépassant le seuil) :

```json
{
  "rule_id": "BP-16",
  "rule_name": "Actualisation incrémentielle des tables de faits volumineuses",
  "execution_status": "SUCCESS",
  "rule_status": "NA",
  "threshold_row_count": 5000000,
  "total_fact_tables": 2,
  "ok_tables": 0,
  "ko_tables": 0,
  "na_tables": 2,
  "na_details": [
    {"table": "F_RESPONSES", "row_count": 4830, "reason": "Volume (4830) sous le seuil (5000000)"},
    {"table": "F_ADOPTION_QUESTION", "row_count": 12100, "reason": "Volume (12100) sous le seuil (5000000)"}
  ]
}
```

Exemple `KO` (scénario hypothétique avec une table volumineuse) :

```json
{
  "rule_id": "BP-16",
  "rule_name": "Actualisation incrémentielle des tables de faits volumineuses",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "threshold_row_count": 5000000,
  "total_fact_tables": 3,
  "ok_tables": 0,
  "ko_tables": 1,
  "na_tables": 2,
  "ko_details": [
    {"table": "F_SALES", "row_count": 42000000,
     "reason": "Table volumineuse sans politique d'actualisation incrémentielle"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `NA`

```text
BP-16 — Actualisation incrémentielle : NON APPLICABLE

2 tables de faits analysées (F_RESPONSES : 4 830 lignes, F_ADOPTION_QUESTION :
12 100 lignes). Aucune ne dépasse le seuil de volumétrie retenu (5 000 000
lignes) : le rechargement complet reste acceptable, une actualisation
incrémentielle n'apporterait pas de gain significatif à ce stade.
```

### Exemple `KO`

```text
BP-16 — Actualisation incrémentielle : KO

1 table non conforme sur 1 table volumineuse identifiée.

Table non conforme :
- F_SALES : 42 000 000 lignes, aucune politique d'actualisation
  incrémentielle configurée (pas de bloc incrementalPolicy, pas de
  paramètres RangeStart/RangeEnd dans la requête source). Chaque
  actualisation recharge l'intégralité de l'historique.

Correction attendue :
créer les paramètres RangeStart et RangeEnd (type DateTime) dans Power
Query, filtrer la partition source sur ces bornes, puis configurer la
politique d'actualisation incrémentielle (période incrémentielle et
fenêtre glissante) dans les paramètres de la table via Power BI Desktop.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- tous les fichiers de tables ont été lus ;
- un extrait de volumétrie externe a été fourni et couvre les tables de faits analysées ;
- le seuil de volumétrie utilisé est explicite et documenté dans le résultat ;
- pour chaque table dépassant le seuil, la présence du bloc `incrementalPolicy` a été vérifiée ;
- pour chaque table avec `incrementalPolicy`, l'utilisation effective de `RangeStart` et `RangeEnd` comme filtre dans la partition source a été confirmée, pas seulement la présence du bloc de politique ;
- aucune table volumineuse n'a été omise de l'analyse.

L'agent ne doit jamais produire `OK` en l'absence d'extrait de volumétrie, ni en présence d'un bloc `incrementalPolicy` dont les paramètres `RangeStart`/`RangeEnd` ne sont pas réellement utilisés comme filtre dans la partition.

---

## 12. Résumé de la règle

```text
RÈGLE BP-16

CHARGER l'extrait de volumétrie externe (obligatoire)
SI absent
    règle = NA (impossible d'évaluer sans volumétrie)
    ARRÊTER

POUR chaque table du modèle
    SI la table est entièrement en DirectQuery
        table = NA
        CONTINUER

    RÉCUPÉRER le volume de la table depuis l'extrait
    SI volume absent
        table = NA (volumétrie non fournie)
        CONTINUER
    SI volume < seuil configuré
        table = NA (sous le seuil)
        CONTINUER

    SI incrementalPolicy absent
        table = KO
    SINON SI RangeStart/RangeEnd non utilisés dans le filtre de la partition
        table = KO
    SINON
        table = OK

    ENREGISTRER le résultat avec le volume utilisé pour la décision
FIN POUR

SI au moins une table KO
    règle = KO
SINON SI aucune table au-dessus du seuil
    règle = NA
SINON
    règle = OK

AFFICHER toutes les tables KO avec recommandation de configuration
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-16 — Actualisation incrémentielle des tables de faits    │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ Lister tables/*.tmdl                     │
          │ Charger expressions.tmdl                 │
          │ CHARGER l'extrait de volumétrie externe  │
          └────────────────┬───────────────────────────┘
               ┌───────────┴───────────┐
               ▼                       ▼
         ╔═════════════╗       ┌──────────────────┐
         ║ Extrait     ║       │ Extrait absent ❌   │
         ║ fourni ✅   ║       └─────────┬──────────┘
         ╚══════╤══════╝                 ▼
                │                ┌────────────────┐
                │                │ Retour global : │
                │                │ règle = NA       │
                │                │ (ARRÊTER)        │
                │                └────────────────┘
                ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque table du modèle (boucle)        │
     └────────────────┬────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ Table 100% directQuery ?        │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ┌──────────┐   ┌──────────────┐
       │ OUI = NA │   │ NON (import)   │
       └──────────┘   └──────┬────────┘
                             ▼
                  ┌───────────────────────┐
                  │ Volume trouvé dans       │
                  │ l'extrait ?              │
                  └──────────┬─────────────────┘
                       ┌──────┴──────┐
                       ▼             ▼
                 ┌──────────┐  ┌──────────────┐
                 │ NON = NA │  │ OUI             │
                 └──────────┘  └──────┬──────────┘
                                      ▼
                          ┌───────────────────────┐
                          │ volume < seuil            │
                          │ (LARGE_TABLE_ROW_         │
                          │ THRESHOLD) ?               │
                          └──────────┬─────────────────┘
                               ┌──────┴──────┐
                               ▼             ▼
                         ┌──────────┐  ┌──────────────┐
                         │ OUI = NA │  │ NON (>= seuil) │
                         └──────────┘  └──────┬──────────┘
                                              ▼
                                  ┌───────────────────────┐
                                  │ Bloc incrementalPolicy    │
                                  │ présent ?                  │
                                  └──────────┬─────────────────┘
                                       ┌──────┴──────┐
                                       ▼             ▼
                                 ╔═══════════╗ ┌──────────────┐
                                 ║ NON = KO  ║ │ OUI             │
                                 ╚═══════════╝ └──────┬──────────┘
                                                      ▼
                                          ┌──────────────────────┐
                                          │ RangeStart/RangeEnd      │
                                          │ utilisés comme filtre    │
                                          │ de la partition ?        │
                                          └──────────┬─────────────────┘
                                               ┌──────┴──────┐
                                               ▼             ▼
                                         ╔═══════════╗ ┌──────────┐
                                         ║ NON = KO  ║ │ OUI = OK  │
                                         ╚═══════════╝ └──────────┘
                                               │             │
                                               └──────┬──────┘
                                                      ▼
                                    FIN DE BOUCLE (table suivante)
                                                      │
                                                      ▼
                    ┌────────────────────────────────────────────┐
                    │ CALCUL DU RÉSULTAT FINAL                      │
                    │ KO présent ?              → règle = KO         │
                    │ Sinon NA seul (aucun OK)  → règle = NA         │
                    │ Sinon                      → règle = OK        │
                    └────────────────────┬───────────────────────────┘
                                         ▼
                         RETOUR rule_status (OK/KO/NA)
```
