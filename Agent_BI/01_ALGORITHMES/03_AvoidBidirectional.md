# BP-03 — Éviter les relations bidirectionnelles et many-to-many non justifiées

## 1. Objectif de la bonne pratique

Le filtrage croisé bidirectionnel (`crossFilteringBehavior: bothDirections`) permet à une relation de propager les filtres dans les deux sens — y compris depuis la table côté « un » vers la table côté « plusieurs », ou entre deux tables de faits reliées à une même dimension. Ce comportement, séduisant en apparence, introduit des **ambiguïtés de filtrage** (chemins de filtrage multiples entre deux tables), des **risques de résultats incorrects** en présence de plusieurs relations actives, et une **dégradation des performances** du moteur VertiPaq, qui doit évaluer des contextes de filtre plus complexes. De la même manière, une relation **plusieurs-à-plusieurs (`*:*`)** directe entre deux tables — sans table de jonction dédiée qui matérialise explicitement les combinaisons valides — est une source fréquente de doublons silencieux dans les mesures agrégées.

L'objectif de cette règle est de vérifier que :

1. **aucune relation du modèle n'est bidirectionnelle par défaut**, sauf si elle est explicitement justifiée par un cas d'usage documenté (ex. filtrage croisé entre deux tables de faits partageant une dimension commune, nécessaire à un visuel particulier) ;
2. **aucune relation plusieurs-à-plusieurs n'existe sans table de jonction explicite** — c'est-à-dire une table intermédiaire dédiée qui porte la relation `*:*` en la décomposant en deux relations `*:1`.

Cette règle est complémentaire de [BP-01](01_Relations.md), qui contrôle la topologie générale en étoile (rôle des tables et sens des relations) : BP-03 se concentre spécifiquement sur la propriété `crossFilteringBehavior` et sur la légitimité des cardinalités `*:*`.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de relations du modèle ;
- du nom des tables et des colonnes impliquées ;
- de l'ordre des propriétés dans les fichiers TMDL ;
- de la présence ou non d'une justification documentée en commentaire.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\relationships.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\
```

L'agent doit charger l'intégralité de `relationships.tmdl` (source principale de la règle) ; les fichiers `tables/*.tmdl` ne sont consultés qu'en appui, pour vérifier si une table candidate à un rôle de table de jonction (peu de colonnes, uniquement des clés étrangères, aucune mesure ni attribut descriptif) existe réellement dans le modèle.

---

## 3. Élément(s) / propriété(s) à contrôler

**Relation bidirectionnelle** — la propriété décisionnelle est `crossFilteringBehavior`. Lorsqu'elle est absente, le filtrage est **à sens unique** (single direction) par défaut :

```tmdl
relationship AutoDetected_04792bd7-6479-4ee6-8d14-fc0d680fe50f
	fromColumn: F_RESPONSES.CAMPAIGN_ID
	toColumn: D_CAMPAIGNS.CAMPAIGN_ID
```

Ici, aucune propriété `crossFilteringBehavior` n'est présente : la relation est donc **conforme par défaut** (filtrage à sens unique, de `D_CAMPAIGNS` vers `F_RESPONSES`).

Une relation bidirectionnelle ajoute explicitement la propriété suivante :

```tmdl
relationship <guid>
	fromColumn: F_RESPONSES.CAMPAIGN_ID
	toColumn: D_CAMPAIGNS.CAMPAIGN_ID
	crossFilteringBehavior: bothDirections
```

**Relation plusieurs-à-plusieurs** — la propriété décisionnelle est la combinaison de `fromCardinality` et `toCardinality`. Par défaut (les deux propriétés absentes), la relation est `many:one`. Une relation `*:*` explicite ajoute :

```tmdl
relationship <guid>
	fromColumn: F_TABLE_A.SHARED_KEY
	toColumn: F_TABLE_B.SHARED_KEY
	fromCardinality: many
	toCardinality: many
```

**Table de jonction candidate** — pour qu'une relation `*:*` soit considérée comme justifiée, l'agent doit trouver, référencée dans le modèle, une table intermédiaire qui porte deux relations `*:1` distinctes vers chacune des deux tables concernées, sur les mêmes colonnes logiques :

```tmdl
table T_JOIN_CAMPAIGN_USAGE
	column CAMPAIGN_ID
		dataType: string
	column AI_USAGE_FREQ_LEVEL
		dataType: string
```

avec deux relations `*:1` : `T_JOIN_CAMPAIGN_USAGE.CAMPAIGN_ID -> D_CAMPAIGNS.CAMPAIGN_ID` et `T_JOIN_CAMPAIGN_USAGE.AI_USAGE_FREQ_LEVEL -> D_USAGE_FREQUENCY_LEVELS.USAGE_FREQUENCY_LEVELS`.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `F_RESPONSES.CAMPAIGN_ID -> D_CAMPAIGNS.CAMPAIGN_ID`, `crossFilteringBehavior` absent | `OK` | Filtrage à sens unique par défaut, conforme. |
| `F_RESPONSES.CAMPAIGN_USER_LOGIN -> D_USERS.CAMPAIGN_USER_LOGIN`, `crossFilteringBehavior` absent | `OK` | Idem, aucune propriété bidirectionnelle déclarée. |
| `F_ADOPTION_QUESTION.CAMPAIGN_ID -> D_CAMPAIGNS.CAMPAIGN_ID`, `crossFilteringBehavior: bothDirections` | `KO` | Bidirectionnel explicite sans table de jonction ni justification structurelle. |
| `F_TABLE_A.KEY -> F_TABLE_B.KEY`, `fromCardinality: many`, `toCardinality: many`, aucune table de jonction identifiée | `KO` | Relation `*:*` directe non justifiée. |
| `T_JOIN_X.KEY_A -> D_A.KEY_A` et `T_JOIN_X.KEY_B -> D_B.KEY_B`, table `T_JOIN_X` ne portant que des clés étrangères | `OK` | Relation `*:*` logique correctement décomposée via une table de jonction dédiée. |
| `P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order' -> D_CHOICE.'ID '` | `NA` | Relation impliquant une table paramètre (`P_`), hors périmètre analytique de cette règle. |
| `crossFilteringBehavior` présent avec une valeur non reconnue (ni `singleDirection`, ni `bothDirections`, ni `automatic`) | `NA` | Valeur non interprétable de façon fiable. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Charger `relationships.tmdl` et extraire tous les blocs `relationship`.
2. Charger `tables/*.tmdl` pour disposer de la liste des colonnes de chaque table (support à l'identification des tables de jonction).
3. Si `relationships.tmdl` est introuvable, retourner `NON_EVALUE`.

### Étape 2 — Contrôler chaque relation vis-à-vis du filtrage bidirectionnel
Pour chaque relation : lire `crossFilteringBehavior` ; normaliser sa valeur ; si `bothDirections`, rechercher une justification structurelle (voir section 6) ; sinon, marquer la relation `OK` sur ce volet.

### Étape 3 — Contrôler chaque relation vis-à-vis de la cardinalité `*:*`
Pour chaque relation : résoudre `fromCardinality`/`toCardinality` (explicite ou défaut `many:one`) ; si `many:many`, rechercher une table de jonction candidate référencée par deux relations `*:1` distinctes vers les tables concernées ; si trouvée, marquer `OK` avec preuve ; sinon, marquer `KO`.

### Étape 4 — Combiner les deux volets par relation
Une relation peut être non conforme sur un seul des deux volets (bidirectionnel OU `*:*`) : les deux volets sont évalués indépendamment puis combinés (`KO` si l'un des deux volets est `KO`).

### Étape 5 — Ne pas s'arrêter à la première anomalie
L'agent analyse l'intégralité des relations, même après une première détection `KO`.

### Étape 6 — Terminer l'analyse
Produire : le nombre total de relations analysées ; le nombre de relations `OK`/`KO`/`NA` ; le détail des relations bidirectionnelles non justifiées ; le détail des relations `*:*` non justifiées ; la liste des tables de jonction identifiées comme justification valide.

---

## 6. Détection robuste / normalisation

**Normalisation des valeurs** — `crossFilteringBehavior` et les propriétés de cardinalité doivent être comparées après suppression des espaces et mise en minuscules :

```python
normalized = str(raw_value).strip().lower()
```

Ainsi `bothDirections`, `BothDirections`, `bothdirections` sont tous reconnus comme équivalents.

**Valeurs reconnues pour `crossFilteringBehavior`** : `singledirection` (ou absence de la propriété, équivalente), `bothdirections`, `automatic`. La valeur `automatic` doit être traitée comme `singledirection` sauf si la relation relie deux tables en cardinalité `1:1`, cas marginal où `automatic` équivaut à `bothdirections` — ce cas doit être signalé en `NA` s'il ne peut être confirmé avec certitude, plutôt que présumé conforme.

**Identification d'une table de jonction légitime** — une table candidate doit cumuler ces caractéristiques :

1. elle porte au moins deux relations sortantes en `*:1` vers deux tables distinctes du modèle ;
2. elle ne porte aucune mesure DAX et peu ou pas de colonnes descriptives au-delà des clés étrangères concernées (heuristique : nombre de colonnes non-clé ≤ 2) ;
3. elle n'est elle-même jamais visée comme `toColumn` par une autre relation (elle n'est pas une dimension description mais une table pivot).

```python
def is_valid_junction_table(table, relationships):
    outgoing = [r for r in relationships if r.from_table == table.name and resolve_cardinality(r) == ("many", "one")]
    distinct_targets = {r.to_table for r in outgoing}
    non_key_columns = [c for c in table.columns if not looks_like_foreign_key(c)]
    never_targeted = not any(r.to_table == table.name for r in relationships)
    return len(distinct_targets) >= 2 and len(non_key_columns) <= 2 and never_targeted
```

**Ordre des propriétés** : `fromColumn`, `toColumn`, `fromCardinality`, `toCardinality`, `crossFilteringBehavior` peuvent apparaître dans n'importe quel ordre dans le bloc `relationship` ; l'agent doit les rechercher par nom de propriété et non par position.

**Guillemets et espaces dans les noms de colonnes** : comme pour BP-01, les noms contenant des espaces sont entourés de guillemets simples (`D_CHOICE.'ID '`) — l'agent doit les dépouiller avant toute comparaison.

---

## 7. Pseudo-code détaillé

```python
def resolve_cross_filtering(rel):
    raw = rel.get_property("crossFilteringBehavior")
    if raw is None:
        return "singledirection"
    normalized = str(raw).strip().lower()
    if normalized in {"singledirection", "bothdirections", "automatic"}:
        return normalized
    return "unknown"


def resolve_cardinality(rel):
    from_card = str(rel.get_property("fromCardinality") or "many").strip().lower()
    to_card = str(rel.get_property("toCardinality") or "one").strip().lower()
    return from_card, to_card


def find_junction_table(rel, tables, relationships):
    # Cherche une table tierce reliée en *:1 à la fois à from_table et à to_table
    for table in tables:
        if table.name in {rel.from_table, rel.to_table}:
            continue
        if is_valid_junction_table(table, relationships):
            targets = {r.to_table for r in relationships if r.from_table == table.name}
            if rel.from_table in targets and rel.to_table in targets:
                return table.name
    return None


def evaluate_relationship(rel, tables, relationships, out_of_scope_tables):
    if rel.from_table in out_of_scope_tables or rel.to_table in out_of_scope_tables:
        return {"status": "NA", "reason": "Relation impliquant une table hors périmètre analytique (paramètre/technique)"}

    issues = []

    cross_filter = resolve_cross_filtering(rel)
    if cross_filter == "unknown":
        return {"status": "NA", "reason": "Valeur crossFilteringBehavior non reconnue"}
    if cross_filter == "bothdirections":
        issues.append("Relation bidirectionnelle (crossFilteringBehavior: bothDirections) sans justification documentée")

    from_card, to_card = resolve_cardinality(rel)
    if from_card == "many" and to_card == "many":
        junction = find_junction_table(rel, tables, relationships)
        if junction is None:
            issues.append("Cardinalité *:* directe sans table de jonction identifiée")
        # si une table de jonction est trouvée, ce volet est conforme : rien à ajouter

    if issues:
        return {"status": "KO", "reasons": issues}
    return {"status": "OK"}
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
| Aucune relation bidirectionnelle, aucune `*:*` non justifiée | `OK` |
| Au moins une relation bidirectionnelle non justifiée ou `*:*` sans table de jonction | `KO` |
| Aucun `KO`, mais au moins une relation `crossFilteringBehavior` illisible | `NA` |
| Relations `KO` et `NA` présentes simultanément | `KO`, avec analyse partielle signalée |

---

## 9. Structure du résultat

Exemple lorsque la bonne pratique est respectée (état actuel du projet audité — aucune des 8 relations de `relationships.tmdl` ne porte `crossFilteringBehavior` ni de cardinalité `*:*` explicite) :

```json
{
  "rule_id": "BP-03",
  "rule_name": "Éviter les relations bidirectionnelles et many-to-many non justifiées",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_relationships": 8,
  "ok_relationships": 6,
  "ko_relationships": 0,
  "na_relationships": 2,
  "bidirectional_ko": [],
  "many_to_many_ko": [],
  "na_details": [
    {"from": "P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'", "to": "D_CHOICE.'ID '", "reason": "Table paramètre hors périmètre"}
  ]
}
```

Exemple avec anomalies :

```json
{
  "rule_id": "BP-03",
  "rule_name": "Éviter les relations bidirectionnelles et many-to-many non justifiées",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_relationships": 9,
  "ok_relationships": 7,
  "ko_relationships": 2,
  "na_relationships": 0,
  "ko_details": [
    {
      "from": "F_ADOPTION_QUESTION.CAMPAIGN_ID",
      "to": "D_CAMPAIGNS.CAMPAIGN_ID",
      "reasons": ["Relation bidirectionnelle (crossFilteringBehavior: bothDirections) sans justification documentée"]
    },
    {
      "from": "F_MONORESPONSES.CAMPAIGN_USER_LOGIN",
      "to": "F_SCORERESPONSES.CAMPAIGN_USER_LOGIN",
      "reasons": ["Cardinalité *:* directe sans table de jonction identifiée"]
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-03 — Relations bidirectionnelles / many-to-many : OK

6 relations analysées sur ce volet (2 relations hors périmètre,
impliquant des tables paramètres). Aucune relation ne porte
crossFilteringBehavior: bothDirections, aucune cardinalité *:*
directe non justifiée n'a été détectée.

Toutes les relations utilisent le filtrage à sens unique par défaut
et la cardinalité *:1 standard.
```

### Exemple `KO`

```text
BP-03 — Relations bidirectionnelles / many-to-many : KO

7 relations conformes sur 9 relations analysées.

Relations non conformes :
- F_ADOPTION_QUESTION.CAMPAIGN_ID -> D_CAMPAIGNS.CAMPAIGN_ID :
  crossFilteringBehavior = bothDirections, sans justification
  identifiable dans le modèle. Risque d'ambiguïté de filtrage avec
  la relation équivalente déjà portée par F_RESPONSES.
- F_MONORESPONSES.CAMPAIGN_USER_LOGIN -> F_SCORERESPONSES.CAMPAIGN_USER_LOGIN :
  cardinalité *:* directe entre deux tables de faits, sans table de
  jonction dédiée.

Correction attendue :
repasser la relation F_ADOPTION_QUESTION -> D_CAMPAIGNS en filtrage
à sens unique (supprimer crossFilteringBehavior ou le régler sur
singleDirection), sauf si un visuel documenté exige explicitement le
filtrage croisé ; pour la relation *:* entre F_MONORESPONSES et
F_SCORERESPONSES, introduire une table de jonction dédiée ou
redéfinir le grain commun des deux tables de faits.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- `relationships.tmdl` a été localisé et intégralement parsé ;
- pour chaque relation, la valeur de `crossFilteringBehavior` a été résolue (explicite ou valeur par défaut `singleDirection`) ;
- pour chaque relation, la cardinalité (`fromCardinality`/`toCardinality`) a été résolue (explicite ou valeur par défaut `many:one`) ;
- aucune relation ne porte `crossFilteringBehavior: bothDirections` sans qu'une table de jonction ou une justification structurelle équivalente n'ait été recherchée et documentée comme absente ;
- aucune relation `*:*` n'a été laissée sans recherche explicite d'une table de jonction candidate dans le modèle ;
- l'intégralité des relations du fichier a été parcourue.

L'agent ne doit jamais produire `OK` en se basant sur l'absence apparente de la propriété `crossFilteringBehavior` sans avoir également vérifié la cardinalité de la relation, ni conclure qu'une relation `*:*` est justifiée sans avoir effectivement localisé la table de jonction correspondante dans le modèle.

---

## 12. Résumé de la règle

```text
RÈGLE BP-03

POUR chaque relation de relationships.tmdl
    SI la relation implique une table paramètre/technique
        relation = NA
        PASSER à la relation suivante

    RÉSOUDRE crossFilteringBehavior (défaut = singleDirection)
    SI valeur non reconnue
        relation = NA ; PASSER à la relation suivante
    SI crossFilteringBehavior = bothDirections
        SIGNALER anomalie bidirectionnelle

    RÉSOUDRE fromCardinality / toCardinality (défaut = many:one)
    SI cardinalité = many:many
        RECHERCHER une table de jonction reliée en *:1 aux deux tables
        SI aucune trouvée
            SIGNALER anomalie *:* non justifiée

    SI au moins une anomalie signalée
        relation = KO
    SINON
        relation = OK

    ENREGISTRER le résultat avec preuve
FIN POUR

SI au moins une relation est KO
    règle = KO
SINON SI au moins une relation est NA
    règle = NA
SINON
    règle = OK

AFFICHER toutes les relations KO avec le détail des anomalies
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-03 — Relations bidirectionnelles / many-to-many      │
│         non justifiées                                          │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │ Charger relationships.tmdl   │
          │ Charger tables/*.tmdl         │
          └──────────────┬────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ Trouvé ✅   ║    │ relationships.tmdl    │
         ╚════╤════════╝    │ introuvable ❌         │
              │              └──────────┬────────────┘
              │                         ▼
              │                 ┌───────────────────┐
              │                 │ Retour : NON_EVALUE│
              │                 └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque relation de relationships.tmdl │
   │ (boucle, jusqu'à épuisement — pas d'arrêt  │
   │  à la première anomalie)                   │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ Table from/to = PARAMETER/TECHNICAL ?│
        └───────┬──────────────────┬───────────┘
              oui│                  │non
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────────┐
         ║ relation = NA ║  │ Résoudre crossFilteringBehavior│
         ╚═══════════════╝  │ (défaut = singleDirection)     │
                             └───────────────┬─────────────────┘
                                             ▼
                             ┌────────────────────────────┐
                             │ Valeur reconnue ?            │
                             │ (singleDirection/bothDirections/automatic)│
                             └───────┬──────────────┬────────┘
                                  non│                │oui
                                     ▼                ▼
                          ╔═══════════════╗  ┌────────────────────────┐
                          ║ relation = NA ║  │ = bothDirections ?      │
                          ╚═══════════════╝  └──────┬──────────┬───────┘
                                                   oui│           │non
                                                      ▼           ▼
                                        ┌─────────────────────┐  │
                                        │ SIGNALER anomalie     │  │
                                        │ "bidirectionnelle"    │  │
                                        └──────────┬─────────────┘
                                                    │◄──────────────┘
                                                    ▼
                                    ┌──────────────────────────────┐
                                    │ Résoudre cardinalité           │
                                    │ (défaut many:one)              │
                                    │ = many:many ?                  │
                                    └───────┬──────────────┬──────────┘
                                          non│                │oui
                                             ▼                ▼
                                             │      ┌──────────────────────────┐
                                             │      │ Rechercher une table de   │
                                             │      │ jonction (*:1 vers les    │
                                             │      │ deux tables) ?            │
                                             │      └──────┬─────────────┬───────┘
                                             │          trouvée│          │absente
                                             │             ▼             ▼
                                             │             │   ┌─────────────────────┐
                                             │             │   │ SIGNALER anomalie     │
                                             │             │   │ "*:* non justifiée"   │
                                             │             │   └──────────┬────────────┘
                                             │◄────────────┘◄─────────────┘
                                             ▼
                                ┌────────────────────────────┐
                                │ Au moins une anomalie        │
                                │ signalée pour la relation ?  │
                                └───────┬──────────────┬────────┘
                                     oui│                │non
                                        ▼                ▼
                             ╔═══════════════╗   ╔═══════════════╗
                             ║ relation = KO ║   ║ relation = OK ║
                             ╚═══════════════╝   ╚═══════════════╝
                       │
                       ▼ (ENREGISTRER le résultat, boucle suivante)
   ┌────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL (priorité KO > NA > OK) │
   │ SI au moins une relation KO    → règle = KO     │
   │ SINON SI au moins une relation NA → règle = NA  │
   │ SINON                            → règle = OK   │
   └───────────────────────┬────────────────────────┘
                            ▼
                RETOUR rule_status (OK / KO / NA)
```
