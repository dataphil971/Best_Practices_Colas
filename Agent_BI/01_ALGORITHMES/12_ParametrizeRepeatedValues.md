# BP-12 — Paramétrer les valeurs littérales répétées dans le code Power Query

## 1. Objectif de la bonne pratique

Lorsqu'une même valeur littérale — une URL de site SharePoint, un chemin de fichier, un nom de catalogue, une chaîne de connexion — est recopiée telle quelle dans plusieurs requêtes Power Query (M), toute évolution de cette valeur (migration de site, changement d'environnement, renommage) impose de la modifier à **chaque occurrence individuellement**, avec un risque élevé d'oubli et d'incohérence entre requêtes. Extraire cette valeur dans un **paramètre Power Query dédié** (`expression <Nom> = <valeur> meta [IsParameterQuery=true, ...]`), puis référencer ce paramètre partout où la valeur était auparavant recopiée en dur, centralise la maintenance en un point unique et rend le modèle plus robuste aux changements d'environnement.

L'objectif de cette règle est de détecter les **littéraux textuels répétés** dans le code M du modèle (tables et expressions partagées) et de vérifier qu'ils sont effectivement extraits sous forme de paramètre lorsque leur fréquence de répétition dépasse un seuil, plutôt que recopiés en dur à chaque occurrence.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de requêtes du modèle ;
- de la nature exacte du littéral répété (URL, chemin, identifiant technique, nom de catalogue) ;
- de l'ordre des requêtes dans `expressions.tmdl` et dans les fichiers de tables ;
- du fait que les paramètres existants portent ou non un nom évocateur.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\expressions.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\
```

L'agent doit charger `expressions.tmdl` (requêtes partagées et paramètres) et l'ensemble des fichiers `tables/*.tmdl` (partitions M des tables), afin de disposer du code M complet du modèle pour la recherche de littéraux répétés.

---

## 3. Élément(s) / propriété(s) à contrôler

Littéral effectivement répété dans ce projet — l'URL de site SharePoint `"https://colase4.sharepoint.com/sites/BaromtreIA"` apparaît en dur dans au moins huit requêtes distinctes d'`expressions.tmdl` (`D_ANSWERS`, `D_INTEREST_LEVELS`, `D_RECEIVED_TRAINING_LEVELS`, `D_RESOURCE_VISIBILITY_LEVELS`, `D_SELF_PERCEIVED_KNOWLEDGE_LEVELS`, `D_WORRY_LEVELS`, `D_USAGE_LEVELS`, `D_TESTED_KNOWLEDGE_LEVELS`, `D_AREA`, `D_TRANSLATION_AREA`, `SOURCE`, `Exemple_fichier_source`) :

```tmdl
expression D_ANSWERS =
		let
		    Source = SharePoint.Tables("https://colase4.sharepoint.com/sites/BaromtreIA", [Implementation="2.0", ViewMode="All"]),
		    ...
```

```tmdl
expression D_INTEREST_LEVELS =
		let
		    Source = SharePoint.Tables("https://colase4.sharepoint.com/sites/BaromtreIA", [Implementation="2.0", ViewMode="All"]),
		    ...
```

À titre de contre-exemple positif déjà présent dans ce même projet, deux valeurs de configuration technique **sont** correctement extraites en paramètres et référencées par identifiant plutôt que recopiées :

```tmdl
expression SPARK_Hostname = "adb-288922581088579.19.azuredatabricks.net" meta [IsParameterQuery=true, List={"adb-288922581088579.19.azuredatabricks.net"}, DefaultValue="adb-288922581088579.19.azuredatabricks.net", Type="Text", IsParameterQueryRequired=false]

expression SPARK_HTTP_Path = "/sql/1.0/warehouses/67e09c513f78a526" meta [IsParameterQuery=true, ...]
```

puis référencées par leur nom dans `D_STRUCTURES` :

```tmdl
Databricks.Catalogs(SPARK_Hostname, SPARK_HTTP_Path, [...])
```

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `SPARK_Hostname` extrait en paramètre, référencé dans `D_STRUCTURES` | `OK` | Valeur technique correctement paramétrée et référencée par nom. |
| `SPARK_HTTP_Path` extrait en paramètre, référencé dans `D_STRUCTURES` | `OK` | Idem. |
| `ReferentialEnvironment` extrait en paramètre avec liste de valeurs (`onecolasdata`/`onecolasdatarec`/`onecolasdatadev`) | `OK` | Paramètre de bascule d'environnement correctement centralisé. |
| `"https://colase4.sharepoint.com/sites/BaromtreIA"` recopiée en dur dans au moins 8 requêtes distinctes | `KO` | Littéral fortement répété, jamais extrait en paramètre malgré une fréquence largement supérieure au seuil de tolérance. |
| Littéral `"2.0"` (valeur `Implementation="2.0"` de `SharePoint.Tables`) répété dans les mêmes requêtes | `NA` | Paramètre technique du connecteur, non métier, à exclure de l'analyse (valeur imposée par l'API SharePoint, pas un point de configuration du projet). |
| Littéral présent une seule fois dans tout le modèle | `NA` | Sous le seuil de répétition : aucune recommandation de paramétrage nécessaire. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Charger `expressions.tmdl` et tous les fichiers `tables/*.tmdl`.
2. Extraire le code M de chaque requête (expressions partagées et partitions de tables).
3. Si aucun fichier n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Extraire tous les littéraux textuels du code M
Pour chaque requête : tokeniser le code M et extraire toutes les chaînes de caractères entre guillemets doubles, en excluant les noms d'étapes (`#"Nom d'étape"`) et les noms de colonnes utilisés comme clés d'accès (`[NomColonne]`).

### Étape 3 — Compter les occurrences de chaque littéral distinct
Regrouper les occurrences par valeur exacte de littéral, en conservant la liste des requêtes où chaque littéral apparaît.

### Étape 4 — Exclure les littéraux hors périmètre
Filtrer les littéraux trop courts, les valeurs techniques imposées par la signature d'une fonction connecteur (`Implementation="2.0"`, `ApiVersion=15`, noms de types M), et les littéraux qui varient légèrement d'une occurrence à l'autre (donc non réellement dupliqués).

### Étape 5 — Vérifier si chaque littéral fréquent est déjà porté par un paramètre
Pour chaque littéral dont la fréquence dépasse le seuil : rechercher, parmi les paramètres déclarés (`IsParameterQuery=true`), un paramètre dont la valeur par défaut (`DefaultValue`) correspond exactement à ce littéral. Si trouvé, vérifier que le littéral brut n'est plus utilisé en parallèle dans le code (auquel cas la centralisation est incomplète).

### Étape 6 — Ne pas s'arrêter au premier littéral détecté
L'agent analyse l'intégralité des littéraux candidats du modèle, même après une première détection conforme ou non conforme.

### Étape 7 — Terminer l'analyse
Produire : la liste des littéraux répétés au-delà du seuil, avec leur fréquence et les requêtes concernées ; leur statut (`OK` si déjà paramétré, `KO` sinon) ; la liste des paramètres déjà en place, à titre de bonne pratique constatée.

---

## 6. Détection robuste / normalisation

**Extraction des littéraux** — l'agent doit tokeniser le code M en tenant compte de l'échappement des guillemets doubles (`""` à l'intérieur d'une chaîne M représente un guillemet littéral) et ignorer les noms d'étapes entre `#"..."`, qui ne sont pas des valeurs de configuration :

```python
def extract_string_literals(m_code, exclude_step_names=True):
    literals = []
    for match in re.finditer(r'(?<!#)"((?:[^"]|"")*)"', m_code):
        value = match.group(1).replace('""', '"')
        literals.append(value)
    return literals
```

**Filtrage des faux positifs** — un littéral n'est retenu comme candidat que s'il :

1. dépasse une longueur minimale (`len(value) >= 8`, pour écarter les codes courts type `"2.0"`, `"All"`) ;
2. n'est pas un mot-clé ou une valeur d'énumération standard du connecteur (`Implementation`, `ViewMode`, noms de types M tels que `type text`) ;
3. n'est pas une valeur qui varie systématiquement d'une occurrence à l'autre malgré une structure commune (ex. des noms d'étapes générés automatiquement comme des GUID `#"9467e4ce-e691-47d1-b165-e351f997f638"`, qui ne sont jamais de véritables doublons).

```python
TECHNICAL_ENUM_VALUES = {"2.0", "all", "true", "false"}

def is_candidate_literal(value):
    if len(value) < 8:
        return False
    if value.strip().lower() in TECHNICAL_ENUM_VALUES:
        return False
    if re.fullmatch(r"[0-9a-f-]{20,}", value, re.I):   # GUID d'élément SharePoint, jamais un doublon voulu
        return False
    return True
```

**Seuil de répétition** (paramétrable) :

```text
REPETITION_KO_THRESHOLD = 3   # un littéral candidat présent dans 3 requêtes distinctes ou plus doit être paramétré
```

**Correspondance littéral ↔ paramètre existant** : la comparaison doit être exacte sur la valeur (après dépouillement des guillemets échappés), mais insensible aux espaces de début/fin. Un paramètre dont la `DefaultValue` correspond au littéral, même si le nom du paramètre ne l'évoque pas explicitement, doit être reconnu comme couverture valide.

```python
def is_already_parametrized(literal_value, parameters):
    return any(
        normalize(param.get_meta("DefaultValue")) == normalize(literal_value)
        for param in parameters
    )
```

**Paramétrage partiel** : si un paramètre existe pour la valeur mais que le littéral brut continue d'apparaître dans au moins une requête (le paramètre n'a pas été propagé partout), le cas doit être classé `KO` avec la mention explicite des requêtes non migrées, distincte du cas où aucun paramètre n'existe du tout.

---

## 7. Pseudo-code détaillé

```python
def collect_all_m_bodies(table_files, expressions_file):
    bodies = {}
    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        if table.has_m_partition():
            bodies[table.name] = table.partition.source_expression
    if expressions_file_exists(expressions_file):
        for expr in parse_tmdl_expressions(expressions_file):
            if expr.is_data_query():
                bodies[expr.name] = expr.body
    return bodies


def build_literal_frequency_map(m_bodies):
    frequency = {}
    for query_name, body in m_bodies.items():
        literals = {lit for lit in extract_string_literals(body) if is_candidate_literal(lit)}
        for literal in literals:
            frequency.setdefault(literal, set()).add(query_name)
    return frequency


def evaluate_literal(literal, queries_using_it, parameters):
    if len(queries_using_it) < REPETITION_KO_THRESHOLD:
        return {"literal": literal, "status": "NA",
                "reason": f"Répété dans seulement {len(queries_using_it)} requête(s), sous le seuil"}

    if is_already_parametrized(literal, parameters):
        return {"literal": literal, "status": "OK", "queries": sorted(queries_using_it)}

    return {"literal": literal, "status": "KO", "queries": sorted(queries_using_it),
            "reason": f"Littéral recopié en dur dans {len(queries_using_it)} requêtes sans paramètre dédié"}


m_bodies = collect_all_m_bodies(table_files, expressions_file)
parameters = [e for e in parse_tmdl_expressions(expressions_file) if e.get_meta("IsParameterQuery") == "true"]
frequency_map = build_literal_frequency_map(m_bodies)

results = [
    evaluate_literal(literal, queries, parameters)
    for literal, queries in frequency_map.items()
]
```

---

## 8. Calcul du statut global

```python
significant_results = [r for r in results if r["status"] != "NA"]

if any(r["status"] == "KO" for r in significant_results):
    rule_status = "KO"
elif not significant_results:
    rule_status = "OK"   # aucun littéral n'atteint le seuil de répétition, rien à paramétrer
else:
    rule_status = "OK"
```

Cette règle utilise un statut `WARN` équivalent à `KO` pour signaler une recommandation ferme mais non strictement bloquante selon le contexte de gouvernance du projet ; par défaut, un littéral métier répété au-delà du seuil sans paramètre est traité comme `KO`, car il s'agit d'une dette de maintenance directe. Priorité des statuts : `KO > OK` (le statut `NA` des littéraux sous le seuil n'influence jamais le résultat global, il documente simplement l'absence de recommandation sur ces littéraux).

| Résultat de l'analyse | Statut global |
|---|---|
| Tous les littéraux répétés au-delà du seuil sont déjà couverts par un paramètre, sans occurrence résiduelle en dur | `OK` |
| Au moins un littéral répété au-delà du seuil n'est couvert par aucun paramètre, ou seulement partiellement | `KO` |
| Aucun littéral n'atteint le seuil de répétition dans l'ensemble du modèle | `OK` |

---

## 9. Structure du résultat

Exemple avec littéral non paramétré (état actuel du projet audité pour l'URL SharePoint) :

```json
{
  "rule_id": "BP-12",
  "rule_name": "Paramétrer les valeurs littérales répétées dans le code Power Query",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "candidate_literals_evaluated": 3,
  "ok_details": [
    {"literal": "adb-288922581088579.19.azuredatabricks.net", "queries": ["D_STRUCTURES"], "status": "OK",
     "reason": "Déjà couvert par le paramètre SPARK_Hostname"}
  ],
  "ko_details": [
    {
      "literal": "https://colase4.sharepoint.com/sites/BaromtreIA",
      "queries": ["D_ANSWERS", "D_AREA", "D_INTEREST_LEVELS", "D_RECEIVED_TRAINING_LEVELS",
                   "D_RESOURCE_VISIBILITY_LEVELS", "D_SELF_PERCEIVED_KNOWLEDGE_LEVELS",
                   "D_TESTED_KNOWLEDGE_LEVELS", "D_TRANSLATION_AREA", "D_USAGE_LEVELS",
                   "D_WORRY_LEVELS", "Exemple_fichier_source", "SOURCE"],
      "reason": "Littéral recopié en dur dans 12 requêtes sans paramètre dédié"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `KO` (état actuel du projet audité)

```text
BP-12 — Paramétrage des valeurs littérales répétées : KO

L'URL de site SharePoint "https://colase4.sharepoint.com/sites/BaromtreIA"
est recopiée en dur dans 12 requêtes Power Query distinctes
(D_ANSWERS, D_AREA, D_INTEREST_LEVELS, D_RECEIVED_TRAINING_LEVELS,
D_RESOURCE_VISIBILITY_LEVELS, D_SELF_PERCEIVED_KNOWLEDGE_LEVELS,
D_TESTED_KNOWLEDGE_LEVELS, D_TRANSLATION_AREA, D_USAGE_LEVELS,
D_WORRY_LEVELS, Exemple_fichier_source, SOURCE), sans paramètre
dédié — alors que les identifiants Databricks (SPARK_Hostname,
SPARK_HTTP_Path) sont, eux, déjà correctement extraits en
paramètres.

Correction attendue :
créer un paramètre Power Query (ex. SharePointSiteUrl, type Text,
valeur par défaut "https://colase4.sharepoint.com/sites/BaromtreIA")
dans expressions.tmdl, puis remplacer chaque occurrence en dur de
cette URL par une référence au paramètre dans les 12 requêtes
concernées, à l'image de ce qui a déjà été fait pour SPARK_Hostname
et SPARK_HTTP_Path.
```

### Exemple `OK`

```text
BP-12 — Paramétrage des valeurs littérales répétées : OK

Aucun littéral métier répété au-delà du seuil de 3 occurrences n'a
été trouvé sans paramètre correspondant. Les valeurs de configuration
technique identifiées (hôte Databricks, chemin HTTP, environnement
référentiel) sont toutes extraites en paramètres dédiés et
référencées par nom dans les requêtes concernées.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- `expressions.tmdl` et tous les fichiers `tables/*.tmdl` ont été chargés et le code M de toutes les requêtes a été extrait ;
- tous les littéraux textuels candidats ont été recensés avec leur fréquence d'apparition à travers l'ensemble des requêtes ;
- pour chaque littéral atteignant le seuil de répétition, la présence d'un paramètre correspondant a été vérifiée par comparaison de valeur (pas seulement par présomption sur le nom) ;
- pour chaque littéral déjà couvert par un paramètre, l'absence d'occurrence résiduelle en dur dans une autre requête a été vérifiée ;
- l'intégralité des requêtes du modèle a été parcourue pour la recherche de littéraux, sans se limiter aux tables physiques.

L'agent ne doit jamais produire `OK` en se fondant sur la seule existence de paramètres bien nommés (`SPARK_Hostname`, `ReferentialEnvironment`) sans avoir recherché, de façon exhaustive, d'autres littéraux répétés qui ne bénéficient d'aucun paramètre.

---

## 12. Résumé de la règle

```text
RÈGLE BP-12

COLLECTER le code M de toutes les requêtes (tables + expressions partagées)
EXTRAIRE tous les littéraux textuels candidats (longueur suffisante, hors énumérations techniques et GUID)
COMPTER la fréquence de chaque littéral distinct à travers les requêtes

POUR chaque littéral dont la fréquence >= seuil de répétition
    RECHERCHER un paramètre (IsParameterQuery=true) dont DefaultValue correspond exactement

    SI paramètre trouvé ET aucune occurrence brute résiduelle
        littéral = OK
    SINON
        littéral = KO

    ENREGISTRER le résultat avec la liste des requêtes concernées
FIN POUR

SI au moins un littéral significatif est KO
    règle = KO
SINON
    règle = OK

AFFICHER tous les littéraux KO avec la liste des requêtes à migrer vers un paramètre
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-12 — Paramétrer les valeurs littérales répétées         │
└────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
              ┌────────────────────────────────────┐
              │ Charger expressions.tmdl             │
              │ + tous les fichiers tables/*.tmdl    │
              └────────────────┬──────────────────────┘
                              │
                   ┌──────────┴──────────┐
                   ▼                     ▼
             ╔═════════════╗     ┌──────────────────┐
             ║ Fichiers    ║     │ Aucun fichier      │
             ║ trouvés ✅  ║     │ trouvé ❌           │
             ╚══════╤══════╝     └─────────┬──────────┘
                    │                      │
                    │                      ▼
                    │              ┌────────────────┐
                    │              │ Retour :        │
                    │              │ NON_EVALUE      │
                    │              └────────────────┘
                    ▼
       ┌───────────────────────────────────────┐
       │ EXTRAIRE tous les littéraux textuels    │
       │ de chaque requête (code M)              │
       └────────────────┬─────────────────────────┘
                        ▼
       ┌───────────────────────────────────────┐
       │ FILTRER les candidats                   │
       │ (longueur >= 8, hors énumérations       │
       │ techniques, hors GUID)                  │
       └────────────────┬─────────────────────────┘
                        ▼
       ┌───────────────────────────────────────┐
       │ REGROUPER par valeur exacte             │
       │ → fréquence + requêtes concernées       │
       └────────────────┬─────────────────────────┘
                        ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque littéral candidat distinct     │
     │ (boucle)                                   │
     └────────────────┬────────────────────────────┘
                      ▼
           ┌──────────────────────────┐
           │ fréquence < seuil (3) ?   │
           └──────────┬────────────────┘
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
     ╔═══════════╗        ┌──────────────────────────┐
     ║ OUI        ║        │ NON (>= seuil) :          │
     ║ littéral   ║        │ RECHERCHER un paramètre   │
     ║ = NA       ║        │ IsParameterQuery=true dont │
     ╚═══════════╝        │ DefaultValue = littéral    │
                          └─────────────┬───────────────┘
                                        │
                             ┌──────────┴──────────┐
                             ▼                     ▼
                       ╔═══════════╗        ┌───────────────────┐
                       ║ Trouvé ET  ║        │ Absent OU résidu   │
                       ║ sans résidu║        │ en dur ailleurs ❌ │
                       ║ brut ✅    ║        │ = KO                │
                       ║ = OK       ║        └───────────────────┘
                       ╚═══════════╝
                             │                     │
                             └──────────┬──────────┘
                                        ▼
                        FIN DE BOUCLE (littéral suivant)
                                        │
                                        ▼
        ┌────────────────────────────────────────────┐
        │ CALCUL DU RÉSULTAT FINAL                     │
        │ significant = littéraux avec statut != NA    │
        │ Un KO parmi significant ? → règle = KO       │
        │ Sinon (NA sous le seuil n'influence jamais   │
        │ le statut global) → règle = OK               │
        └────────────────────┬──────────────────────────┘
                             ▼
                  RETOUR rule_status (OK/KO)
```
