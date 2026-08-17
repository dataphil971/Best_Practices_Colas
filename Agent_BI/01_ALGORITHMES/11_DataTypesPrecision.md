# BP-11 — Vérifier les types de données et la précision numérique des colonnes

## 1. Objectif de la bonne pratique

Le type de données déclaré d'une colonne dans le modèle sémantique (`dataType` en TMDL) doit correspondre au besoin métier réel de cette colonne, et pas seulement au type détecté automatiquement par Power Query lors de l'import. Deux écarts fréquents dégradent la qualité et la performance du modèle : d'une part, l'usage du type **`double`** (virgule flottante) pour des valeurs qui sont en réalité des entiers (compteurs, identifiants, années) ou qui nécessitent une précision décimale fixe (montants financiers, scores sur une échelle définie) — le type `double` est plus coûteux à stocker et introduit un risque d'erreurs d'arrondi lors des agrégations DAX ; d'autre part, l'absence de `formatString` cohérent avec le type et l'usage réel de la colonne, qui nuit à la lisibilité dans les visuels sans pour autant constituer une non-conformité de même gravité que le typage lui-même.

L'objectif de cette règle est de comparer, pour chaque colonne numérique du modèle, le `dataType` déclaré au besoin métier inféré à partir du nom de la colonne, de son usage (agrégation, clé, mesure) et, lorsque c'est possible, de la nature réelle des valeurs observées (valeurs toutes entières malgré un typage `double`), afin de signaler les colonnes pour lesquelles un type plus adapté (`int64`, ou une précision décimale fixe) devrait être utilisé.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables et de colonnes numériques ;
- du nom des tables et des colonnes ;
- du connecteur source (SharePoint, Databricks, fichier plat...) ;
- de l'ordre des propriétés dans les fichiers TMDL.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_CAMPAIGNS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
```

L'agent doit charger l'ensemble des fichiers `tables/*.tmdl` et analyser chaque colonne dont le `dataType` appartient à une catégorie numérique (`int64`, `double`, `decimal`).

---

## 3. Élément(s) / propriété(s) à contrôler

Colonne réelle du modèle audité, correctement typée en entier :

```tmdl
column CAMPAIGN_TOTAL_SAMPLE_SIZE
	dataType: int64
	formatString: 0
	lineageTag: 18a20768-b290-4cf3-8db2-62dbea443384
	summarizeBy: none
	sourceColumn: CAMPAIGN_TOTAL_SAMPLE_SIZE

	annotation SummarizationSetBy = User
```

`CAMPAIGN_TOTAL_SAMPLE_SIZE` (taille d'échantillon d'une campagne, une valeur nécessairement entière) est typée `int64` avec un `formatString: 0` (aucune décimale affichée) — conforme au besoin métier.

Cas non conforme hypothétique, construit par analogie avec les colonnes de score du modèle (`KNOWLEDGE_SCORE`, `USAGE_SCORE`, qui sont par nature des compteurs entiers) :

```tmdl
column KNOWLEDGE_SCORE
	dataType: double
	formatString: General Number
	lineageTag: <guid>
	summarizeBy: sum
	sourceColumn: KNOWLEDGE_SCORE
```

Un score cumulé de connaissances, calculé par `List.Sum` sur des indicateurs 0/1 en Power Query (cf. `F_SCORERESPONSES` dans `expressions.tmdl`, étape `Calculated Total Knowledge Score` suivie de `Table.TransformColumnTypes(..., {{"SCORE_TOTAL", Int64.Type}})`), ne devrait jamais être typé `double` : la transformation M elle-même confirme l'intention entière via `Int64.Type`.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `D_CAMPAIGNS[CAMPAIGN_TOTAL_SAMPLE_SIZE]`, `dataType: int64`, `formatString: 0` | `OK` | Type entier cohérent avec une taille d'échantillon. |
| `F_RESPONSES[INTEREST_LEGEND_ORDER]`, `dataType: int64`, `formatString: 0`, usage d'ordre de tri | `OK` | Type entier cohérent avec un indice d'ordre. |
| Colonne hypothétique `F_SCORERESPONSES[SCORE_TOTAL]`, `dataType: double`, alors que le code M applique `Int64.Type` avant le chargement | `KO` | Incohérence entre l'intention de typage en amont (Power Query) et le typage déclaré au niveau du modèle. |
| Colonne hypothétique `F_SALES[UNIT_PRICE]`, `dataType: double`, valeurs métier réellement décimales à 2 chiffres (montant financier) | `WARN` | Type flottant utilisé pour un montant financier : un type `decimal`/`fixed decimal number` à précision fixe serait préférable pour éviter les erreurs d'arrondi cumulées, sans que `double` soit strictement interdit. |
| Colonne hypothétique `F_EVENTS[EVENT_YEAR]`, `dataType: double`, valeurs toujours entières (2023, 2024, 2025) | `KO` | Colonne discrète par nature (année), typée en flottant sans raison. |
| Colonne non numérique (`string`, `dateTime`, `boolean`) | `NA` | Hors périmètre de cette règle, qui porte exclusivement sur les colonnes numériques. |
| `dataType` absent ou illisible | `NA` | Impossible de conclure. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables/*.tmdl`.
2. Extraire toutes les colonnes de toutes les tables.
3. Si aucun fichier n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Filtrer les colonnes numériques
Ne conserver que les colonnes dont le `dataType` est `int64`, `double` ou `decimal` ; les autres types sont classés `NA` d'emblée et ne participent pas au calcul du statut global.

### Étape 3 — Inférer le besoin métier de chaque colonne numérique
Pour chaque colonne : analyser le nom (suffixes évocateurs `_SCORE`, `_COUNT`, `_NUMBER`, `_ORDER`, `_YEAR`, `_ID` pour un besoin entier ; `_PRICE`, `_AMOUNT`, `_RATE`, `_PCT` pour un besoin de précision décimale fixe) ; rechercher, si la colonne provient d'une transformation M visible dans la partition ou une expression partagée, une conversion de type explicite (`Int64.Type`, `Currency.Type`, `type number`) qui révèle l'intention réelle du concepteur du flux.

### Étape 4 — Appliquer la grille de décision
Comparer le `dataType` déclaré à l'intention inférée et classer la colonne `OK`, `WARN` ou `KO` selon la sévérité de l'écart (voir section 6).

### Étape 5 — Ne pas s'arrêter à la première colonne non conforme
L'agent analyse l'intégralité des colonnes numériques de toutes les tables.

### Étape 6 — Terminer l'analyse
Produire : le nombre total de colonnes numériques analysées ; le nombre de colonnes `OK`/`WARN`/`KO`/`NA` ; la liste détaillée des colonnes `KO` et `WARN` avec le type constaté, le type recommandé et la justification.

---

## 6. Détection robuste / normalisation

**Classification par suffixe de nom** — l'agent applique une correspondance de motifs, insensible à la casse, pour émettre une hypothèse de besoin métier :

```python
INTEGER_NAME_HINTS = re.compile(r"(_SCORE|_COUNT|_NUMBER|_ORDER|_YEAR|_AGE|_QUANTITY|_RANK|_LEVEL)$", re.I)
FIXED_DECIMAL_NAME_HINTS = re.compile(r"(_PRICE|_AMOUNT|_COST|_RATE|_PCT|_PERCENTAGE|_TOTAL_AMOUNT)$", re.I)
```

Cette classification par nom est une **heuristique de première intention**, jamais suffisante à elle seule pour conclure `KO` : elle doit être corroborée soit par une conversion de type explicite trouvée dans le code M source, soit par l'observation d'un échantillon de valeurs (si disponible) démontrant que toutes les valeurs observées sont entières malgré un typage `double`.

```python
def sample_confirms_integer(sample_values):
    if not sample_values:
        return None  # indéterminé, ne pas conclure sur ce seul critère
    return all(float(v).is_integer() for v in sample_values if v is not None)
```

**Recherche de la conversion M d'origine** — l'agent recherche, dans le code M de la partition ou de l'expression alimentant la table, un appel `Table.TransformColumnTypes` mentionnant la colonne avec un type cible entier ou monétaire, y compris si ce typage a ensuite été « élargi » côté modèle :

```python
def find_upstream_type_intent(column_name, m_code):
    pattern = re.compile(
        r'\{"' + re.escape(column_name) + r'",\s*(Int64\.Type|Currency\.Type|Number\.Type|type\s+number)\}',
        re.I,
    )
    match = pattern.search(m_code or "")
    return match.group(1) if match else None
```

**Distinction `KO` / `WARN`** : un écart entre un typage `double` et un besoin manifestement entier (nom + conversion M confirmée, ou échantillon entièrement entier) est classé `KO` — c'est un typage objectivement inadapté. Un écart entre `double` et un besoin de précision décimale fixe (montant financier) est classé `WARN` — `double` reste techniquement fonctionnel pour ce cas, la recommandation d'un type à précision fixe est une amélioration, pas une non-conformité bloquante.

**Gestion des colonnes calculées DAX** : une colonne calculée (mesure de type colonne, `column ... = <expression DAX>`) hérite d'un type déduit par le moteur ; l'agent doit également la contrôler si son `dataType` est explicite dans le TMDL, mais ne doit pas tenter d'inférer un typage M amont pour ce type de colonne (il n'existe pas).

---

## 7. Pseudo-code détaillé

```python
NUMERIC_TYPES = {"int64", "double", "decimal"}

def infer_expected_precision(column_name, upstream_m_type, sample_values):
    if upstream_m_type and "int64" in upstream_m_type.lower():
        return "INTEGER_CONFIRMED"
    if INTEGER_NAME_HINTS.search(column_name):
        confirmation = sample_confirms_integer(sample_values)
        return "INTEGER_CONFIRMED" if confirmation else "INTEGER_SUSPECTED"
    if FIXED_DECIMAL_NAME_HINTS.search(column_name):
        return "FIXED_DECIMAL_SUSPECTED"
    return "UNKNOWN"


def evaluate_numeric_column(table, column, m_code, sample_values):
    raw_type = normalize_datatype(column.get_property("dataType"))
    if raw_type not in NUMERIC_TYPES:
        return {"table": table.name, "column": column.name, "status": "NA",
                "reason": "Colonne non numérique, hors périmètre"}

    upstream_type = find_upstream_type_intent(column.source_column or column.name, m_code)
    expectation = infer_expected_precision(column.name, upstream_type, sample_values)

    if raw_type == "int64":
        return {"table": table.name, "column": column.name, "status": "OK"}

    if raw_type in {"double", "decimal"}:
        if expectation == "INTEGER_CONFIRMED":
            return {"table": table.name, "column": column.name, "status": "KO",
                    "reason": "Typage flottant/décimal pour une valeur confirmée entière (nom + conversion M en amont ou échantillon)",
                    "current_type": raw_type, "recommended_type": "int64"}
        if expectation == "INTEGER_SUSPECTED":
            return {"table": table.name, "column": column.name, "status": "KO",
                    "reason": "Typage flottant pour une colonne dont le nom évoque un compteur entier",
                    "current_type": raw_type, "recommended_type": "int64"}
        if expectation == "FIXED_DECIMAL_SUSPECTED" and raw_type == "double":
            return {"table": table.name, "column": column.name, "status": "WARN",
                    "reason": "Type double utilisé pour un montant financier : une précision décimale fixe est recommandée",
                    "current_type": raw_type, "recommended_type": "decimal (fixed decimal number)"}
        return {"table": table.name, "column": column.name, "status": "OK"}

    return {"table": table.name, "column": column.name, "status": "NA", "reason": "Type non couvert"}


results = [
    evaluate_numeric_column(table, column, get_m_code_for(table), get_sample_for(table, column))
    for table in tables
    for column in table.columns
]
```

---

## 8. Calcul du statut global

```python
if any(r["status"] == "KO" for r in results):
    rule_status = "KO"
elif any(r["status"] == "WARN" for r in results):
    rule_status = "WARN"
elif any(r["status"] == "NA" for r in results and la colonne était numérique mais indéterminable):
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > WARN > OK` (une colonne numérique dont le besoin est réellement indéterminable prime sur un simple avertissement, mais reste moins grave qu'une non-conformité confirmée).

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les colonnes numériques ont un typage cohérent avec leur besoin | `OK` |
| Au moins une colonne présente un typage flottant/décimal pour un besoin entier confirmé | `KO` |
| Aucun `KO`, mais au moins une colonne signalée `WARN` (montant financier en `double`) | `WARN` |
| Aucun `KO`/`WARN`, mais au moins une colonne numérique dont le besoin n'a pas pu être déterminé | `NA` |

---

## 9. Structure du résultat

Exemple représentatif du projet audité (colonnes numériques correctement typées) :

```json
{
  "rule_id": "BP-11",
  "rule_name": "Vérifier les types de données et la précision numérique des colonnes",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_numeric_columns": 9,
  "ok_columns": 9,
  "ko_columns": 0,
  "warn_columns": 0,
  "ko_details": [],
  "warn_details": []
}
```

Exemple avec anomalies :

```json
{
  "rule_id": "BP-11",
  "rule_name": "Vérifier les types de données et la précision numérique des colonnes",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_numeric_columns": 12,
  "ok_columns": 9,
  "ko_columns": 2,
  "warn_columns": 1,
  "ko_details": [
    {"table": "F_SCORERESPONSES", "column": "SCORE_TOTAL", "current_type": "double", "recommended_type": "int64",
     "reason": "Typage flottant pour une valeur confirmée entière (conversion Int64.Type détectée en amont dans le code M)"},
    {"table": "F_EVENTS", "column": "EVENT_YEAR", "current_type": "double", "recommended_type": "int64",
     "reason": "Typage flottant pour une colonne dont le nom évoque un compteur entier"}
  ],
  "warn_details": [
    {"table": "F_SALES", "column": "UNIT_PRICE", "current_type": "double", "recommended_type": "decimal (fixed decimal number)",
     "reason": "Type double utilisé pour un montant financier"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-11 — Types de données et précision numérique : OK

9 colonnes numériques analysées. Tous les compteurs et indices
d'ordre (CAMPAIGN_TOTAL_SAMPLE_SIZE, INTEREST_LEGEND_ORDER,
TESTED_KNOWLEDGE_LEGEND_ORDER, RESOURCES_LEGEND_ORDER...) sont
typés en int64, cohérents avec leur nature entière.
```

### Exemple `KO`

```text
BP-11 — Types de données et précision numérique : KO

9 colonnes conformes sur 12 colonnes numériques analysées.

Colonnes non conformes :
- F_SCORERESPONSES[SCORE_TOTAL] : dataType = double, alors que le
  code M applique explicitement Int64.Type avant le chargement.
- F_EVENTS[EVENT_YEAR] : dataType = double pour une colonne d'année,
  par nature entière.

Colonne à surveiller (non bloquant) :
- F_SALES[UNIT_PRICE] : dataType = double pour un montant financier ;
  un type à précision décimale fixe est recommandé pour éviter les
  erreurs d'arrondi cumulées lors des agrégations.

Correction attendue :
retyper SCORE_TOTAL et EVENT_YEAR en int64 dans le modèle (cohérent
avec la transformation déjà réalisée en Power Query pour SCORE_TOTAL) ;
évaluer le passage de UNIT_PRICE à un type numérique à précision
fixe si le connecteur source le permet.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- tous les fichiers `tables/*.tmdl` ont été chargés et toutes les colonnes numériques (`int64`, `double`, `decimal`) ont été identifiées ;
- pour chaque colonne numérique non entière, le nom de la colonne a été confronté aux motifs de besoin métier et le code M amont a été recherché pour une conversion de type explicite ;
- aucune colonne n'a été classée `OK` sur la seule base de l'absence de nom évocateur, sans vérification du code M amont lorsque celui-ci est accessible ;
- l'intégralité des colonnes numériques de toutes les tables a été parcourue, y compris les colonnes masquées.

L'agent ne doit jamais produire `OK` pour une colonne dont le code M amont applique explicitement `Int64.Type` alors que le `dataType` déclaré au niveau du modèle reste `double` ou `decimal` : cette incohérence doit systématiquement être signalée en `KO`.

---

## 12. Résumé de la règle

```text
RÈGLE BP-11

POUR chaque table du modèle
    POUR chaque colonne
        SI dataType non numérique
            colonne = NA ; PASSER à la suivante

        RECHERCHER une conversion de type explicite dans le code M amont
        INFÉRER le besoin métier (nom de colonne + conversion M + échantillon si disponible)

        SI dataType = int64
            colonne = OK
        SINON SI dataType ∈ {double, decimal}
            SI besoin entier confirmé
                colonne = KO (recommander int64)
            SINON SI besoin de précision décimale fixe suspecté (montant financier)
                colonne = WARN (recommander un type à précision fixe)
            SINON
                colonne = OK

        ENREGISTRER le résultat avec preuve
    FIN POUR
FIN POUR

SI au moins une colonne est KO
    règle = KO
SINON SI au moins une colonne est WARN
    règle = WARN
SINON SI au moins une colonne est NA sans conclusion possible
    règle = NA
SINON
    règle = OK

AFFICHER toutes les colonnes KO et WARN avec type recommandé
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-11 — Types de données et précision numérique des     │
│         colonnes                                                │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │ Lister tables/*.tmdl          │
          │ Extraire toutes les colonnes   │
          │ de toutes les tables           │
          └──────────────┬────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ Trouvé ✅   ║    │ Aucun fichier trouvé ❌ │
         ╚════╤════════╝    └──────────┬────────────┘
              │                        ▼
              │                ┌───────────────────┐
              │                │ Retour : NON_EVALUE│
              │                └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque table, POUR chaque colonne      │
   │ (boucle imbriquée, y compris colonnes        │
   │  masquées)                                  │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ dataType ∈ {int64, double, decimal} ? │
        └───────┬──────────────────┬───────────┘
              non│                  │oui
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────────┐
         ║ colonne = NA  ║  │ RECHERCHER conversion M       │
         ║ (hors périmètre║  │ amont (Int64.Type,            │
         ║  numérique)    ║  │ Currency.Type...) + nom de     │
         ╚═══════════════╝  │ colonne (_SCORE, _PRICE...)    │
                             │ → INFÉRER le besoin métier      │
                             └───────────────┬─────────────────┘
                                             ▼
                             ┌────────────────────────────┐
                             │ dataType = int64 ?            │
                             └───────┬──────────────┬────────┘
                                  oui│                │non (double/decimal)
                                     ▼                ▼
                          ╔═══════════════╗  ┌────────────────────────────┐
                          ║ colonne = OK  ║  │ Besoin entier confirmé        │
                          ╚═══════════════╝  │ (nom + conversion M, ou        │
                                              │ échantillon tout-entier) ?     │
                                              └──────┬──────────┬────────────┘
                                                   oui│           │non
                                                      ▼           ▼
                                           ╔═══════════════╗ ┌───────────────────────────┐
                                           ║ colonne = KO  ║ │ Besoin de précision           │
                                           ║ (recommander  ║ │ décimale fixe suspecté          │
                                           ║  int64)       ║ │ (montant financier) et          │
                                           ╚═══════════════╝ │ dataType = double ?              │
                                                              └──────┬──────────┬────────────────┘
                                                                   oui│           │non
                                                                      ▼           ▼
                                                          ╔═══════════════╗ ╔═══════════════╗
                                                          ║ colonne = WARN║ ║ colonne = OK  ║
                                                          ║ (recommander  ║ ╚═══════════════╝
                                                          ║  decimal fixe)║
                                                          ╚═══════════════╝
                       │
                       ▼ (ENREGISTRER avec preuve, boucle suivante — toutes les
                       │  colonnes numériques de toutes les tables analysées)
   ┌──────────────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL (priorité effective du pseudo-code :│
   │ KO > WARN > NA > OK, cf. section 12 "Résumé de la règle")   │
   │ SI au moins une colonne KO       → règle = KO               │
   │ SINON SI au moins une colonne WARN → règle = WARN            │
   │ SINON SI au moins une colonne NA sans conclusion possible    │
   │        → règle = NA                                          │
   │ SINON                              → règle = OK               │
   └───────────────────────┬──────────────────────────────────┘
                            ▼
                RETOUR rule_status (OK / WARN / NA / KO)
```
