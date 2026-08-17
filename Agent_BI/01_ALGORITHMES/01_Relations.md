# BP-01 — Respect de la topologie en étoile des relations

## 1. Objectif de la bonne pratique

Un modèle sémantique Power BI performant et maintenable doit respecter une **topologie en étoile** (star schema) : des tables de faits, volumineuses et au grain fin, reliées à des tables de dimension, plus petites et descriptives, via des relations de cardinalité **plusieurs-vers-un** (`*:1`) orientées de la table de faits vers la table de dimension. Cette structure garantit des plans de requête VertiPaq prévisibles, un moteur de filtrage cohérent et une maintenance facilitée (chaque dimension ne joue qu'un seul rôle sémantique).

L'objectif de cette règle est de vérifier que **chaque relation déclarée dans le modèle respecte ce principe** : la table côté « plusieurs » (`*`) doit être une table de faits (ou, à défaut, une table dont le rôle logique est clairement celui d'un référentiel de détail), et la table côté « un » (`1`) doit être une table de dimension possédant une clé candidate. Une relation qui relie deux tables de faits entre elles, deux dimensions entre elles sans table de jonction, ou qui présente une cardinalité `*:*` non justifiée par une table de jonction explicite, constitue une entorse à la topologie en étoile.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables de faits et de dimensions ;
- du nom réel des tables et des colonnes ;
- de l'ordre des relations et des propriétés dans les fichiers TMDL ;
- des préfixes de nommage utilisés (le modèle audité utilise `D_`, `F_`, `P_`, `T_`, mais la règle ne doit pas dépendre exclusivement de cette convention : elle doit combiner l'indice de nommage avec des indices structurels).

Cette règle porte sur la **topologie et la cardinalité** des relations. Le contrôle du filtrage croisé bidirectionnel et des relations plusieurs-à-plusieurs sans table de jonction fait l'objet d'une règle dédiée : [BP-03](03_AvoidBidirectional.md).

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\relationships.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_CAMPAIGNS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_ADOPTION_QUESTION.tmdl
```

L'agent doit charger :

1. `relationships.tmdl` en intégralité, pour extraire chaque bloc `relationship` ;
2. tous les fichiers `tables/*.tmdl`, pour déterminer le rôle logique de chaque table (fait, dimension, paramètre, technique) et localiser les colonnes clés.

---

## 3. Élément(s) / propriété(s) à contrôler

Chaque relation est un bloc `relationship <guid>` dans `relationships.tmdl`. Extrait réel du modèle audité :

```tmdl
relationship AutoDetected_04792bd7-6479-4ee6-8d14-fc0d680fe50f
	fromColumn: F_RESPONSES.CAMPAIGN_ID
	toColumn: D_CAMPAIGNS.CAMPAIGN_ID
```

Points clés du format TMDL :

- `fromColumn` / `toColumn` désignent respectivement la colonne côté « plusieurs » et la colonne côté « un » **par défaut** ;
- lorsque `fromCardinality` et `toCardinality` sont **absents**, Power BI applique la cardinalité par défaut `many` côté `from` et `one` côté `to` — c'est le cas de toutes les relations de ce projet ;
- une cardinalité explicite peut être présente pour signaler un écart au défaut, par exemple :

```tmdl
relationship <guid>
	fromColumn: F_TABLE_A.KEY
	toColumn: F_TABLE_B.KEY
	fromCardinality: many
	toCardinality: many
```

qui indique une relation **plusieurs-à-plusieurs (`*:*`)** entre les deux tables.

Du côté des tables, l'agent s'appuie sur :

```tmdl
table D_CAMPAIGNS
	lineageTag: 6bfd2601-0ebf-442a-8353-f9e5f53901ab

	column CAMPAIGN_ID
		dataType: string
		isHidden
		lineageTag: b30938a6-aa65-4080-bd83-dd84d12c599d
		summarizeBy: none
		sourceColumn: CAMPAIGN_ID
```

- le **nom de la table** (préfixe `D_`, `F_`, `P_`, `T_` dans ce projet) ;
- la présence d'une propriété `isKey` sur une colonne (marqueur explicite de clé primaire, absent dans cet extrait mais utilisable lorsqu'il existe) ;
- le nombre de colonnes et le volume de lignes de la partition, utilisés comme indices secondaires (une dimension a en général peu de colonnes descriptives, une table de faits en a souvent davantage et un grain plus fin).

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `F_RESPONSES` (fait) → `D_CAMPAIGNS` (dimension), cardinalité par défaut `*:1` | `OK` | Topologie en étoile respectée : la table de faits filtre la dimension. |
| `F_ADOPTION_QUESTION` (fait) → `D_CAMPAIGNS` (dimension), cardinalité par défaut `*:1` | `OK` | Idem, deuxième table de faits reliée à la même dimension partagée. |
| `F_RESPONSES` (fait) ↔ `F_ADOPTION_QUESTION` (fait), relation directe entre deux tables de faits | `KO` | Relation fait-à-fait : viole la topologie en étoile, risque de double comptage et de filtrage incohérent. |
| `D_USERS` (dimension) → `D_CAMPAIGNS` (dimension), relation directe entre deux dimensions sans table de faits intermédiaire | `KO` | Relation dimension-à-dimension : doit transiter par une table de faits ou être fusionnée en une seule dimension (snowflake non justifié). |
| `fromCardinality: many` et `toCardinality: many` sans table de jonction dédiée référencée par ailleurs | `KO` | Cardinalité `*:*` non justifiée : source d'ambiguïté de filtrage et de doublons. |
| `P_EVOLUTION_LEGEND_TOP` (table paramètre, préfixe `P_`) → `D_CHOICE` | `NA` | Table technique/paramètre hors périmètre de l'analyse en étoile (pas une table de faits). |
| `T_NOTIFICATION` ou `T_PAGE_NUMBER` impliquée dans une relation | `NA` | Table technique (préfixe `T_`), rôle non analytique, hors périmètre. |
| Rôle de l'une des deux tables non déterminable (aucun signal fiable de fait/dimension) | `NA` | Analyse impossible avec un niveau de confiance suffisant. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Charger `relationships.tmdl` et extraire tous les blocs `relationship`.
2. Charger tous les fichiers `tables/*.tmdl`.
3. Si `relationships.tmdl` est introuvable ou vide, retourner `NON_EVALUE` (aucune relation à analyser n'implique pas nécessairement une erreur, mais empêche toute conclusion sur la topologie).

### Étape 2 — Déterminer le rôle logique de chaque table
Pour chaque table du modèle, avant même de regarder les relations, l'agent calcule un rôle probable : `FACT`, `DIMENSION`, `PARAMETER`, `TECHNICAL` ou `UNKNOWN` (voir section 6).

### Étape 3 — Analyser chaque relation
Pour chaque relation : identifier la table et la colonne côté `from` et côté `to` ; résoudre la cardinalité effective (explicite ou par défaut) ; croiser avec le rôle logique des deux tables ; appliquer la grille de décision (section 4) ; enregistrer le résultat avec preuve.

### Étape 4 — Ne pas s'arrêter à la première anomalie
L'agent doit analyser l'intégralité des relations du fichier, même après avoir détecté une première relation `KO`, afin de fournir une vision exhaustive de la topologie (une seule relation dimension-à-dimension peut coexister avec sept relations parfaitement conformes).

### Étape 5 — Terminer l'analyse
Produire : le nombre total de relations analysées ; le nombre de relations `OK`, `KO`, `NA` ; la liste des relations `KO` avec le détail des tables et rôles impliqués ; une synthèse de la topologie globale (nombre de tables de faits, de dimensions, de dimensions partagées entre plusieurs faits).

---

## 6. Détection robuste / normalisation

**Inférence du rôle de table** — l'agent ne doit pas se fier uniquement au préfixe de nommage, qui peut être absent ou différent d'un projet à l'autre. Il combine plusieurs signaux, par ordre de priorité :

1. **Signal fort — préfixe conventionnel** : `D_*`/`Dim*` → `DIMENSION`, `F_*`/`Fact*` → `FACT`, `P_*`/`Param*` → `PARAMETER`, `T_*`/`Tech*` → `TECHNICAL`. Reconnu de façon insensible à la casse.
2. **Signal structurel — position dans le graphe de relations** : une table qui apparaît majoritairement côté `from` (cardinalité `many`) de ses relations et jamais côté `to` d'une relation venant d'une autre table à grain plus fin est un candidat `FACT` ; une table qui apparaît majoritairement côté `to` (cardinalité `one`) avec une colonne clé correspondant à la colonne `from` de plusieurs relations est un candidat `DIMENSION`.
3. **Signal de clé** : présence de la propriété `isKey` sur une colonne, ou colonne dont le nom correspond au nom de la table suivi de `_ID`/`_KEY` (ex. `CAMPAIGN_ID` dans `D_CAMPAIGNS`) et qui est référencée comme `toColumn` par au moins une relation → renforce le rôle `DIMENSION`.
4. En l'absence de tout signal exploitable, le rôle est `UNKNOWN` et toute relation impliquant cette table est classée `NA`.

**Gestion de l'ordre et de la casse** : les propriétés `fromColumn`, `toColumn`, `fromCardinality`, `toCardinality`, `crossFilteringBehavior` peuvent apparaître dans n'importe quel ordre à l'intérieur d'un bloc `relationship`. La comparaison des valeurs de cardinalité (`many`/`one`) doit être insensible à la casse et tolérer les espaces superflus.

**Noms de colonnes composés** : certains noms de colonnes contiennent des espaces ou une apostrophe et sont donc entourés de guillemets simples en TMDL, par exemple `P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'` ou `D_CHOICE.'ID '` (avec un espace final). L'agent doit dépouiller ces guillemets pour extraire le nom réel de la table et de la colonne, sans que l'espace final ne casse la correspondance avec les autres occurrences de `D_CHOICE`.

**Cardinalité implicite** : l'absence des propriétés `fromCardinality`/`toCardinality` ne doit jamais être interprétée comme `NA` — elle doit être résolue en `many:one`, qui est la valeur par défaut documentée du format TMDL.

---

## 7. Pseudo-code détaillé

```python
FACT_PREFIXES = ("F_", "FACT", "FAIT")
DIM_PREFIXES = ("D_", "DIM")
PARAM_PREFIXES = ("P_", "PARAM")
TECH_PREFIXES = ("T_", "TECH")

def infer_table_role(table, relationships):
    name_upper = table.name.strip().upper()

    if name_upper.startswith(FACT_PREFIXES):
        return "FACT"
    if name_upper.startswith(DIM_PREFIXES):
        return "DIMENSION"
    if name_upper.startswith(PARAM_PREFIXES):
        return "PARAMETER"
    if name_upper.startswith(TECH_PREFIXES):
        return "TECHNICAL"

    # Signal structurel : position dominante dans le graphe de relations
    as_from = [r for r in relationships if r.from_table == table.name]
    as_to = [r for r in relationships if r.to_table == table.name]

    has_key_column = any(
        c.has_property("isKey") or normalize(c.name) in {
            normalize(table.name) + "_ID", normalize(table.name) + "_KEY"
        }
        for c in table.columns
    )

    if len(as_to) > len(as_from) and has_key_column:
        return "DIMENSION"
    if len(as_from) > len(as_to):
        return "FACT"

    return "UNKNOWN"


def resolve_cardinality(rel):
    from_card = normalize(rel.get_property("fromCardinality") or "many")
    to_card = normalize(rel.get_property("toCardinality") or "one")
    return from_card, to_card


def evaluate_relationship(rel, table_roles):
    from_table = rel.from_table
    to_table = rel.to_table
    from_role = table_roles.get(from_table, "UNKNOWN")
    to_role = table_roles.get(to_table, "UNKNOWN")
    from_card, to_card = resolve_cardinality(rel)

    if from_role in {"PARAMETER", "TECHNICAL"} or to_role in {"PARAMETER", "TECHNICAL"}:
        return {"status": "NA", "reason": f"Table hors périmètre analytique ({from_role}/{to_role})"}

    if from_role == "UNKNOWN" or to_role == "UNKNOWN":
        return {"status": "NA", "reason": "Rôle logique d'une des deux tables non déterminable"}

    if from_card == "many" and to_card == "many":
        return {"status": "KO", "reason": "Cardinalité *:* non justifiée par une table de jonction explicite"}

    if from_role == "FACT" and to_role == "DIMENSION" and from_card == "many" and to_card == "one":
        return {"status": "OK", "reason": "Relation fait -> dimension, cardinalité *:1 conforme"}

    if from_role == "FACT" and to_role == "FACT":
        return {"status": "KO", "reason": "Relation directe entre deux tables de faits"}

    if from_role == "DIMENSION" and to_role == "DIMENSION":
        return {"status": "KO", "reason": "Relation directe entre deux tables de dimension (snowflake non justifié)"}

    if from_role == "DIMENSION" and to_role == "FACT":
        return {"status": "KO", "reason": "Sens de la relation inversé : la dimension est déclarée côté 'plusieurs'"}

    return {"status": "NA", "reason": "Combinaison de rôles non couverte par la grille de décision"}
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
| Toutes les relations analysables sont `*:1` fait → dimension | `OK` |
| Au moins une relation fait-à-fait, dimension-à-dimension ou `*:*` non justifiée | `KO` |
| Aucun `KO`, mais au moins une relation implique une table au rôle indéterminé | `NA` |
| Relations `KO` et `NA` présentes simultanément | `KO`, avec analyse partielle signalée |

---

## 9. Structure du résultat

Exemple lorsque la topologie en étoile est respectée (état actuel du projet audité) :

```json
{
  "rule_id": "BP-01",
  "rule_name": "Respect de la topologie en étoile des relations",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_relationships": 8,
  "ok_relationships": 6,
  "ko_relationships": 0,
  "na_relationships": 2,
  "ok_details": [
    {"from": "F_RESPONSES.CAMPAIGN_ID", "to": "D_CAMPAIGNS.CAMPAIGN_ID", "cardinality": "many:one"},
    {"from": "F_ADOPTION_QUESTION.CAMPAIGN_ID", "to": "D_CAMPAIGNS.CAMPAIGN_ID", "cardinality": "many:one"},
    {"from": "F_RESPONSES.CAMPAIGN_USER_LOGIN", "to": "D_USERS.CAMPAIGN_USER_LOGIN", "cardinality": "many:one"},
    {"from": "F_ADOPTION_QUESTION.CAMPAIGN_USER_LOGIN", "to": "D_USERS.CAMPAIGN_USER_LOGIN", "cardinality": "many:one"},
    {"from": "F_RESPONSES.AI_USAGE_FREQ_LEVEL", "to": "D_USAGE_FREQUENCY_LEVELS.USAGE_FREQUENCY_LEVELS", "cardinality": "many:one"}
  ],
  "ko_details": [],
  "na_details": [
    {"from": "P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'", "to": "D_CHOICE.'ID '", "reason": "Table hors périmètre analytique (PARAMETER/DIMENSION)"},
    {"from": "P_EVOLUTION_LEGEND_BOTTOM.'P_LEGEND2 Order'", "to": "D_CHOICE.'ID '", "reason": "Table hors périmètre analytique (PARAMETER/DIMENSION)"}
  ]
}
```

Exemple avec anomalie de topologie :

```json
{
  "rule_id": "BP-01",
  "rule_name": "Respect de la topologie en étoile des relations",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_relationships": 9,
  "ok_relationships": 6,
  "ko_relationships": 1,
  "na_relationships": 2,
  "ko_details": [
    {
      "from": "F_RESPONSES.CAMPAIGN_ID",
      "to": "F_ADOPTION_QUESTION.CAMPAIGN_ID",
      "reason": "Relation directe entre deux tables de faits"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-01 — Topologie en étoile des relations : OK

6 relations conformes sur 8 relations analysées (2 relations hors
périmètre car reliant des tables paramètres).

Toutes les relations fait -> dimension respectent une cardinalité
*:1 : F_RESPONSES et F_ADOPTION_QUESTION filtrent correctement
D_CAMPAIGNS, D_USERS et D_USAGE_FREQUENCY_LEVELS.
```

### Exemple `KO`

```text
BP-01 — Topologie en étoile des relations : KO

6 relations conformes sur 9 relations analysées.

Relation non conforme :
- F_RESPONSES.CAMPAIGN_ID -> F_ADOPTION_QUESTION.CAMPAIGN_ID :
  relation directe entre deux tables de faits, ce qui viole la
  topologie en étoile et expose le modèle à un risque de double
  comptage lors de mesures croisant les deux tables.

Correction attendue :
supprimer cette relation directe et faire transiter la relation par
la dimension partagée D_CAMPAIGNS (déjà reliée aux deux tables de
faits), ou fusionner les deux tables de faits si elles partagent
réellement le même grain.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- `relationships.tmdl` a été localisé, chargé et intégralement parsé ;
- tous les fichiers `tables/*.tmdl` ont été chargés pour permettre l'inférence de rôle ;
- chaque relation a pu être rattachée à deux tables existantes du modèle ;
- le rôle logique des deux tables de chaque relation analysée a été déterminé avec un signal fiable (préfixe, structure du graphe ou clé) — un rôle `UNKNOWN` doit produire `NA`, jamais un `OK` implicite ;
- la cardinalité de chaque relation (explicite ou par défaut) a été résolue ;
- aucune relation fait-à-fait, dimension-à-dimension ou `*:*` non justifiée n'a été détectée ;
- l'intégralité des relations du fichier a été parcourue, sans arrêt à la première conformité constatée.

L'agent ne doit jamais produire `OK` sur la base d'un sous-ensemble de relations, ni en se fondant uniquement sur le nombre de relations `*:1` sans avoir vérifié qu'aucune relation fait-à-fait ou `*:*` n'existe par ailleurs dans le fichier.

---

## 12. Résumé de la règle

```text
RÈGLE BP-01

POUR chaque table du modèle
    DÉTERMINER le rôle logique (FACT, DIMENSION, PARAMETER, TECHNICAL, UNKNOWN)
    via préfixe de nommage, position dans le graphe de relations, présence de clé

POUR chaque relation de relationships.tmdl
    RÉSOUDRE la cardinalité (explicite ou défaut many:one)
    CROISER le rôle des deux tables avec la cardinalité

    SI l'une des tables est PARAMETER/TECHNICAL/UNKNOWN
        relation = NA
    SINON SI cardinalité = *:* sans table de jonction
        relation = KO
    SINON SI FACT -> DIMENSION avec cardinalité *:1
        relation = OK
    SINON SI FACT <-> FACT ou DIMENSION <-> DIMENSION
        relation = KO
    SINON
        relation = NA

    ENREGISTRER le résultat avec preuve
FIN POUR

SI au moins une relation est KO
    règle = KO
SINON SI au moins une relation est NA
    règle = NA
SINON
    règle = OK

AFFICHER toutes les relations KO et la synthèse de la topologie globale
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-01 — Topologie en étoile des relations              │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │ Charger relationships.tmdl   │
          │ Charger tous les tables/*.tmdl│
          └──────────────┬────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ Trouvé ✅   ║    │ relationships.tmdl    │
         ╚════╤════════╝    │ introuvable/vide ❌   │
              │              └──────────┬────────────┘
              │                         ▼
              │                 ┌───────────────────┐
              │                 │ Retour : NON_EVALUE│
              │                 └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque table du modèle (boucle 1)     │
   │ INFÉRER le rôle logique :                  │
   │ FACT / DIMENSION / PARAMETER / TECHNICAL /  │
   │ UNKNOWN (préfixe > graphe > clé)            │
   └──────────────────┬──────────────────────────┘
                       ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque relation de relationships.tmdl │
   │ (boucle 2 — jusqu'à épuisement)            │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ Résoudre from_role / to_role         │
        │ Résoudre cardinalité (défaut many:one)│
        └──────────────┬────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ from_role/to_role ∈ {PARAMETER,     │
        │ TECHNICAL, UNKNOWN} ?               │
        └───────┬──────────────────┬───────────┘
              oui│                  │non
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────┐
         ║ relation = NA ║  │ cardinalité = many:many │
         ╚═══════════════╝  │ sans table de jonction ?│
                             └───────┬──────────┬───────┘
                                  oui│           │non
                                     ▼           ▼
                          ╔═══════════════╗ ┌─────────────────────┐
                          ║ relation = KO ║ │ FACT → DIMENSION     │
                          ╚═══════════════╝ │ cardinalité *:1 ?    │
                                             └──────┬────────┬──────┘
                                                  oui│         │non
                                                     ▼         ▼
                                          ╔═══════════════╗ ┌───────────────────────┐
                                          ║ relation = OK ║ │ FACT↔FACT ou           │
                                          ╚═══════════════╝ │ DIMENSION↔DIMENSION ?  │
                                                             └──────┬────────┬────────┘
                                                                  oui│         │non
                                                                     ▼         ▼
                                                          ╔═══════════════╗ ╔═══════════════╗
                                                          ║ relation = KO ║ ║ relation = NA ║
                                                          ╚═══════════════╝ ╚═══════════════╝
                       │
                       │ (ENREGISTRER le résultat avec preuve, revenir en boucle 2
                       │  jusqu'à la dernière relation — jamais d'arrêt prématuré)
                       ▼
   ┌────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL (priorité KO > NA > OK) │
   │ SI au moins une relation KO    → règle = KO     │
   │ SINON SI au moins une relation NA → règle = NA  │
   │ SINON                            → règle = OK   │
   └───────────────────────┬────────────────────────┘
                            ▼
                RETOUR rule_status (OK / KO / NA)
                avec la liste des relations KO et la
                synthèse de la topologie globale
```
