# BP-15 — Maximiser le query folding vers la source

## 1. Objectif de la bonne pratique

Le **query folding** (repli de requête) est le mécanisme par lequel le moteur Mashup de Power Query traduit les étapes M en une requête native exécutée directement par la source (SQL, Databricks, OData...), au lieu de rapatrier les données brutes et de les transformer localement. Lorsqu'il est préservé, il permet de déléguer le filtrage, le tri, l'agrégation et le typage au moteur de la source — généralement bien plus performant et déjà optimisé (index, statistiques, parallélisme) que le moteur Mashup local.

L'objectif de cette règle est de vérifier que, pour les requêtes adossées à une **source repliable** (base SQL, Databricks, OData, service d'analyse...), la chaîne d'étapes M est composée exclusivement — ou majoritairement — de fonctions repliables, et que les mécanismes explicites de repli disponibles (paramètre `EnableFolding=true` de `Value.NativeQuery`) sont correctement activés lorsqu'ils sont utilisés.

Cette règle est complémentaire de :

- [BP-04](04_PushTransformUpstream.md), qui vérifie si les transformations métier lourdes devraient être déléguées à un dataflow / une couche gold en amont de Power Query ;
- [BP-13](13_AvoidEarlyMergesAppends.md), qui vérifie l'ordre des étapes lourdes au sein d'une requête donnée.

**BP-15** se concentre sur un point différent : à source égale, la chaîne d'étapes M casse-t-elle le repli plus tôt que nécessaire à cause de fonctions ou de constructions non repliables ?

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du type de connecteur repliable utilisé (SQL Server, Databricks, Synapse, OData, service d'analyse...) ;
- du nombre d'étapes de chaque requête ;
- du fait que la requête interroge directement des tables/vues de la source (navigation de schéma) ou exécute une requête native via `Value.NativeQuery`.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl        (partitions "= m")
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl      (requêtes partagées)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\expressions.tmdl   (contient D_STRUCTURES, seule requête adossée à Databricks)
```

Aucun fichier du rapport n'est nécessaire : cette règle porte exclusivement sur le code M du modèle sémantique.

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1 Qualifier la source comme repliable ou non

```python
FOLDABLE_CONNECTORS = {
    "Sql.Database", "Sql.Databases",
    "Databricks.Catalogs",                 # navigation de schéma (pas Value.NativeQuery)
    "AnalysisServices.Database",
    "Odbc.DataSource", "Odbc.Query",
    "OData.Feed",
    "PostgreSQL.Database", "Snowflake.Databases", "AzureDataLakeStorage.Contents (avec vue SQL)",
}

NON_FOLDABLE_CONNECTORS = {
    "SharePoint.Files", "SharePoint.Tables",
    "Excel.Workbook", "Csv.Document", "Json.Document",
    "Web.Contents", "Folder.Files",
}
```

### 3.2 Cas de la requête native (`Value.NativeQuery`)

Exemple réel du projet audité (`expressions.tmdl`, requête `D_STRUCTURES`) :

```text
Source =
    Value.NativeQuery(
        Databricks.Catalogs(SPARK_Hostname, SPARK_HTTP_Path, [...])
            {[Name=ReferentialEnvironment, Kind="Database"]}[Data],
        "
        SELECT
                USR_LOGIN, u.STC_UE_IDENTIFIER, s.STC_STRUCTURES_KEY,
                CTR_COUNTRY_LABEL_EN AS USER_COUNTRY, DIR_LEVEL3_LABEL AS USER_AREA
        FROM master_data.v_usr_colasusers_lastknown_d u
        JOIN master_data.stc_colas_structures_last_known_d s ON ...
        JOIN master_data.ctr_countries_d c ON ...
        "
        , null, [EnableFolding=true])
in
    Source
```

Ici, la jointure SQL est exécutée **côté Databricks** : le paramètre `EnableFolding=true` est explicitement positionné en 4ᵉ argument de `Value.NativeQuery`, ce qui autorise Power Query à replier d'éventuelles étapes ultérieures (filtrage, tri) sur cette requête native plutôt que de les exécuter localement. La requête `D_STRUCTURES` ne comporte ici aucune étape après la requête native (`in Source` directement) : le repli est donc trivialement préservé sur toute la chaîne.

### 3.3 Fonctions connues pour casser le repli

```python
FOLD_BREAKING_FUNCTIONS = {
    "Table.Buffer", "List.Buffer",                 # mise en cache locale forcée
    "Python.Execute", "R.Execute",                  # scripts exécutés dans le moteur local
    "Table.Profile",                                 # calcul de profils statistiques local
    "Table.AddColumn",                               # repliable seulement si la logique "each" est simple
                                                      # (référence de colonne + opérateur arithmétique/texte basique) ;
                                                      # casse le repli si elle appelle une fonction M personnalisée
                                                      # ou une fonction non traduisible en SQL
    "Table.Distinct",                                # repliable seulement sans comparateur personnalisé
    "Table.Group",                                   # repliable seulement avec des agrégateurs standards
                                                      # (List.Sum, List.Count...) ; casse le repli avec "each" complexe
}
```

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Source racine non repliable (`SharePoint.Files`, `Excel.Workbook`...) | `NA` | Le folding n'est pas applicable à cette requête : hors périmètre de la règle. |
| `Value.NativeQuery` utilisé avec `EnableFolding=true` explicite, aucune étape non repliable après | `OK` | Le repli est correctement activé et préservé jusqu'à la fin de la requête. |
| `Value.NativeQuery` utilisé sans le paramètre `EnableFolding`, ou avec `EnableFolding=false` | `KO` | Le repli n'est pas explicitement activé alors que la source le permettrait — étapes ultérieures potentiellement exécutées en local. |
| Source de navigation de schéma repliable (`Sql.Database`, `Databricks.Catalogs` sans requête native), aucune fonction de `FOLD_BREAKING_FUNCTIONS` détectée dans les étapes suivantes | `OK` | Chaîne entièrement composée de fonctions présumées repliables. |
| Source de navigation de schéma repliable, au moins une fonction de `FOLD_BREAKING_FUNCTIONS` détectée | `KO` | Le repli est présumé rompu à partir de cette étape ; toutes les étapes suivantes s'exécutent probablement en local. |
| Requête sans code M analysable (DAX, DirectQuery/DirectLake sans partition M) | `NA` | Hors périmètre. |

Exemple issu du modèle audité :

| Requête | Source racine | `Value.NativeQuery` ? | `EnableFolding` | Étapes après | Statut |
|---|---|---|---|---|---|
| `D_STRUCTURES` | `Databricks.Catalogs` | Oui | `true` | aucune | `OK` |
| `SOURCE` | `SharePoint.Files` | — | — | — | `NA` (source non repliable) |
| `D_USERS`, `F_MONORESPONSES` | résolues via `SOURCE` → `SharePoint.Files` | — | — | — | `NA` |

Aucune requête `KO` n'existe actuellement dans ce modèle : la seule source repliable identifiée (`D_STRUCTURES`) active correctement `EnableFolding=true`.

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables/*.tmdl`.
2. Charger `expressions.tmdl` s'il existe.
3. Si aucun fichier de table n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Construire le graphe de requêtes atteignables
Identique à BP-04 : ne retenir que les requêtes réellement utilisées, transitivement, par une table chargée du modèle.

### Étape 3 — Qualifier la source racine de chaque requête
Résoudre récursivement la première étape jusqu'à un appel de connecteur réel (même logique que BP-04, section 4), puis classer ce connecteur en `FOLDABLE`, `NON_FOLDABLE` ou `UNKNOWN`.

### Étape 4 — Analyser la chaîne d'étapes pour les sources repliables
Pour chaque requête dont la source racine est `FOLDABLE` :
1. si la première étape est un `Value.NativeQuery`, vérifier la présence et la valeur du paramètre `EnableFolding` ;
2. sinon, parcourir toutes les étapes suivantes et détecter la première fonction appartenant à `FOLD_BREAKING_FUNCTIONS` ;
3. enregistrer le résultat avec preuve (nom de l'étape, fonction en cause).

### Étape 5 — Ne pas s'arrêter à la première anomalie
Toutes les requêtes adossées à une source repliable doivent être analysées, même après un premier `KO`.

### Étape 6 — Terminer l'analyse
Produire le nombre de requêtes analysées, la répartition `OK`/`KO`/`NA`, et le détail des requêtes `KO` avec la fonction responsable de la rupture de repli.

---

## 6. Détection robuste / normalisation

- Le paramètre `EnableFolding` de `Value.NativeQuery` peut apparaître avec une casse ou un espacement variable (`[EnableFolding=true]`, `[ EnableFolding = true ]`) : l'agent doit normaliser les espaces avant de rechercher la clé et de comparer la valeur (`true`/`false`, insensible à la casse).
- `Value.NativeQuery` accepte 5 arguments positionnels (`connexion`, `requête`, `paramètres`, `options`) : l'option `EnableFolding` se trouve dans le 4ᵉ argument (`options`, un `record`) ; l'agent doit localiser ce record indépendamment de l'ordre des autres clés qu'il peut contenir (`EnableQueryFolding`, `HierarchicalNavigation`...).
- Une requête peut être encadrée par des triples backticks `` ``` `` (cas de `D_STRUCTURES`) : cette enveloppe doit être retirée avant le parsing.
- `Table.AddColumn` ne doit pas être classée automatiquement `FOLD_BREAKING` : l'agent doit inspecter le corps de la fonction `each ...` et ne la considérer comme rompant le repli que si elle appelle une fonction M personnalisée, une fonction non standard (`Text.Combine` avec logique conditionnelle complexe, appel récursif...), ou accède à des colonnes d'une autre requête non repliable.
- Le principe de détection reste **heuristique** : la seule vérification définitive du repli est la disponibilité de l'option « Afficher la requête source » (View Native Query) sur la dernière étape dans Power BI Desktop. L'agent doit le signaler explicitement dans sa restitution comme méthode de contre-vérification manuelle, sans prétendre remplacer cette vérification runtime.
- Les fonctions M sont sensibles à la casse (`Table.Group` ≠ `table.group`) ; les noms d'étapes utilisateur ne le sont pas et ne doivent jamais servir de critère de décision (seule la fonction réellement appelée compte).

---

## 7. Pseudo-code détaillé

```python
FOLD_BREAKING_FUNCTIONS = {"Table.Buffer", "List.Buffer", "Python.Execute", "R.Execute", "Table.Profile"}

def extract_enable_folding_option(native_query_call):
    options_record = get_argument(native_query_call, position=4)  # peut être absent
    if options_record is None:
        return None
    return parse_record_boolean(options_record, key="EnableFolding")  # None si clé absente

def step_breaks_folding(step_expression):
    called_functions = find_all_called_functions(step_expression)
    if called_functions & FOLD_BREAKING_FUNCTIONS:
        return True
    if "Table.AddColumn" in called_functions and calls_custom_or_nonstandard_function(step_expression):
        return True
    if "Table.Group" in called_functions and not uses_standard_aggregators(step_expression):
        return True
    if "Table.Distinct" in called_functions and has_custom_comparer(step_expression):
        return True
    return False

def evaluate_query_folding(query_name, m_code, root_source_connector):
    if root_source_connector not in FOLDABLE_CONNECTORS:
        return {"query": query_name, "status": "NA", "reason": "Source non repliable"}

    steps = extract_ordered_steps(m_code)
    first_expr = steps[0][1] if steps else None

    if first_expr and "Value.NativeQuery" in find_all_called_functions(first_expr):
        enable_folding = extract_enable_folding_option(first_expr)
        if enable_folding is not True:
            return {"query": query_name, "status": "KO",
                    "reason": "Value.NativeQuery sans EnableFolding=true explicite",
                    "enable_folding_value": enable_folding}
        remaining_steps = steps[1:]
    else:
        remaining_steps = steps

    for step_name, step_expr in remaining_steps:
        if step_breaks_folding(step_expr):
            return {"query": query_name, "status": "KO",
                    "reason": f"Étape '{step_name}' présumée non repliable",
                    "breaking_step": step_name}

    return {"query": query_name, "status": "OK"}


ok_results, ko_results, na_results = [], [], []

table_files = find_all_tmdl_files("<SEMANTIC_MODEL_PATH>/definition/tables/")
if not table_files:
    return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
            "reason": "Aucun fichier de table TMDL trouvé"}

queries = build_query_graph(table_files, expressions_file="<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl")
reachable = collect_all_reachable_queries(tables_with_m_partition(table_files), queries)

for name in reachable:
    if is_out_of_scope(queries[name]):
        na_results.append({"query": name, "status": "NA", "reason": "Pas de code M analysable"})
        continue

    root_source = resolve_root_source(name, queries)
    connector = classify_connector_foldability(root_source)   # FOLDABLE / NON_FOLDABLE / UNKNOWN

    if connector == "UNKNOWN":
        na_results.append({"query": name, "status": "NA", "reason": "Connecteur racine non déterminable"})
        continue

    result = evaluate_query_folding(name, queries[name]["m_code"], connector)
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
| Toutes les requêtes adossées à une source repliable préservent le folding | `OK` |
| Au moins une requête adossée à une source repliable rompt le folding | `KO` |
| Aucune requête du modèle n'est adossée à une source repliable | `NA` |

---

## 9. Structure du résultat

Exemple `OK` (état actuel du projet audité) :

```json
{
  "rule_id": "BP-15",
  "rule_name": "Maximiser le query folding vers la source",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_queries": 27,
  "foldable_source_queries": 1,
  "ok_queries": 1,
  "ko_queries": 0,
  "na_queries": 26,
  "ok_details": [
    {"query": "D_STRUCTURES", "root_source": "Databricks.Catalogs (Value.NativeQuery)", "enable_folding_value": true}
  ],
  "ko_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-15",
  "rule_name": "Maximiser le query folding vers la source",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_queries": 27,
  "foldable_source_queries": 2,
  "ok_queries": 1,
  "ko_queries": 1,
  "na_queries": 25,
  "ko_details": [
    {
      "query": "D_STRUCTURES_V2",
      "root_source": "Databricks.Catalogs (Value.NativeQuery)",
      "reason": "Value.NativeQuery sans EnableFolding=true explicite",
      "enable_folding_value": null
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-15 — Query folding : OK

1 requête adossée à une source repliable (D_STRUCTURES, via Databricks).
La requête native déclare explicitement EnableFolding=true et aucune étape
non repliable ne suit dans la chaîne : le repli est correctement préservé.
```

### Exemple `KO`

```text
BP-15 — Query folding : KO

1 requête conforme sur 2 requêtes adossées à une source repliable.

Requête non conforme :
- D_STRUCTURES_V2 : la requête native (Value.NativeQuery sur Databricks)
  n'active pas explicitement EnableFolding=true. Sans ce paramètre, les
  étapes de filtrage ou de tri ajoutées après cette requête native
  s'exécuteront potentiellement en local plutôt que d'être repliées.

Correction attendue :
ajouter l'option [EnableFolding=true] en 4e argument de Value.NativeQuery,
puis vérifier via "Afficher la requête source" (clic droit sur la dernière
étape dans Power BI Desktop) que le repli est effectif de bout en bout.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- toutes les tables et `expressions.tmdl` ont été lues et parsées sans erreur ;
- le graphe de requêtes atteignables a été construit intégralement ;
- pour chaque requête retenue, la source racine a pu être résolue jusqu'à un connecteur réel ;
- toutes les requêtes dont la source racine est repliable ont été analysées, sans exception ;
- pour chaque `Value.NativeQuery` détecté, la présence et la valeur du paramètre `EnableFolding` ont été vérifiées explicitement (une absence de paramètre n'équivaut jamais à `OK`) ;
- toutes les étapes de chaque requête repliable ont été inspectées pour détecter une éventuelle fonction rompant le repli.

L'agent ne doit jamais produire `OK` si la source racine d'une requête n'a pas pu être déterminée avec certitude, ni conclure silencieusement qu'une fonction personnalisée non reconnue est repliable par défaut.

---

## 12. Résumé de la règle

```text
RÈGLE BP-15

CONSTRUIRE le graphe de requêtes atteignables
POUR chaque requête

    RÉSOUDRE la source racine (connecteur réel)
    SI source racine non repliable
        requête = NA
        CONTINUER

    SI première étape = Value.NativeQuery
        SI EnableFolding != true explicitement
            requête = KO
            CONTINUER
        ÉTAPES_À_VÉRIFIER = étapes après la requête native
    SINON
        ÉTAPES_À_VÉRIFIER = toutes les étapes

    POUR chaque étape de ÉTAPES_À_VÉRIFIER
        SI la fonction appelée rompt le repli (Table.Buffer, script, agrégation
           non standard, appel de fonction personnalisée non repliable...)
            requête = KO
            ARRÊTER la boucle sur les étapes

    SI aucune rupture détectée
        requête = OK

    ENREGISTRER le résultat avec preuve (étape ou paramètre en cause)
FIN POUR

SI au moins une requête KO
    règle = KO
SINON SI aucune requête n'est adossée à une source repliable
    règle = NA
SINON
    règle = OK

AFFICHER toutes les requêtes KO, avec recommandation et rappel de la
vérification manuelle "Afficher la requête source"
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-15 — Maximiser le query folding vers la source           │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ Lister tables/*.tmdl                     │
          │ + charger expressions.tmdl                │
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
     ┌─────────────────────────────────────────┐
     │ CONSTRUIRE le graphe des requêtes         │
     │ atteignables depuis les tables chargées   │
     └────────────────┬────────────────────────────┘
                      ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque requête atteignable (boucle)    │
     └────────────────┬────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ RÉSOUDRE la source racine       │
        │ (connecteur réel)               │
        └──────────┬──────────────────────┘
                   ▼
        ┌───────────────────────────────┐
        │ Connecteur FOLDABLE ?           │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ┌──────────┐   ╔═══════════╗
       │ NON/      │   ║ OUI        ║
       │ INCONNU   │   ╚═════╤══════╝
       │ = NA      │         ▼
       └──────────┘  ┌──────────────────────────┐
                      │ 1re étape = Value.          │
                      │ NativeQuery ?               │
                      └──────────┬─────────────────┘
                           ┌──────┴──────┐
                           ▼             ▼
                     ╔═══════════╗  ┌──────────────────┐
                     ║ OUI        ║  │ NON                │
                     ╚═════╤══════╝  │ Vérifier chaque      │
                           ▼         │ étape (fonction        │
              ┌────────────────────┐│ FOLD_BREAKING ?)        │
              │ EnableFolding=true  │└─────────┬────────────────┘
              │ explicite ?         │          │
              └──────────┬───────────┘          │
                   ┌──────┴──────┐              │
                   ▼             ▼              │
             ┌──────────┐  ╔═══════════╗        │
             │ NON = KO │  ║ OUI         ║        │
             └──────────┘  ╚═════╤═══════╝        │
                                 ▼               ▼
                     ┌────────────────────────────────┐
                     │ Étapes suivantes analysées :      │
                     │ fonction rompant le repli          │
                     │ détectée (Buffer, script, agrégat  │
                     │ non standard, AddColumn custom) ?  │
                     └──────────────┬─────────────────────┘
                              ┌──────┴──────┐
                              ▼             ▼
                        ╔═══════════╗ ┌──────────┐
                        ║ OUI = KO  ║ │ NON = OK  │
                        ╚═══════════╝ └──────────┘
                              │             │
                              └──────┬──────┘
                                    ▼
                    FIN DE BOUCLE (requête suivante)
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
