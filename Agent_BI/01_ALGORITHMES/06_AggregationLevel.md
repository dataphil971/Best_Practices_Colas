# BP-06 — Choisir le niveau d'agrégation (grain) adapté des tables de faits

## 1. Objectif de la bonne pratique

Le **grain** d'une table de faits — c'est-à-dire ce que représente une ligne — doit correspondre au besoin d'analyse réel du rapport, ni plus fin, ni plus grossier que nécessaire. Un grain excessivement fin (par exemple une ligne par événement horodaté à la milliseconde alors que l'analyse se fait par jour, ou une ligne par réponse individuelle à une sous-question alors que l'analyse porte sur le répondant) gonfle inutilement le volume de données chargées en mémoire VertiPaq, ralentit les temps de rafraîchissement, et complique l'écriture de mesures DAX correctes (risque de double comptage lors d'agrégations `DISTINCTCOUNT` mal posées). À l'inverse, un grain trop grossier interdit certaines analyses.

L'objectif de cette règle est de détecter les tables de faits dont la granularité apparaît **anormalement fine par rapport à leur usage constaté dans le modèle et le rapport** : concrètement, un ratio `distinct_count(clé métier) / row_count` proche de 1 signifie que chaque ligne correspond quasiment à une valeur unique de la clé — ce qui est attendu pour une clé technique de ligne, mais suspect pour une clé porteuse de sens métier (identifiant de campagne, identifiant de session) si aucune dimension ni mesure du modèle n'exploite ce niveau de détail fin. La règle ne conclut jamais seule à un problème : un ratio élevé peut être parfaitement justifié (table de faits au grain "un événement" par nature) — elle **signale** les tables candidates à un réexamen et exige une justification métier explicite.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables de faits ;
- du nom des tables et des colonnes ;
- du volume réel de données (le ratio est une proportion, pas un compte absolu) ;
- de la présence ou non d'une clé technique explicitement marquée `isKey`.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
<REPORT_PATH>\definition\pages\*\visuals\*\visual.json
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_ADOPTION_QUESTION.tmdl
AI_BAROMETER_BI-CDS.Report\definition\pages\
```

L'agent doit charger :

1. les fichiers de tables de faits (préfixe `F_` dans ce projet, ou déterminé par l'heuristique de rôle décrite dans [BP-01](01_Relations.md)) pour identifier les colonnes candidates à une clé métier ;
2. un échantillon de données de la partition (si l'agent dispose d'un accès au moteur du modèle ou à un export de la table) pour calculer le ratio `distinct_count`/`row_count` ;
3. les définitions de visuels du rapport (`visual.json`), pour vérifier si le grain fin est réellement exploité (ex. un visuel de type table détaillée listant chaque ligne, un visuel de type dispersion utilisant la clé comme identifiant de point).

---

## 3. Élément(s) / propriété(s) à contrôler

Colonnes candidates à une clé métier de grain, identifiées par leur définition TMDL :

```tmdl
column CAMPAIGN_USER_LOGIN
	dataType: string
	lineageTag: ...
	summarizeBy: none
	sourceColumn: CAMPAIGN_USER_LOGIN
```

et par leur usage dans une relation (`relationships.tmdl`) comme `fromColumn` d'une table de faits, ce qui confirme qu'elle porte le grain de la table.

L'agent s'appuie également sur les propriétés de partition pour estimer le volume :

```tmdl
partition F_RESPONSES = m
	mode: import
	queryGroup: FAITS
	source = ...
```

Si un accès aux données (échantillon ou statistiques VertiPaq) est disponible, l'agent calcule directement :

```text
ratio = distinct_count(CAMPAIGN_USER_LOGIN) / row_count(F_RESPONSES)
```

À défaut d'accès aux données, l'agent applique une heuristique structurelle basée sur le nombre de colonnes descriptives non techniques de la table (une table de faits avec une seule colonne de mesure et une clé quasi unique par ligne est un signal indirect de grain trop fin), combinée à la présence ou à l'absence d'un usage exploitant ce niveau de détail dans les visuels du rapport.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `F_RESPONSES`, clé `CAMPAIGN_USER_LOGIN`, ratio ≈ 1.0, mais colonne utilisée dans plusieurs visuels de type carte/segment individuel | `OK` | Le grain fin est directement exploité par le rapport, justification constatée. |
| `F_ADOPTION_QUESTION`, ratio ≈ 0.15 (plusieurs lignes de réponse par utilisateur, agrégées ensuite) | `OK` | Grain cohérent avec l'usage : plusieurs réponses par utilisateur, analysées par question. |
| Table hypothétique `F_CLICK_EVENTS`, clé `EVENT_ID` horodatée à la milliseconde, ratio ≈ 1.0, aucune mesure ni visuel n'agrège en dessous du niveau "jour" | `KO` | Granularité événementielle inutilement fine par rapport à l'usage constaté ; alourdit le modèle sans bénéfice analytique. |
| Table hypothétique `F_DAILY_SUMMARY`, clé composite (date, campagne), ratio faible, alimentée par une pré-agrégation en amont | `OK` | Grain déjà résumé au niveau d'analyse pertinent. |
| Table candidate sans clé métier identifiable et sans échantillon de données accessible | `NA` | Impossible de calculer le ratio ou d'établir un jugement fiable. |
| Table de dimension (`D_*`) ou table technique (`T_*`, `P_*`) | `NA` | Hors périmètre : la règle porte exclusivement sur les tables de faits. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Identifier les tables de faits via l'heuristique de rôle partagée avec BP-01 (préfixe `F_`, position dans le graphe de relations).
2. Charger les fichiers `tables/*.tmdl` correspondants et `relationships.tmdl`.
3. Charger les définitions de visuels du rapport si disponibles.
4. Si aucune table de faits n'est identifiée, retourner `NON_EVALUE`.

### Étape 2 — Identifier la clé de grain de chaque table de faits
Pour chaque table de faits : repérer la ou les colonnes utilisées comme `fromColumn` dans des relations vers des dimensions, ou la colonne qui varie à chaque ligne d'un même groupe logique (heuristique de nommage `_ID`, `_LOGIN`, `_KEY`).

### Étape 3 — Calculer ou estimer le ratio de cardinalité
Si un échantillon de données est accessible : calculer `distinct_count / row_count`. Sinon : appliquer l'heuristique structurelle (nombre de colonnes de mesure vs colonnes d'identification, présence d'agrégations en amont dans le code M).

### Étape 4 — Croiser avec l'usage réel du rapport
Rechercher, dans les définitions de visuels, si la clé de grain fin est directement projetée dans un visuel (table détaillée, export) ou si elle n'est utilisée que comme clé technique de relation (jamais affichée ni utilisée dans un contexte de filtre visuel).

### Étape 5 — Ne pas s'arrêter à la première table analysée
L'agent évalue l'intégralité des tables de faits, y compris celles jugées conformes après la première analyse.

### Étape 6 — Terminer l'analyse
Produire : la liste des tables de faits analysées avec leur ratio (calculé ou estimé) ; les tables `KO` avec justification de l'anomalie ; les tables `NA` faute d'accès aux données.

---

## 6. Détection robuste / normalisation

**Absence d'accès direct aux données** — dans un contexte d'audit statique (lecture seule des fichiers TMDL/JSON sans connexion au moteur Power BI), l'agent ne peut pas toujours calculer un `distinct_count` réel. Il doit alors :

1. rechercher dans le code M de la partition (`Table.Group`, `Table.Distinct`) des indices d'une agrégation déjà réalisée en amont, qui réduirait mécaniquement le ratio ;
2. rechercher dans le code M l'absence de toute opération de regroupement, ce qui indique que la table conserve un grain brut ;
3. signaler explicitement dans le résultat si le ratio est **estimé** (`"ratio_source": "heuristic"`) plutôt que **mesuré** (`"ratio_source": "sampled"`), afin que l'utilisateur puisse pondérer la confiance accordée à la conclusion.

```python
def estimate_ratio_source(table):
    m_code = table.partition.source_expression if table.has_m_partition() else ""
    if contains_function_call(m_code, "Table.Group"):
        return "reduced_by_grouping"
    if contains_function_call(m_code, "Table.Distinct"):
        return "reduced_by_distinct"
    return "raw_grain"
```

**Identification de la clé de grain** : priorité à la colonne utilisée comme `fromColumn` dans une relation vers une dimension et présente dans la majorité des lignes (non nulle) ; à défaut, heuristique de nommage (`*_ID`, `*_LOGIN`, `*_KEY`, `*_CODE`).

**Correspondance avec les visuels** : la comparaison entre le nom de colonne du modèle et le nom du champ dans `visual.json` (`queryRef`, `Column` property) doit être normalisée (suppression du préfixe de table, insensibilité à la casse) car Power BI peut référencer une colonne sous la forme `F_RESPONSES.CAMPAIGN_USER_LOGIN` ou uniquement `CAMPAIGN_USER_LOGIN` selon le contexte.

**Seuils par défaut** (paramétrables) :

```text
RATIO_SUSPECT_THRESHOLD = 0.90   # ratio >= 0.90 : granularité suspecte, à examiner
```

Ce seuil ne déclenche jamais un `KO` automatique : il déclenche l'examen de l'usage réel (étape 4). Seule l'absence d'usage constaté du grain fin, combinée à un ratio élevé, produit un `KO`.

---

## 7. Pseudo-code détaillé

```python
def identify_grain_key(fact_table, relationships):
    outgoing = [r for r in relationships if r.from_table == fact_table.name]
    if outgoing:
        return outgoing[0].from_column
    for c in fact_table.columns:
        if re.search(r"(_ID|_LOGIN|_KEY|_CODE)$", c.name, re.I):
            return c.name
    return None


def compute_or_estimate_ratio(fact_table, grain_key, data_sample):
    if data_sample is not None:
        distinct = len(set(row[grain_key] for row in data_sample))
        total = len(data_sample)
        return {"ratio": distinct / total, "ratio_source": "sampled"}
    reduction_hint = estimate_ratio_source(fact_table)
    estimated_ratio = 0.95 if reduction_hint == "raw_grain" else 0.30
    return {"ratio": estimated_ratio, "ratio_source": f"heuristic:{reduction_hint}"}


def grain_key_used_in_visuals(grain_key, visuals):
    normalized_key = normalize(grain_key)
    for visual in visuals:
        fields = extract_referenced_fields(visual)  # queryRef / Column
        if any(normalize(f) == normalized_key for f in fields):
            return True
    return False


def evaluate_fact_table(fact_table, relationships, data_sample, visuals):
    grain_key = identify_grain_key(fact_table, relationships)
    if grain_key is None:
        return {"table": fact_table.name, "status": "NA", "reason": "Clé de grain non identifiable"}

    ratio_info = compute_or_estimate_ratio(fact_table, grain_key, data_sample)

    if ratio_info["ratio"] < RATIO_SUSPECT_THRESHOLD:
        return {"table": fact_table.name, "status": "OK", "grain_key": grain_key, **ratio_info}

    used_in_visuals = grain_key_used_in_visuals(grain_key, visuals)
    if used_in_visuals:
        return {"table": fact_table.name, "status": "OK", "grain_key": grain_key,
                "reason": "Grain fin exploité directement par au moins un visuel", **ratio_info}

    return {"table": fact_table.name, "status": "KO", "grain_key": grain_key,
            "reason": "Ratio de cardinalité élevé sans usage constaté du grain fin dans le rapport", **ratio_info}
```

---

## 8. Calcul du statut global

```python
if any(r["status"] == "KO" for r in results):
    rule_status = "KO"
elif any(r["status"] == "NA" for r in results):
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les tables de faits ont un ratio raisonnable, ou un ratio élevé justifié par l'usage | `OK` |
| Au moins une table de faits présente un ratio élevé sans justification d'usage | `KO` |
| Aucun `KO`, mais au moins une table sans clé de grain identifiable ou sans échantillon de données | `NA` |
| Tables `KO` et `NA` présentes simultanément | `KO`, avec analyse partielle signalée |

---

## 9. Structure du résultat

Exemple lorsque la granularité est jugée cohérente (état représentatif du projet audité) :

```json
{
  "rule_id": "BP-06",
  "rule_name": "Choisir le niveau d'agrégation (grain) adapté des tables de faits",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_fact_tables": 2,
  "ok_details": [
    {"table": "F_RESPONSES", "grain_key": "CAMPAIGN_USER_LOGIN", "ratio": 0.98, "ratio_source": "heuristic:raw_grain",
     "reason": "Grain fin exploité directement par au moins un visuel"},
    {"table": "F_ADOPTION_QUESTION", "grain_key": "CAMPAIGN_USER_LOGIN", "ratio": 0.22, "ratio_source": "heuristic:reduced_by_grouping"}
  ],
  "ko_details": [],
  "na_details": []
}
```

Exemple avec granularité suspecte :

```json
{
  "rule_id": "BP-06",
  "rule_name": "Choisir le niveau d'agrégation (grain) adapté des tables de faits",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_fact_tables": 3,
  "ko_details": [
    {
      "table": "F_CLICK_EVENTS",
      "grain_key": "EVENT_ID",
      "ratio": 0.99,
      "ratio_source": "heuristic:raw_grain",
      "reason": "Ratio de cardinalité élevé sans usage constaté du grain fin dans le rapport"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-06 — Niveau d'agrégation des tables de faits : OK

2 tables de faits analysées. F_RESPONSES conserve un grain fin
(ratio ~0,98 sur CAMPAIGN_USER_LOGIN) mais ce niveau de détail est
directement exploité par les visuels du rapport. F_ADOPTION_QUESTION
présente un ratio de 0,22, cohérent avec plusieurs réponses par
utilisateur agrégées par question.
```

### Exemple `KO`

```text
BP-06 — Niveau d'agrégation des tables de faits : KO

Table non conforme :
- F_CLICK_EVENTS : ratio distinct_count(EVENT_ID)/row_count ≈ 0,99
  (quasiment une ligne unique par événement horodaté), sans qu'aucun
  visuel du rapport n'exploite ce niveau de détail — toutes les
  analyses agrègent au niveau jour/campagne.

Correction attendue :
pré-agréger F_CLICK_EVENTS au grain jour x campagne dans l'ETL ou un
dataflow en amont (cf. BP-04), et ne conserver le détail événement
que si un besoin d'exploration fine est explicitement documenté et
exposé dans un visuel dédié.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- toutes les tables de faits du modèle ont été identifiées via l'heuristique de rôle ;
- pour chaque table de faits, une clé de grain a pu être identifiée (relation ou heuristique de nommage) ;
- un ratio a été calculé (échantillon réel) ou estimé (heuristique structurelle documentée) pour chaque table de faits, avec la source de l'estimation tracée ;
- pour chaque table présentant un ratio élevé, l'usage réel de la clé de grain dans les visuels du rapport a été recherché avant de conclure ;
- aucune table de faits n'a été ignorée faute d'accès aux données sans être classée `NA`.

L'agent ne doit jamais produire `OK` uniquement parce qu'un ratio n'a pas pu être calculé : l'absence de donnée doit être explicitement classée `NA`, jamais assimilée à une conformité implicite.

---

## 12. Résumé de la règle

```text
RÈGLE BP-06

IDENTIFIER les tables de faits (heuristique de rôle, cf. BP-01)

POUR chaque table de faits
    IDENTIFIER la clé de grain (relation vers une dimension ou heuristique de nommage)
    SI clé introuvable
        table = NA ; PASSER à la suivante

    CALCULER ou ESTIMER ratio = distinct_count(clé) / row_count
    TRACER la source du ratio (mesuré vs heuristique)

    SI ratio < seuil de suspicion
        table = OK
    SINON
        RECHERCHER l'usage de la clé de grain dans les visuels du rapport
        SI usage constaté
            table = OK (grain fin justifié)
        SINON
            table = KO (granularité suspecte, sans justification d'usage)

    ENREGISTRER le résultat avec preuve
FIN POUR

SI au moins une table est KO
    règle = KO
SINON SI au moins une table est NA
    règle = NA
SINON
    règle = OK

AFFICHER toutes les tables KO avec recommandation de pré-agrégation
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-06 — Niveau d'agrégation (grain) des tables de faits │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────────┐
          │ IDENTIFIER les tables de faits     │
          │ (heuristique de rôle, cf. BP-01)   │
          │ Charger relationships.tmdl +        │
          │ visuels du rapport si disponibles   │
          └──────────────┬────────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ ≥1 table     ║    │ Aucune table de faits ❌│
         ║ de faits ✅  ║    └──────────┬────────────┘
         ╚════╤════════╝               ▼
              │                ┌───────────────────┐
              │                │ Retour : NON_EVALUE│
              │                └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque table de faits (boucle)         │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ IDENTIFIER la clé de grain            │
        │ (fromColumn d'une relation, ou nom     │
        │ *_ID/_LOGIN/_KEY/_CODE)               │
        └───────┬──────────────────┬───────────┘
          introuvable│              │trouvée
                     ▼              ▼
             ╔═══════════════╗  ┌────────────────────────────┐
             ║ table = NA    ║  │ CALCULER ou ESTIMER          │
             ╚═══════════════╝  │ ratio = distinct_count(clé)/ │
                                 │ row_count (mesuré ou          │
                                 │ heuristique M : Table.Group/  │
                                 │ Table.Distinct)                │
                                 └───────────────┬─────────────────┘
                                                 ▼
                                 ┌────────────────────────────┐
                                 │ ratio < seuil de suspicion   │
                                 │ (0,90) ?                     │
                                 └───────┬──────────────┬────────┘
                                      oui│                │non
                                         ▼                ▼
                              ╔═══════════════╗  ┌────────────────────────┐
                              ║ table = OK    ║  │ RECHERCHER l'usage de la │
                              ╚═══════════════╝  │ clé de grain dans les     │
                                                  │ visuels du rapport        │
                                                  │ (visual.json)             │
                                                  └──────┬──────────┬────────┘
                                                    usage│           │pas
                                                   constaté          usage
                                                        ▼             ▼
                                            ╔═══════════════╗ ╔═══════════════╗
                                            ║ table = OK    ║ ║ table = KO    ║
                                            ║ (grain justifié)║ ║ (granularité   ║
                                            ╚═══════════════╝ ║ suspecte)      ║
                                                               ╚═══════════════╝
                       │
                       ▼ (ENREGISTRER avec preuve et source du ratio,
                       │  boucle suivante jusqu'à la dernière table de faits)
   ┌────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL (priorité KO > NA > OK) │
   │ SI au moins une table KO    → règle = KO        │
   │ SINON SI au moins une table NA → règle = NA     │
   │ SINON                          → règle = OK     │
   └───────────────────────┬────────────────────────┘
                            ▼
                RETOUR rule_status (OK / KO / NA)
```
