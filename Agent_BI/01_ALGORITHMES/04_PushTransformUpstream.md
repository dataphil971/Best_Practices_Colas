# BP-04 (alias SEM-003) — Pousser les transformations en amont (dataflows / gold)

## 1. Objectif de la bonne pratique

> « Poussez les transformations en amont, vers la source de données (dataflows / gold), lorsque cela est possible. »

L'objectif est de vérifier que les transformations « métier » lourdes (jointures, agrégations, pivots/dépivots, colonnes calculées complexes, nettoyage multi-règles...) ne sont **pas** réalisées dans le Power Query (M) du modèle sémantique, alors qu'elles pourraient être déléguées :

- à un **dataflow** (Power Platform / Fabric) ;
- à une **couche gold / curated** d'un lakehouse ou d'un entrepôt (Databricks, Synapse, etc.) ;
- ou, à défaut, à une **requête native repliable** (`Value.NativeQuery` avec `EnableFolding=true`) exécutée côté source.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables et d'expressions partagées ;
- du connecteur utilisé (SQL, Databricks, SharePoint, dataflow, fichier plat...) ;
- de l'ordre des étapes dans le code M ;
- du fait que la requête soit une table physique du modèle ou une expression partagée (`expressions.tmdl`) utilisée comme brique intermédiaire.

---

## 2. Emplacement du modèle sémantique

L'agent doit lire **deux emplacements** :

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl        (partitions "= m" contenant le code M)
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl      (requêtes partagées / intermédiaires)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\expressions.tmdl
```

Contrairement à [BP-22](22_DisableSummarization.md), cette règle ne porte pas sur les colonnes mais sur le **code M** :

- dans `tables/*.tmdl`, le code se trouve dans le bloc `partition <NOM> = m ... source = ...` ;
- dans `expressions.tmdl`, chaque bloc `expression <NOM> = let ... in ...` est une requête intermédiaire (souvent un paramètre, une fonction utilitaire ou une brique réutilisée par plusieurs tables).

Les paramètres (`meta [IsParameterQuery=true, ...]`) et les fonctions utilitaires sans étape de transformation de données (ex. une fonction qui ne fait que réexposer `Excel.Workbook`) sont hors périmètre : ils ne sont analysés que s'ils sont référencés comme source par une table ou une autre requête.

L'agent doit récupérer :
1. tous les fichiers `*.tmdl` du dossier `tables/` ;
2. le fichier `expressions.tmdl` s'il existe.

---

## 3. Construction du graphe de requêtes

Avant de classer quoi que ce soit, l'agent doit construire une table de correspondance **nom → code M**, car une table peut s'appuyer sur une expression partagée qui elle-même s'appuie sur une autre expression.

```python
queries = {}  # nom_requete -> { "kind": "table"|"expression", "m_code": str, "origin_file": str }

for table_file in table_files:
    table = parse_tmdl_table(table_file)
    if table.has_m_partition():
        queries[table.name] = {
            "kind": "table",
            "m_code": table.partition.source_expression,
            "origin_file": table_file,
        }

if expressions_file exists:
    for expr in parse_tmdl_expressions(expressions_file):
        if expr.is_data_query():   # exclut les simples paramètres texte/binaires
            queries[expr.name] = {
                "kind": "expression",
                "m_code": expr.body,
                "origin_file": expressions_file,
            }
```

Exemple concret observé dans le modèle audité (`AI_BAROMETER_BI-CDS.SemanticModel`) :

```text
D_USERS (table)         → Source = SOURCE
F_MONORESPONSES (expr)  → Source = SOURCE
F_SCORERESPONSES (expr) → Source = SOURCE
F_ADOPTION_LEVEL (expr) → Source = F_ADOPTION_QUESTION (table)
F_RESPONSES (table)     → Source = Table.NestedJoin(F_MONORESPONSES, ..., F_SCORERESPONSES, ...)
SOURCE (expr)           → Source = SharePoint.Files(...)
D_STRUCTURES (expr)     → Source = Value.NativeQuery(Databricks.Catalogs(...), "SELECT ... JOIN ... JOIN ...", EnableFolding=true)
```

Ce graphe permet de répondre à la question clé : **le premier connecteur atteint en remontant la chaîne est-il déjà une source amont (dataflow/gold) ou une requête repliable ?**

---

## 4. Qualifier la source racine d'une requête

Pour chaque requête, l'agent résout récursivement la première étape (`Source = ...`) jusqu'à atteindre un **appel de connecteur réel** (et non plus une simple référence à une autre requête locale).

```python
def resolve_root_source(query_name, queries, visited=None):
    visited = visited or set()
    if query_name in visited:
        return "CIRCULAR_REFERENCE"
    visited.add(query_name)

    m_code = queries[query_name]["m_code"]
    first_step_expr = get_first_step_expression(m_code)  # partie droite de "Source = ..."

    referenced_name = as_simple_identifier(first_step_expr)
    if referenced_name and referenced_name in queries:
        return resolve_root_source(referenced_name, queries, visited)

    return classify_connector(first_step_expr)
```

```python
def classify_connector(expr_text):
    if matches(expr_text, r"PowerPlatform\.Dataflows|Fabric\.Dataflows"):
        return "DATAFLOW"
    if matches(expr_text, r"Lakehouse\.Contents") and matches_schema(expr_text, r"gold|curated|dwh"):
        return "GOLD"
    if matches(expr_text, r"Value\.NativeQuery") and has_option(expr_text, "EnableFolding", "true") \
            and contains_join_or_group_in_sql(expr_text):
        return "NATIVE_QUERY_FOLDED"   # transformation déjà déléguée à la requête native côté source
    if matches(expr_text, r"Sql\.Database|Odbc\.Query|Databricks\.Catalogs"):
        return "RAW_DATABASE"
    if matches(expr_text, r"SharePoint\.(Files|Tables)|Excel\.Workbook|Csv\.Document|Json\.Document|Web\.Contents"):
        return "RAW_FILE_OR_LIST"
    return "UNKNOWN_SOURCE"

UPSTREAM_SOURCES = {"DATAFLOW", "GOLD", "NATIVE_QUERY_FOLDED"}
```

Exemples issus du modèle audité :

| Requête | Connecteur racine résolu | `isUpstreamSource` |
|---|---|---|
| `D_STRUCTURES` | `Value.NativeQuery(Databricks.Catalogs(...), "SELECT ... JOIN ... JOIN ...", EnableFolding=true)` | ✅ `NATIVE_QUERY_FOLDED` |
| `SOURCE` | `SharePoint.Files(...)` | ❌ `RAW_FILE_OR_LIST` |
| `D_USERS`, `F_MONORESPONSES`, `F_SCORERESPONSES` | résolu via `SOURCE` → `SharePoint.Files(...)` | ❌ `RAW_FILE_OR_LIST` |
| `D_INTEREST_LEVELS`, `D_WORRY_LEVELS`, ... | `SharePoint.Tables(...)` | ❌ `RAW_FILE_OR_LIST` |

Aucune source de type `DATAFLOW` ou `GOLD` n'est présente dans ce modèle : toutes les données transitent par un fichier SharePoint ou un accès Databricks brut, à l'exception de `D_STRUCTURES` qui utilise une requête SQL repliable.

---

## 5. Classifier les étapes M (hors étape `Source`)

Deux listes de fonctions M servent à qualifier chaque étape qui suit la source :

**Lourdes — logique métier qui devrait être poussée en amont**

```text
Table.Group, Table.Pivot, Table.Unpivot, Table.UnpivotOtherColumns,
Table.NestedJoin, Table.Join, Table.FuzzyNestedJoin, Table.FuzzyGroup,
Table.Combine, Table.AddColumn (avec logique conditionnelle / multi-colonnes),
Table.SplitColumn (règles complexes), Table.ExpandTableColumn (quand elle suit
un NestedJoin), Table.AddIndexColumn suivi d'un Group, Python.Execute, R.Execute,
Table.ReplaceValue (règles métier multiples), "Merged Queries" (nom d'étape généré
par l'UI pour une fusion)
```

**Légères — acceptables dans le modèle (présentation / typage)**

```text
Table.TransformColumnTypes, Table.RenameColumns, Table.SelectColumns,
Table.RemoveColumns, Table.SelectRows (filtre simple), Table.Sort,
Table.Distinct (simple), navigation de schéma/table, Table.AddIndexColumn (seule,
sans agrégation derrière)
```

```python
HEAVY_FUNCTIONS = {"Table.Group", "Table.Pivot", "Table.Unpivot", "Table.UnpivotOtherColumns",
                    "Table.NestedJoin", "Table.Join", "Table.FuzzyNestedJoin", "Table.FuzzyGroup",
                    "Table.Combine", "Table.SplitColumn", "Python.Execute", "R.Execute"}

LIGHT_FUNCTIONS = {"Table.TransformColumnTypes", "Table.RenameColumns", "Table.SelectColumns",
                    "Table.RemoveColumns", "Table.SelectRows", "Table.Sort", "Table.Distinct"}

def classify_step(step):
    fn = step.called_function  # ex: "Table.NestedJoin"
    if fn in HEAVY_FUNCTIONS:
        return "HEAVY"
    if fn == "Table.AddColumn" and step.has_conditional_or_multi_column_logic():
        return "HEAVY"
    if fn == "Table.ExpandTableColumn" and previous_step_is_join(step):
        return "HEAVY"   # l'expansion qui matérialise un merge compte comme partie de la jointure
    if fn in LIGHT_FUNCTIONS:
        return "LIGHT"
    return "UNKNOWN"      # à signaler, compté prudemment comme HEAVY si non reconnu
```

Exemple concret — requête `SOURCE` (`expressions.tmdl`) :

| Étape | Fonction | Classification |
|---|---|---|
| `Lignes filtrées` | `Table.SelectRows` | LIGHT |
| `Fichiers masqués filtrés1` | `Table.SelectRows` | LIGHT |
| `Appeler une fonction personnalisée1` | `Table.AddColumn` (appel de fonction simple) | LIGHT |
| `Colonnes renommées1` | `Table.RenameColumns` | LIGHT |
| `Colonne de tables développée1` | `Table.ExpandTableColumn` | LIGHT |
| `Type modifié` | `Table.TransformColumnTypes` | LIGHT |
| `Colonnes renommées` | `Table.RenameColumns` | LIGHT |
| `Texte extrait entre les délimiteurs` | `Table.TransformColumns` (extraction) | LIGHT |
| **`Merged Queries`** | **`Table.NestedJoin`** | **HEAVY** |
| **`Expanded D_STRUCTURES`** | **`Table.ExpandTableColumn`** (suit le join) | **HEAVY** |
| `Added Custom` | `Table.AddColumn` (concaténation simple `[CAMPAIGN_ID]&[USER_LOGIN]`) | LIGHT |
| `Removed Other Columns` | `Table.SelectColumns` | LIGHT |

→ 2 étapes lourdes détectées sur une source `RAW_FILE_OR_LIST`.

---

## 6. Règle d'évaluation par requête

```python
def evaluate_query(query_name, queries):
    m_code = queries[query_name]["m_code"]
    steps = parse_steps(m_code)                 # toutes les étapes hors "Source"
    heavy_steps = [s for s in steps if classify_step(s) == "HEAVY"]

    root_source = resolve_root_source(query_name, queries)
    is_upstream = root_source in UPSTREAM_SOURCES

    if is_upstream and not heavy_steps:
        return "OK", root_source, heavy_steps
    if is_upstream and heavy_steps:
        return "KO", root_source, heavy_steps   # source déjà amont mais logique lourde ajoutée en plus
    if not is_upstream and not heavy_steps:
        return "OK", root_source, heavy_steps   # rien de lourd à remonter
    return "KO", root_source, heavy_steps        # cas visé par la bonne pratique
```

| Source racine amont ? | Étapes lourdes présentes ? | Verdict | Interprétation |
|---|---|---|---|
| Oui (dataflow/gold/native foldée) | Non | `OK` | Transformations déjà déléguées en amont. |
| Oui | Oui | `KO` | Incohérence : logique lourde ajoutée malgré une source déjà amont. |
| Non (fichier/liste/table brute) | Non | `OK` | Rien de lourd à remonter, la requête ne fait que sélectionner/typer. |
| Non | Oui | `KO` | Cas type de la bonne pratique : jointures/agrégations faites dans le modèle sur une source brute. |
| — | — | `NA` | Requête sans code M (table calculée DAX, DirectQuery/DirectLake sans partition M) ou requête non résolvable (référence circulaire, connecteur non reconnu). |

---

## 7. Requêtes hors périmètre → `NA`

```python
def is_out_of_scope(table):
    return (
        table.mode in {"directQuery", "directLake"} and not table.has_m_partition()
        or table.is_calculated_table()          # DAX uniquement
        or table.partition is None
    )
```

---

## 8. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables/*.tmdl`.
2. Charger `expressions.tmdl` s'il existe.
3. Si aucun fichier de table n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Construire le graphe de requêtes
1. Extraire chaque table avec partition `= m` → `queries[table.name]`.
2. Extraire chaque expression de type requête de données (exclure les paramètres purs) → `queries[expr.name]`.

### Étape 3 — Évaluer chaque requête atteignable depuis une table du modèle

L'agent n'évalue que les requêtes réellement utilisées par le modèle (tables + expressions qu'elles référencent, transitivement), afin d'ignorer les brouillons ou requêtes désactivées non chargées dans le modèle.

```python
reachable = set()
def collect_reachable(name):
    if name in reachable or name not in queries:
        return
    reachable.add(name)
    for ref in extract_referenced_query_names(queries[name]["m_code"]):
        collect_reachable(ref)

for table in tables_with_m_partition:
    collect_reachable(table.name)
```

### Étape 4 — Évaluer et enregistrer
Pour chaque requête dans `reachable` :
1. résoudre sa source racine ;
2. classer ses étapes ;
3. appliquer la règle de décision (section 6) ;
4. enregistrer le résultat avec preuve (nom des étapes lourdes, code du connecteur racine).

### Étape 5 — Terminer l'analyse
Produire le nombre total de requêtes évaluées, le nombre `OK`/`KO`/`NA`, la liste des requêtes `KO` avec détail, et la liste des requêtes `NA` avec raison.

---

## 9. Détection robuste du code M

L'agent ne doit pas supposer un format figé du bloc `let ... in ...` :

- les étapes peuvent être nommées `#"Nom avec espaces"` ou `NomSimple` ;
- les commentaires `//` ou `/* ... */` doivent être ignorés lors du parsing des fonctions appelées mais peuvent être conservés comme contexte explicatif ;
- une requête peut être encadrée par des triples backticks `` ``` `` (cas de `D_STRUCTURES` dans `expressions.tmdl`) : l'agent doit retirer cette enveloppe avant de parser le M ;
- une étape peut appeler plusieurs fonctions imbriquées (ex. `Table.ExpandTableColumn(Table.NestedJoin(...), ...)`) : l'agent doit détecter **toutes** les fonctions présentes dans l'expression de l'étape, pas seulement celle en tête ;
- la référence à une autre requête locale se fait par un identifiant nu (`Source = SOURCE`, `Source = F_ADOPTION_QUESTION`) — à distinguer d'un appel de fonction de connecteur (qui contient toujours des parenthèses).

```python
def extract_referenced_query_names(m_code):
    first_step_expr = get_first_step_expression(m_code)
    if is_simple_identifier(first_step_expr):   # pas d'appel de fonction, ex: "SOURCE"
        return [first_step_expr]
    return find_identifiers_used_as_table_arguments(m_code, known_names=queries.keys())
```

---

## 10. Pseudo-code détaillé (bout en bout)

```python
ok_queries, ko_queries, na_queries = [], [], []

table_files = find_all_tmdl_files(f"{PROJECT}.SemanticModel/definition/tables/")
if not table_files:
    return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
            "reason": "Aucun fichier de table TMDL trouvé"}

queries = build_query_graph(table_files, expressions_file=f"{PROJECT}.SemanticModel/definition/expressions.tmdl")
reachable = collect_all_reachable_queries(tables_with_m_partition(table_files), queries)

for name in reachable:
    if is_out_of_scope(queries[name]):
        na_queries.append({"query": name, "status": "NA", "reason": "Pas de code M analysable"})
        continue

    root_source = resolve_root_source(name, queries)
    if root_source in {"CIRCULAR_REFERENCE", "UNKNOWN_SOURCE"}:
        na_queries.append({"query": name, "status": "NA",
                            "reason": f"Source racine non déterminable ({root_source})"})
        continue

    steps = parse_steps(queries[name]["m_code"])
    heavy_steps = [s for s in steps if classify_step(s) == "HEAVY"]
    is_upstream = root_source in UPSTREAM_SOURCES

    if heavy_steps:
        ko_queries.append({
            "query": name, "status": "KO", "root_source": root_source,
            "heavy_steps": [s.name for s in heavy_steps],
            "reason": "Transformations lourdes présentes dans le modèle malgré une source amont disponible"
                      if is_upstream else
                      "Transformations lourdes réalisées dans le modèle sur une source brute",
        })
    else:
        ok_queries.append({"query": name, "status": "OK", "root_source": root_source})
```

---

## 11. Calcul du statut global de la bonne pratique

```python
if ko_queries:
    rule_status = "KO"
elif na_queries:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts, identique aux autres règles : `KO > NA > OK`.

---

## 12. Structure du résultat

```json
{
  "rule_id": "BP-04",
  "alias": "SEM-003",
  "rule_name": "Pousser les transformations en amont (dataflows / gold)",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_queries": 24,
  "ok_queries": 19,
  "ko_queries": 4,
  "na_queries": 1,
  "ko_details": [
    {
      "query": "SOURCE",
      "root_source": "RAW_FILE_OR_LIST",
      "heavy_steps": ["Merged Queries", "Expanded D_STRUCTURES"],
      "reason": "Transformations lourdes réalisées dans le modèle sur une source brute"
    },
    {
      "query": "F_SCORERESPONSES",
      "root_source": "RAW_FILE_OR_LIST",
      "heavy_steps": ["Unpivoted Knowledge Responses", "Joined Answer Scoring Reference",
                       "Calculated Total Knowledge Score"],
      "reason": "Transformations lourdes réalisées dans le modèle sur une source brute"
    },
    {
      "query": "F_MONORESPONSES",
      "root_source": "RAW_FILE_OR_LIST",
      "heavy_steps": ["Joined Self-Perceived Knowledge Reference", "Joined Training Level Reference",
                       "Joined Resource Visibility Reference", "Joined Worry Level Reference",
                       "Joined Interest Level Reference", "Joined Usage Frequency Reference"],
      "reason": "Transformations lourdes réalisées dans le modèle sur une source brute"
    },
    {
      "query": "F_RESPONSES",
      "root_source": "RAW_FILE_OR_LIST",
      "heavy_steps": ["Source (Table.NestedJoin)", "Joined AI Adoption Level",
                       "Joined Tested Knowledge Reference"],
      "reason": "Transformations lourdes réalisées dans le modèle sur une source brute"
    }
  ],
  "ok_details": [
    {"query": "D_STRUCTURES", "root_source": "NATIVE_QUERY_FOLDED"},
    {"query": "D_INTEREST_LEVELS", "root_source": "RAW_FILE_OR_LIST"},
    {"query": "D_WORRY_LEVELS", "root_source": "RAW_FILE_OR_LIST"}
  ],
  "na_details": []
}
```

---

## 13. Message présenté à l'utilisateur

### Exemple `KO`

```text
BP-04 (SEM-003) — Pousser les transformations en amont : KO

19 requêtes conformes sur 24 requêtes analysées.

Requêtes non conformes :
- SOURCE : jointure "Merged Queries" (Table.NestedJoin) faite dans le modèle
  sur une source brute SharePoint.Files. À déplacer vers un dataflow / la
  couche gold en amont.
- F_MONORESPONSES : 6 jointures (Table.NestedJoin) réalisées dans le modèle
  pour associer les réponses aux référentiels de niveaux. À déplacer en amont.
- F_SCORERESPONSES : dépivot (Table.UnpivotOtherColumns) + jointure + agrégation
  (Table.Group) réalisés dans le modèle. À déplacer en amont.
- F_RESPONSES : jointures (Table.NestedJoin) entre requêtes intermédiaires
  réalisées dans le modèle. À déplacer en amont.

Requête conforme à titre d'exemple :
- D_STRUCTURES : la jointure entre les référentiels utilisateurs/structures/pays
  est réalisée directement dans la requête SQL native (Value.NativeQuery,
  EnableFolding=true) exécutée côté Databricks — bonne pratique respectée.

Correction attendue :
créer un dataflow (ou une vue/table gold côté Databricks) qui réalise les
jointures, le dépivot et l'agrégation identifiés ci-dessus, et faire pointer
les requêtes Power Query correspondantes vers ce résultat déjà transformé.
```

### Exemple `OK`

```text
BP-04 (SEM-003) — Pousser les transformations en amont : OK

24 requêtes analysées, aucune transformation lourde détectée dans le modèle
sémantique. Les jointures/agrégations identifiées sont toutes déléguées à des
dataflows, à une couche gold, ou à des requêtes natives repliables côté source.
```

---

## 14. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- le dossier `tables/` a été localisé et tous les fichiers `.tmdl` ont été lus ;
- `expressions.tmdl` a été lu s'il existe ;
- le graphe de requêtes a pu être construit sans erreur de parsing ;
- toutes les requêtes atteignables depuis une table du modèle (`reachable`) ont été évaluées ;
- pour chaque requête, la source racine a pu être résolue (pas de `CIRCULAR_REFERENCE` ni de `UNKNOWN_SOURCE` silencieusement ignoré) ;
- aucune étape `HEAVY` n'a été détectée dans une requête dont la source racine n'est pas amont ;
- aucune requête n'a été classée `NA` par manque d'information.

L'agent ne doit jamais produire `OK` si une partie du graphe de requêtes n'a pas pu être résolue ou si des fonctions M non reconnues (`UNKNOWN`) ont été rencontrées sans être signalées.

---

## 15. Résumé de la règle

```text
RÈGLE BP-04 (SEM-003)

CONSTRUIRE le graphe de requêtes (tables + expressions partagées)
POUR chaque requête atteignable depuis une table du modèle

    RÉSOUDRE la source racine (remonter les références jusqu'à un connecteur réel)
    SI source racine ∈ {DATAFLOW, GOLD, NATIVE_QUERY_FOLDED}
        is_upstream = VRAI
    SINON
        is_upstream = FAUX

    CLASSER chaque étape après la source : HEAVY (jointure/pivot/agrégation/script...)
                                            ou LIGHT (typage/renommage/sélection...)

    SI au moins une étape HEAVY présente
        requête = KO
    SINON
        requête = OK

    SI la requête n'a pas de code M analysable (DAX, DirectQuery/DirectLake sans M)
        requête = NA

    ENREGISTRER le résultat avec la preuve (connecteur racine + étapes lourdes)
FIN POUR

SI au moins une requête est KO
    règle = KO
SINON SI au moins une requête est NA
    règle = NA
SINON
    règle = OK

AFFICHER toutes les requêtes KO (avec recommandation) et toutes les requêtes NA
```

La propriété décisionnelle est exclusivement le **code M** de chaque partition/expression (`source = ...` / `expression <NOM> = let ... in ...`), analysé selon :

1. le connecteur atteint à la racine de la chaîne de résolution (`isUpstreamSource`) ;
2. la présence d'étapes appartenant à la liste des fonctions M « lourdes » (section 5).

Les annotations techniques (`annotation PBI_NavigationStepName`, `annotation PBI_ResultType`, `lineageTag`, `queryGroup`) ne modifient jamais le verdict.

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-04 (SEM-003) — Pousser les transformations en amont  │
│         (dataflows / gold)                                      │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │ Lister tables/*.tmdl          │
          │ Charger expressions.tmdl      │
          │ (si présent)                  │
          └──────────────┬────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ Trouvé ✅   ║    │ Aucun fichier de table │
         ╚════╤════════╝    │ trouvé ❌              │
              │              └──────────┬────────────┘
              │                         ▼
              │                 ┌───────────────────┐
              │                 │ Retour : NON_EVALUE│
              │                 └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ CONSTRUIRE le graphe de requêtes            │
   │ queries[nom] = {kind, m_code, origin_file}  │
   │ (tables avec partition = m + expressions    │
   │  de type requête de données)                │
   └──────────────────┬──────────────────────────┘
                       ▼
   ┌───────────────────────────────────────────┐
   │ CALCULER l'ensemble "reachable" : toutes    │
   │ les requêtes atteignables depuis une table  │
   │ du modèle (parcours récursif des références)│
   └──────────────────┬──────────────────────────┘
                       ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque requête ∈ reachable (boucle)   │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ Code M analysable ? (mode import,    │
        │ pas DAX pur / DirectQuery sans M)    │
        └───────┬──────────────────┬───────────┘
              non│                  │oui
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────────┐
         ║ requête = NA  ║  │ RÉSOUDRE la source racine    │
         ╚═══════════════╝  │ (remonter Source = ... jusqu'à│
                             │  un connecteur réel)          │
                             └───────────────┬─────────────────┘
                                             ▼
                             ┌────────────────────────────┐
                             │ Source = CIRCULAR_REFERENCE  │
                             │ ou UNKNOWN_SOURCE ?          │
                             └───────┬──────────────┬────────┘
                                  oui│                │non
                                     ▼                ▼
                          ╔═══════════════╗  ┌────────────────────────┐
                          ║ requête = NA  ║  │ is_upstream = source ∈  │
                          ╚═══════════════╝  │ {DATAFLOW, GOLD,        │
                                              │ NATIVE_QUERY_FOLDED} ?  │
                                              └──────────────┬───────────┘
                                                             ▼
                                              ┌────────────────────────────┐
                                              │ CLASSER chaque étape après   │
                                              │ Source : HEAVY (jointure,    │
                                              │ pivot, agrégation, script)   │
                                              │ ou LIGHT (typage, sélection) │
                                              └──────────────┬────────────────┘
                                                             ▼
                                              ┌────────────────────────────┐
                                              │ ≥1 étape HEAVY présente ?    │
                                              └───────┬──────────────┬────────┘
                                                    oui│                │non
                                                       ▼                ▼
                                            ╔═══════════════╗  ╔═══════════════╗
                                            ║ requête = KO  ║  ║ requête = OK  ║
                                            ╚═══════════════╝  ╚═══════════════╝
                       │
                       ▼ (ENREGISTRER avec preuve : connecteur racine + étapes lourdes,
                       │  boucle suivante jusqu'à la dernière requête reachable)
   ┌────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL (priorité KO > NA > OK) │
   │ SI au moins une requête KO    → règle = KO      │
   │ SINON SI au moins une requête NA → règle = NA   │
   │ SINON                           → règle = OK    │
   └───────────────────────┬────────────────────────┘
                            ▼
                RETOUR rule_status (OK / KO / NA)
```
