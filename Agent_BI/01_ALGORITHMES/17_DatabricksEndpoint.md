# BP-17 — Endpoint SQL Warehouse dédié pour les sources Databricks en DirectQuery

## 1. Objectif de la bonne pratique

Lorsqu'une table du modèle sémantique est connectée à Databricks en mode **DirectQuery** (chaque interaction du rapport déclenche une requête en temps réel vers Databricks, sans import préalable), le point de terminaison de calcul utilisé pour exécuter ces requêtes a un impact direct sur la performance et la stabilité du rapport. Le connecteur `Databricks.Catalogs(host, httpPath, [...])` accepte un `httpPath` qui peut pointer :

- vers un **SQL Warehouse** (endpoint dédié au requêtage SQL, dimensionné et isolé, avec mise à l'échelle automatique propre) — chemin de la forme `/sql/1.0/warehouses/<warehouse_id>` ;
- vers un **cluster interactif partagé** (cluster « all-purpose », mutualisé avec des notebooks, des jobs Spark ou d'autres utilisateurs) — chemin de la forme `/sql/protocolv1/o/<org_id>/<cluster_id>`.

L'objectif de cette règle est de vérifier que toute source Databricks utilisée en **DirectQuery** pointe vers un SQL Warehouse dédié plutôt qu'un cluster interactif partagé, afin de garantir :

- une **performance** prévisible (les SQL Warehouses sont optimisés pour des requêtes courtes et concurrentes, contrairement aux clusters interactifs dimensionnés pour des charges Spark) ;
- une **isolation** du rapport vis-à-vis des autres charges de travail (un notebook lourd exécuté sur le même cluster partagé peut dégrader ou bloquer les requêtes du rapport) ;
- une **stabilité des temps de réponse**, le SQL Warehouse pouvant être configuré avec une politique de mise à l'échelle et un délai d'auto-suspension adaptés à l'usage BI.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables connectées à Databricks ;
- de la façon dont le `httpPath` est fourni (littéral en dur dans le code M, ou via un paramètre M comme `SPARK_HTTP_Path`) ;
- de l'identifiant exact du warehouse ou du cluster, qui varie d'un environnement à l'autre.

Cette règle est **spécifique au mode DirectQuery** : une source Databricks utilisée en mode `import` (les données sont rapatriées une fois lors de l'actualisation, sans requêtage temps réel depuis le rapport) est hors périmètre, l'impact d'un endpoint partagé y étant limité à la seule fenêtre d'actualisation plutôt qu'à chaque interaction utilisateur.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl          (mode de partition : import / directQuery)
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl        (paramètres d'hôte / httpPath, requêtes Databricks.Catalogs)
```

Exemple pour ce projet (paramètres réels, utilisés en mode `import`) :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\expressions.tmdl
```

```tmdl
expression SPARK_Hostname = "adb-288922581088579.19.azuredatabricks.net" meta [IsParameterQuery=true, ...]
expression SPARK_HTTP_Path = "/sql/1.0/warehouses/67e09c513f78a526" meta [IsParameterQuery=true, ...]
```

Dans ce projet, la table `D_STRUCTURES` connectée à Databricks est chargée en mode `import` (`partition ... = m / mode: import`) : le mode DirectQuery n'est utilisé nulle part dans ce modèle. Le `httpPath` configuré (`/sql/1.0/warehouses/67e09c513f78a526`) correspond néanmoins déjà, par sa structure, à un SQL Warehouse dédié et non à un cluster partagé — bonne pratique respectée par anticipation si ce connecteur venait à être basculé en DirectQuery.

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1 Identifier les partitions Databricks en DirectQuery

```tmdl
partition F_LIVE_METRICS = m
    mode: directQuery
    source =
            let
                Source = Databricks.Catalogs(SPARK_Hostname, SPARK_HTTP_Path, [...])
                    {[Name="prod", Kind="Database"]}[Data]
            in
                Source
```

### 3.2 Distinguer un SQL Warehouse d'un cluster interactif via le `httpPath`

```python
import re

SQL_WAREHOUSE_PATH_PATTERN = re.compile(r"^/sql/1\.0/warehouses/[A-Za-z0-9]+$")
INTERACTIVE_CLUSTER_PATH_PATTERN = re.compile(r"^/sql/protocolv1/o/\d+/[A-Za-z0-9-]+$")
```

| Forme du `httpPath` | Type d'endpoint |
|---|---|
| `/sql/1.0/warehouses/67e09c513f78a526` | SQL Warehouse dédié (conforme) |
| `/sql/protocolv1/o/1234567890123456/0821-142233-abcd1234` | Cluster interactif partagé (non conforme en DirectQuery) |
| valeur illisible / littéral non résolvable / paramètre externe non fourni | Indéterminé |

### 3.3 Résolution du `httpPath` lorsqu'il est paramétré

Le second argument de `Databricks.Catalogs(host, httpPath, [...])` référence fréquemment un paramètre M (`SPARK_HTTP_Path` dans ce projet) plutôt qu'un littéral direct : l'agent doit résoudre ce paramètre jusqu'à sa valeur littérale déclarée dans `expressions.tmdl` avant d'appliquer les motifs de la section 3.2.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Table en DirectQuery sur Databricks, `httpPath` résolu et conforme au motif SQL Warehouse (`/sql/1.0/warehouses/...`) | `OK` | Endpoint dédié correctement configuré. |
| Table en DirectQuery sur Databricks, `httpPath` résolu et conforme au motif cluster interactif (`/sql/protocolv1/o/.../...`) | `KO` | La table pointe vers un cluster partagé, non recommandé pour du DirectQuery de production. |
| Table en DirectQuery sur Databricks, `httpPath` non résolvable (paramètre externe, valeur dynamique) | `NA` | Impossible de déterminer le type d'endpoint depuis les fichiers statiques du modèle. |
| Table en mode `import` uniquement, même connectée à Databricks | `NA` | Hors périmètre : la règle cible spécifiquement le DirectQuery. |
| Table non connectée à Databricks (`Sql.Database`, `SharePoint.Files`...) | `NA` | Hors périmètre. |
| Table en mode « hybride » (au moins une partition `directQuery` et une partition `import`, cas des tables avec actualisation incrémentielle et fenêtre temps réel) | Évaluée comme DirectQuery pour les partitions concernées | Les partitions `directQuery` sont soumises à la règle, les partitions `import` sont ignorées. |

Exemple issu du modèle audité :

| Table | Mode | Connecteur | `httpPath` résolu | Statut |
|---|---|---|---|---|
| `D_STRUCTURES` | import | `Databricks.Catalogs` (via `Value.NativeQuery`) | `/sql/1.0/warehouses/67e09c513f78a526` | `NA` (hors périmètre, mode import) |
| *(hypothèse)* `F_LIVE_METRICS` | directQuery | `Databricks.Catalogs` | `/sql/1.0/warehouses/67e09c513f78a526` | `OK` |
| *(hypothèse)* `F_LIVE_EVENTS` | directQuery | `Databricks.Catalogs` | `/sql/protocolv1/o/1234567890123456/0821-142233-abcd1234` | `KO` |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Charger `expressions.tmdl` s'il existe, pour résoudre les paramètres d'hôte et de chemin.
3. Si aucun fichier de table n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Identifier les partitions DirectQuery sur Databricks
Pour chaque table, examiner chaque partition : conserver celles dont `mode: directQuery` **et** dont la source appelle `Databricks.Catalogs`.

### Étape 3 — Résoudre le `httpPath`
Pour chaque partition retenue, extraire le second argument de `Databricks.Catalogs` ; si c'est un identifiant simple référant un paramètre M connu, résoudre sa valeur littérale dans `expressions.tmdl` ; si la valeur reste non résolvable (paramètre fourni dynamiquement à l'exécution, absent du fichier), classer `NA`.

### Étape 4 — Appliquer les motifs de classification
Comparer le `httpPath` résolu aux motifs `SQL_WAREHOUSE_PATH_PATTERN` et `INTERACTIVE_CLUSTER_PATH_PATTERN` ; attribuer le statut selon la table de décision de la section 4.

### Étape 5 — Ne pas s'arrêter à la première anomalie
Toutes les partitions DirectQuery connectées à Databricks doivent être analysées, y compris lorsqu'un même `httpPath` est réutilisé par plusieurs tables (le signaler comme un point positif de cohérence, pas comme une redite à ignorer).

### Étape 6 — Terminer l'analyse
Produire le nombre de partitions DirectQuery/Databricks détectées, la répartition `OK`/`KO`/`NA`, et le détail de chaque partition `KO`.

---

## 6. Détection robuste / normalisation

- Le nom du paramètre M portant le `httpPath` varie d'un projet à l'autre (`SPARK_HTTP_Path` dans ce projet, mais pourrait être nommé `DatabricksHttpPath`, `WarehousePath`...) : l'agent doit résoudre la valeur en suivant la référence, quel que soit le nom du paramètre, plutôt que de chercher un nom fixe.
- La casse du `httpPath` doit être normalisée en minuscules avant comparaison aux motifs (`/SQL/1.0/Warehouses/...` doit être reconnu comme équivalent à `/sql/1.0/warehouses/...`), bien que Databricks produise généralement ces chemins en minuscules par défaut.
- Le `httpPath` peut être suivi ou précédé d'espaces superflus dans le code M : l'agent doit les supprimer avant comparaison (`str.strip()`).
- Certains projets appellent `Databricks.Catalogs` avec un chemin construit dynamiquement par concaténation de texte (`"/sql/1.0/warehouses/" & WarehouseId`) : l'agent doit tenter de reconstituer la valeur littérale finale si tous les fragments sont eux-mêmes résolvables ; si la concaténation dépend d'une valeur non résolvable statiquement, le résultat reste `NA`.
- Une même table peut comporter plusieurs partitions (partition historique + partition temps réel en mode hybride) : seules les partitions explicitement `mode: directQuery` sont soumises à cette règle ; les partitions `import` de la même table sont ignorées pour cette règle mais peuvent relever de BP-16.

---

## 7. Pseudo-code détaillé

```python
import re

SQL_WAREHOUSE_PATH_PATTERN = re.compile(r"^/sql/1\.0/warehouses/[a-z0-9]+$", re.IGNORECASE)
INTERACTIVE_CLUSTER_PATH_PATTERN = re.compile(r"^/sql/protocolv1/o/\d+/[a-z0-9-]+$", re.IGNORECASE)

def resolve_parameter_value(identifier, parameters_by_name):
    if identifier in parameters_by_name:
        return parameters_by_name[identifier].literal_value   # None si non littéral
    return None

def resolve_http_path(databricks_call, parameters_by_name):
    raw_arg = get_argument(databricks_call, position=2)
    if is_string_literal(raw_arg):
        return raw_arg.value.strip()
    if is_simple_identifier(raw_arg):
        return resolve_parameter_value(raw_arg.name, parameters_by_name)
    if is_concatenation(raw_arg):
        return try_resolve_concatenation(raw_arg, parameters_by_name)   # None si un fragment est dynamique
    return None

def classify_http_path(http_path):
    if http_path is None:
        return "UNKNOWN"
    normalized = http_path.strip().lower()
    if SQL_WAREHOUSE_PATH_PATTERN.match(normalized):
        return "SQL_WAREHOUSE"
    if INTERACTIVE_CLUSTER_PATH_PATTERN.match(normalized):
        return "INTERACTIVE_CLUSTER"
    return "UNKNOWN"


ok_results, ko_results, na_results = [], [], []

table_files = find_all_tmdl_files("<SEMANTIC_MODEL_PATH>/definition/tables/")
if not table_files:
    return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
            "reason": "Aucun fichier de table TMDL trouvé"}

parameters_by_name = parse_m_parameters("<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl")

for table_file in table_files:
    table = parse_tmdl_table(table_file)

    for partition in table.partitions:
        databricks_calls = find_calls(partition.source_expression, "Databricks.Catalogs")
        if not databricks_calls:
            continue   # hors périmètre : pas de connecteur Databricks

        if partition.mode != "directQuery":
            na_results.append({
                "table": table.name, "partition": partition.name, "status": "NA",
                "reason": f"Mode {partition.mode}, hors périmètre (règle spécifique au DirectQuery)",
            })
            continue

        http_path = resolve_http_path(databricks_calls[0], parameters_by_name)
        endpoint_type = classify_http_path(http_path)

        if endpoint_type == "SQL_WAREHOUSE":
            ok_results.append({"table": table.name, "partition": partition.name,
                                "status": "OK", "http_path": http_path})
        elif endpoint_type == "INTERACTIVE_CLUSTER":
            ko_results.append({"table": table.name, "partition": partition.name,
                                "status": "KO", "http_path": http_path,
                                "reason": "Endpoint Databricks résolu vers un cluster interactif partagé"})
        else:
            na_results.append({"table": table.name, "partition": partition.name, "status": "NA",
                                "reason": "httpPath non résolvable statiquement"})
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
| Toutes les partitions DirectQuery/Databricks pointent vers un SQL Warehouse | `OK` |
| Au moins une partition DirectQuery/Databricks pointe vers un cluster interactif partagé | `KO` |
| Aucune partition DirectQuery sur Databricks dans le modèle (comme dans ce projet, entièrement en import) | `NA` |

---

## 9. Structure du résultat

Exemple `NA` (état actuel du projet audité, aucun DirectQuery Databricks) :

```json
{
  "rule_id": "BP-17",
  "rule_name": "Endpoint SQL Warehouse dédié pour les sources Databricks en DirectQuery",
  "execution_status": "SUCCESS",
  "rule_status": "NA",
  "total_databricks_partitions": 1,
  "directquery_databricks_partitions": 0,
  "ok_partitions": 0,
  "ko_partitions": 0,
  "na_partitions": 1,
  "na_details": [
    {"table": "D_STRUCTURES", "partition": "D_STRUCTURES",
     "reason": "Mode import, hors périmètre (règle spécifique au DirectQuery)"}
  ]
}
```

Exemple `KO` (scénario hypothétique) :

```json
{
  "rule_id": "BP-17",
  "rule_name": "Endpoint SQL Warehouse dédié pour les sources Databricks en DirectQuery",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_databricks_partitions": 3,
  "directquery_databricks_partitions": 2,
  "ok_partitions": 1,
  "ko_partitions": 1,
  "na_partitions": 1,
  "ko_details": [
    {"table": "F_LIVE_EVENTS", "partition": "F_LIVE_EVENTS",
     "http_path": "/sql/protocolv1/o/1234567890123456/0821-142233-abcd1234",
     "reason": "Endpoint Databricks résolu vers un cluster interactif partagé"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `NA`

```text
BP-17 — Endpoint Databricks dédié en DirectQuery : NON APPLICABLE

1 connexion Databricks détectée (D_STRUCTURES), utilisée exclusivement en
mode import. Aucune table de ce modèle n'utilise le DirectQuery : la règle
ne s'applique pas actuellement. Note : le httpPath configuré
(/sql/1.0/warehouses/67e09c513f78a526) correspond déjà à un SQL Warehouse
dédié, ce qui serait conforme si ce connecteur passait un jour en DirectQuery.
```

### Exemple `KO`

```text
BP-17 — Endpoint Databricks dédié en DirectQuery : KO

1 partition conforme sur 2 partitions DirectQuery/Databricks analysées.

Partition non conforme :
- F_LIVE_EVENTS : httpPath résolu vers
  /sql/protocolv1/o/1234567890123456/0821-142233-abcd1234, correspondant à
  un cluster interactif partagé plutôt qu'à un SQL Warehouse dédié.

Correction attendue :
créer (ou réutiliser) un SQL Warehouse Databricks dimensionné pour la charge
BI, puis remplacer le httpPath de cette connexion par le chemin du warehouse
(format /sql/1.0/warehouses/<id>), disponible dans les paramètres de
connexion du SQL Warehouse dans l'espace d'administration Databricks.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- tous les fichiers de tables ont été lus, ainsi que `expressions.tmdl` ;
- toutes les partitions appelant `Databricks.Catalogs` ont été identifiées, quel que soit le mode de la partition ;
- pour chaque partition en `directQuery`, le `httpPath` a été résolu jusqu'à sa valeur littérale finale (résolution de paramètre ou de concaténation), pas seulement lu tel quel s'il s'agit d'un identifiant ;
- chaque `httpPath` résolu a été comparé aux deux motifs de classification (SQL Warehouse / cluster interactif) ;
- aucune partition DirectQuery n'a été classée `OK` sur la base d'un `httpPath` non résolvable (auquel cas le statut correct est `NA`, jamais `OK` par défaut).

L'agent ne doit jamais produire `OK` si au moins une partition DirectQuery/Databricks présente un `httpPath` non résolvable ou correspondant à un cluster interactif.

---

## 12. Résumé de la règle

```text
RÈGLE BP-17

POUR chaque table du modèle
    POUR chaque partition de la table
        SI la source n'appelle pas Databricks.Catalogs
            CONTINUER (hors périmètre)
        SI mode != directQuery
            partition = NA (hors périmètre, mode import)
            CONTINUER

        RÉSOUDRE httpPath (littéral direct, paramètre, ou concaténation)
        SI httpPath non résolvable
            partition = NA
            CONTINUER

        SI httpPath correspond au motif /sql/1.0/warehouses/...
            partition = OK
        SINON SI httpPath correspond au motif /sql/protocolv1/o/.../...
            partition = KO
        SINON
            partition = NA (motif non reconnu)

        ENREGISTRER le résultat avec le httpPath résolu
    FIN POUR
FIN POUR

SI au moins une partition KO
    règle = KO
SINON SI aucune partition DirectQuery/Databricks détectée
    règle = NA
SINON
    règle = OK

AFFICHER toutes les partitions KO avec recommandation de bascule vers un
SQL Warehouse dédié
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-17 — Endpoint SQL Warehouse dédié en DirectQuery          │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ Lister tables/*.tmdl                     │
          │ Charger expressions.tmdl (paramètres)     │
          └────────────────┬───────────────────────────┘
               ┌───────────┴───────────┐
               ▼                       ▼
         ╔═════════════╗       ┌──────────────────┐
         ║ Trouvés ✅  ║       │ Aucun fichier ❌    │
         ╚══════╤══════╝       └─────────┬──────────┘
                │                        ▼
                │                ┌────────────────┐
                │                │ Retour :        │
                │                │ NON_EVALUE      │
                │                └────────────────┘
                ▼
     ┌─────────────────────────────────────────────┐
     │ POUR chaque table → POUR chaque partition       │
     │ (boucle imbriquée)                               │
     └────────────────┬──────────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ Source appelle Databricks.       │
        │ Catalogs ?                       │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ┌──────────────┐  ╔═══════════╗
       │ NON             │  ║ OUI         ║
       │ CONTINUER        │  ╚═════╤═══════╝
       │ (hors périmètre) │        ▼
       └──────────────┘  ┌────────────────────────┐
                          │ mode: directQuery ?         │
                          └──────────┬─────────────────┘
                               ┌──────┴──────┐
                               ▼             ▼
                         ┌──────────┐  ╔═══════════╗
                         │ NON = NA │  ║ OUI          ║
                         │(import,   │  ╚═════╤════════╝
                         │hors       │        ▼
                         │périmètre) │ ┌──────────────────────┐
                         └──────────┘ │ RÉSOUDRE httpPath         │
                                      │ (littéral, paramètre,     │
                                      │ concaténation)             │
                                      └──────────┬─────────────────┘
                                           ┌──────┴──────┐
                                           ▼             ▼
                                     ┌──────────┐  ┌──────────────┐
                                     │Non          │  │ Résolu ✅       │
                                     │résolvable   │  └──────┬──────────┘
                                     │= NA         │         ▼
                                     └──────────┘  ┌──────────────────────┐
                                                    │ Motif /sql/1.0/           │
                                                    │ warehouses/... ?           │
                                                    └──────────┬─────────────────┘
                                                         ┌──────┴──────┐
                                                         ▼             ▼
                                                   ╔═══════════╗ ┌──────────────────────┐
                                                   ║ OUI = OK  ║ │ Motif /sql/protocolv1/    │
                                                   ╚═══════════╝ │ o/.../... ?                │
                                                                 └──────────┬─────────────────┘
                                                                      ┌──────┴──────┐
                                                                      ▼             ▼
                                                                ╔═══════════╗ ┌──────────┐
                                                                ║ OUI = KO  ║ │NON = NA    │
                                                                ╚═══════════╝ │(motif non   │
                                                                              │reconnu)     │
                                                                              └──────────┘
                                    FIN DE BOUCLE (partition suivante)
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
