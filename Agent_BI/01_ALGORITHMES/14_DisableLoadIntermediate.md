# BP-14 — Désactivation du chargement des requêtes strictement intermédiaires

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que les requêtes Power Query **strictement intermédiaires** — celles qui ne servent que de brique à d'autres requêtes et qui ne sont jamais destinées à être consultées directement dans le modèle — ont bien leur chargement désactivé, plutôt que d'être matérialisées inutilement comme tables physiques du modèle sémantique.

Dans l'interface Power Query, cela correspond à la case à cocher « Activer le chargement » (`EnableLoad`) décochée sur une requête. Dans un projet PBIP au format TMDL, ce comportement se traduit structurellement de la façon suivante :

- une requête **chargée** dans le modèle possède un fichier dédié dans `definition\tables\<NOM>.tmdl` **et** une entrée `ref table <NOM>` dans `model.tmdl` ;
- une requête dont le chargement est désactivé n'a **pas** de fichier `tables\<NOM>.tmdl` ni d'entrée `ref table` : elle n'existe que comme bloc `expression <NOM> = ...` dans `expressions.tmdl`, référencé par d'autres requêtes via `Source = <NOM>`.

Charger inutilement une requête intermédiaire dans le modèle a un coût réel : elle consomme de la mémoire VertiPaq, alourdit le temps d'actualisation, complexifie inutilement l'arborescence des tables visibles par les créateurs de rapports, et peut faire apparaître dans le volet des champs une « table fantôme » qui n'a aucune vocation à être utilisée directement dans un visuel ou une mesure.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de requêtes et de tables du modèle ;
- du nombre de niveaux d'imbrication entre requêtes intermédiaires (une requête intermédiaire peut elle-même dépendre d'une autre requête intermédiaire) ;
- de l'ordre d'apparition des blocs `expression` dans `expressions.tmdl` ou des entrées `ref table` dans `model.tmdl`.

---

## 2. Emplacement des fichiers concernés

L'agent doit croiser trois emplacements :

```text
<SEMANTIC_MODEL_PATH>\definition\model.tmdl            (liste des "ref table" = tables réellement chargées)
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl          (une table chargée = un fichier physique)
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl       (requêtes partagées, chargées ou non)
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl     (pour identifier les tables intégrées au schéma en étoile)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\model.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\expressions.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\relationships.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1 Liste des tables réellement chargées (`model.tmdl`)

```tmdl
ref table MEASURE
ref table T_CHOICE_COUNTRY_JOB
ref table F_ADOPTION_QUESTION
ref table F_RESPONSES
ref table D_CAMPAIGNS
ref table D_USERS
ref table T_PAGE_NUMBER
ref table T_NOTIFICATION
ref table T_NOTIFICATION_TEXT
ref table D_USAGE_FREQUENCY_LEVELS
ref table P_EVOLUTION_LEGEND_TOP
ref table P_EVOLUTION_LEGEND_BOTTOM
ref table P_EVOLUTION_VALUE_TOP
ref table P_EVOLUTION_VALUE_BOTTOM
ref table D_CHOICE
```

Seuls les noms listés ici sont des tables **effectivement chargées** (`EnableLoad` effectif = `true`).

### 3.2 Requêtes présentes dans `expressions.tmdl` mais absentes de `ref table`

```tmdl
expression D_ANSWERS = let ... in ...
expression F_MONORESPONSES = let ... in ...
expression F_SCORERESPONSES = let ... in ...
expression F_ADOPTION_LEVEL = let ... in ...
expression D_STRUCTURES = ``` let ... in ... ```
expression SOURCE = let ... in ...
```

Aucun de ces noms n'apparaît dans la liste `ref table` du projet audité : ce sont donc, par construction, des requêtes dont le chargement est désactivé — conforme à la bonne pratique, **à condition** qu'elles soient bien utilisées uniquement comme brique par d'autres requêtes.

### 3.3 Graphe de dépendances entre requêtes

L'agent doit établir, pour chaque requête, la liste des autres requêtes qui la référencent en `Source = <NOM>` ou comme argument d'une fonction (`Table.NestedJoin(..., D_STRUCTURES, ...)`), afin de qualifier une requête de « strictement intermédiaire » : référencée par au moins une autre requête, et non porteuse de relation directe dans `relationships.tmdl`.

```text
D_USERS (table chargée)        → Source = SOURCE ; Table.NestedJoin(..., D_STRUCTURES, ...)
F_MONORESPONSES (expression)   → Source = SOURCE
F_RESPONSES (table chargée)    → Source = Table.NestedJoin(F_MONORESPONSES, ..., F_SCORERESPONSES, ...)
SOURCE (expression)            → référencée par D_USERS, F_MONORESPONSES, F_SCORERESPONSES
D_STRUCTURES (expression)      → référencée par SOURCE, D_USERS
```

`SOURCE` et `D_STRUCTURES` sont donc bien référencées comme brique par plusieurs autres requêtes, sans jamais apparaître elles-mêmes en `ref table` : c'est le cas nominal attendu par cette règle.

---

## 4. Règle(s) d'évaluation

Pour chaque requête du modèle (table ou expression), l'agent détermine d'abord si elle est **structurellement intermédiaire** : référencée par au moins une autre requête, **et** absente de `relationships.tmdl` en tant que table source de relation.

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Requête intermédiaire, absente de `ref table` (pas de fichier `tables\<NOM>.tmdl`) | `OK` | Chargement correctement désactivé : la requête n'est utilisée que comme brique. |
| Requête intermédiaire, présente dans `ref table` (fichier `tables\<NOM>.tmdl` existe) | `KO` | La requête est matérialisée en table du modèle alors qu'elle ne sert qu'à alimenter d'autres requêtes — table fantôme inutile. |
| Requête non référencée par aucune autre requête (terminale) et présente dans `ref table` | `NA` | Hors périmètre : c'est une table finale normale du modèle, pas une requête intermédiaire. |
| Requête non référencée par aucune autre requête et absente de `ref table` | `NA` | Requête orpheline non chargée et non utilisée — relève d'une autre bonne pratique (nettoyage des requêtes mortes), pas de celle-ci. |
| Requête intermédiaire mais également porteuse d'une relation dans `relationships.tmdl` | `NA` | Elle participe directement au schéma du modèle : elle n'est pas « strictement » intermédiaire, son chargement est légitime. |

Exemples issus du modèle audité :

| Requête | Référencée par d'autres requêtes ? | Présente en `ref table` ? | Porte une relation ? | Statut |
|---|---|---|---|---|
| `SOURCE` | Oui (D_USERS, F_MONORESPONSES, F_SCORERESPONSES) | Non | Non | `OK` |
| `D_STRUCTURES` | Oui (SOURCE, D_USERS) | Non | Non | `OK` |
| `F_MONORESPONSES` | Oui (F_RESPONSES) | Non | Non | `OK` |
| `D_USERS` | Oui (référencée par des relations) | Oui | Oui (`F_RESPONSES.CAMPAIGN_USER_LOGIN → D_USERS.CAMPAIGN_USER_LOGIN`) | `NA` (table finale légitime) |
| *(hypothèse)* `D_STAGING_TEMP` | Oui (une seule table l'utilise) | Oui (chargée par erreur) | Non | `KO` |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lire `model.tmdl` et extraire toutes les lignes `ref table <NOM>`.
2. Lister tous les fichiers `tables\*.tmdl`.
3. Charger `expressions.tmdl` s'il existe.
4. Charger `relationships.tmdl` s'il existe.
5. Si `model.tmdl` est introuvable, retourner `NON_EVALUE`.

### Étape 2 — Construire le graphe de requêtes et de dépendances
1. Construire l'ensemble `queries` (tables + expressions), comme pour BP-04.
2. Pour chaque requête, extraire les noms des autres requêtes locales qu'elle référence dans son code M.
3. Construire la relation inverse `referenced_by[nom] = [requêtes qui la référencent]`.

### Étape 3 — Qualifier chaque requête
Pour chaque requête : déterminer si elle est référencée par au moins une autre requête ; déterminer si elle porte une relation dans `relationships.tmdl` (recherche du nom de table dans `fromColumn`/`toColumn`) ; déterminer si elle est présente dans `ref table`.

### Étape 4 — Appliquer la règle de décision
Appliquer la table de décision de la section 4 à chaque requête, sans s'arrêter à la première anomalie détectée — toutes les requêtes intermédiaires chargées à tort doivent être recensées.

### Étape 5 — Terminer l'analyse
Produire le nombre total de requêtes analysées, le nombre de requêtes qualifiées « strictement intermédiaires », la répartition `OK`/`KO`/`NA`, et le détail complet des requêtes `KO`.

---

## 6. Détection robuste / normalisation

- Le nom d'une requête peut être encadré de guillemets simples en TMDL lorsqu'il contient des caractères spéciaux (`'REPORT NAME'`, `'SOURCE\SOURCES V1'` pour le nom d'un `queryGroup`) : l'agent doit comparer les noms de requêtes après avoir retiré ces guillemets d'échappement.
- Une requête peut être référencée soit par un identifiant nu (`Source = SOURCE`), soit comme argument d'une fonction (`Table.NestedJoin(..., D_STRUCTURES, ...)`, `Table.ExpandTableColumn(..., "D_STRUCTURES", ...)` où le nom apparaît alors comme littéral texte servant de nom de colonne imbriquée — dans ce dernier cas, il ne s'agit **pas** d'une référence à une autre requête et l'agent ne doit pas la compter comme telle) : seule la présence du nom en position d'argument de type valeur/table (et non en tant que chaîne de nom de colonne) doit être retenue.
- Les paramètres (`meta [IsParameterQuery=true, ...]`) ne sont jamais considérés comme des requêtes intermédiaires au sens de cette règle : leur non-chargement est un comportement normal et systématique de Power Query, pas une bonne pratique à vérifier.
- Les fonctions utilitaires (`expression Fonction_source = (Paramètre_V1 as binary) => ...`) sont également hors périmètre : elles ne représentent pas une table de données.
- La comparaison des noms de requêtes doit être insensible à un éventuel encodage ou échappement TMDL des espaces et accents, mais reste sensible à la casse (Power Query distingue `SOURCE` de `Source` comme identifiants).
- L'ordre des lignes `ref table` dans `model.tmdl` et des blocs `expression` dans `expressions.tmdl` est arbitraire et ne doit jamais être utilisé comme critère de décision.

---

## 7. Pseudo-code détaillé

```python
def is_parameter_or_function(expr):
    return "IsParameterQuery=true" in expr.meta_text or expr.result_type == "Function"

def find_referenced_query_names(m_code, known_names):
    # Détecte les identifiants nus (Source = NOM) et les arguments de type table/valeur
    # référençant un nom de requête connu, en excluant les littéraux texte utilisés
    # comme noms de colonnes (ex: "D_STRUCTURES" comme string dans ExpandTableColumn).
    return extract_table_value_references(m_code, known_names)

loaded_table_names = parse_model_tmdl_ref_tables("<SEMANTIC_MODEL_PATH>/definition/model.tmdl")
if loaded_table_names is None:
    return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
            "reason": "model.tmdl introuvable ou illisible"}

table_files = find_all_tmdl_files("<SEMANTIC_MODEL_PATH>/definition/tables/")
expressions_file = "<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl"

queries = build_query_graph(table_files, expressions_file)     # nom -> {kind, m_code, ...}
queries = {name: q for name, q in queries.items() if not is_parameter_or_function(q)}

referenced_by = {name: [] for name in queries}
for name, q in queries.items():
    for ref in find_referenced_query_names(q["m_code"], set(queries.keys())):
        if ref in referenced_by:
            referenced_by[ref].append(name)

relationship_tables = parse_relationship_table_names("<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl")

ok_results, ko_results, na_results = [], [], []

for name, q in queries.items():
    is_referenced = len(referenced_by[name]) > 0
    is_loaded = name in loaded_table_names
    carries_relationship = name in relationship_tables

    if not is_referenced:
        na_results.append({"query": name, "status": "NA",
                            "reason": "Requête terminale non référencée : hors périmètre de cette règle"})
        continue

    if carries_relationship:
        na_results.append({"query": name, "status": "NA",
                            "reason": "Requête intermédiaire mais intégrée au schéma via une relation : chargement légitime"})
        continue

    if is_loaded:
        ko_results.append({
            "query": name, "status": "KO",
            "referenced_by": referenced_by[name],
            "reason": "Requête strictement intermédiaire chargée comme table du modèle (table fantôme)",
        })
    else:
        ok_results.append({
            "query": name, "status": "OK",
            "referenced_by": referenced_by[name],
        })
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
| Toutes les requêtes strictement intermédiaires ont le chargement désactivé | `OK` |
| Au moins une requête strictement intermédiaire est chargée comme table physique | `KO` |
| Aucune requête intermédiaire identifiée dans le modèle | `NA` |

---

## 9. Structure du résultat

Exemple `OK` (état actuel du projet audité) :

```json
{
  "rule_id": "BP-14",
  "rule_name": "Désactivation du chargement des requêtes strictement intermédiaires",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_queries": 27,
  "intermediate_queries": 6,
  "ok_queries": 6,
  "ko_queries": 0,
  "na_queries": 21,
  "ok_details": [
    {"query": "SOURCE", "referenced_by": ["D_USERS", "F_MONORESPONSES", "F_SCORERESPONSES"]},
    {"query": "D_STRUCTURES", "referenced_by": ["SOURCE", "D_USERS"]},
    {"query": "F_MONORESPONSES", "referenced_by": ["F_RESPONSES"]},
    {"query": "F_SCORERESPONSES", "referenced_by": ["F_RESPONSES"]},
    {"query": "F_ADOPTION_LEVEL", "referenced_by": ["F_ADOPTION_QUESTION"]},
    {"query": "D_ANSWERS", "referenced_by": ["F_SCORERESPONSES"]}
  ],
  "ko_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-14",
  "rule_name": "Désactivation du chargement des requêtes strictement intermédiaires",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_queries": 27,
  "intermediate_queries": 6,
  "ok_queries": 5,
  "ko_queries": 1,
  "na_queries": 21,
  "ko_details": [
    {
      "query": "D_STRUCTURES",
      "referenced_by": ["SOURCE", "D_USERS"],
      "reason": "Requête strictement intermédiaire chargée comme table du modèle (table fantôme)"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-14 — Chargement des requêtes intermédiaires désactivé : OK

6 requêtes strictement intermédiaires identifiées (SOURCE, D_STRUCTURES,
F_MONORESPONSES, F_SCORERESPONSES, F_ADOPTION_LEVEL, D_ANSWERS) : aucune
n'est chargée comme table physique du modèle. Toutes n'apparaissent que
dans expressions.tmdl et servent uniquement de brique à d'autres requêtes.
```

### Exemple `KO`

```text
BP-14 — Chargement des requêtes intermédiaires désactivé : KO

5 requêtes conformes sur 6 requêtes strictement intermédiaires identifiées.

Requête non conforme :
- D_STRUCTURES : référencée uniquement comme brique par SOURCE et D_USERS,
  mais chargée comme table physique du modèle (présente dans "ref table"
  et fichier tables\D_STRUCTURES.tmdl existant). Cette table n'est reliée
  à aucune autre table par une relation et ne devrait pas apparaître dans
  le volet des champs du rapport.

Correction attendue :
décocher "Activer le chargement" sur la requête D_STRUCTURES dans Power
Query, ou supprimer son "ref table" et son fichier de table TMDL associé
lors de la prochaine synchronisation du modèle.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- `model.tmdl` a été lu et toutes les lignes `ref table` ont été extraites ;
- tous les fichiers `tables\*.tmdl` ont été énumérés ;
- `expressions.tmdl` a été lu s'il existe ;
- `relationships.tmdl` a été lu s'il existe ;
- le graphe de dépendances entre requêtes a été construit sans erreur de parsing, y compris pour les références imbriquées dans des appels de fonction ;
- chaque requête a été qualifiée (intermédiaire strictement / terminale / porteuse de relation) avant d'être classée ;
- aucune requête strictement intermédiaire n'a été omise du croisement avec `ref table`.

L'agent ne doit jamais produire `OK` si le graphe de dépendances n'a pas pu être résolu intégralement, ou si une requête référencée par une autre n'a pas pu être localisée dans `queries` (référence pendante non résolue).

---

## 12. Résumé de la règle

```text
RÈGLE BP-14

LIRE model.tmdl → EXTRAIRE l'ensemble loaded_table_names (ref table ...)
CONSTRUIRE le graphe de requêtes (tables + expressions partagées)
CONSTRUIRE la relation inverse referenced_by[nom]
LIRE relationships.tmdl → EXTRAIRE relationship_tables

POUR chaque requête (hors paramètres et fonctions utilitaires)

    SI la requête n'est référencée par aucune autre requête
        requête = NA (requête terminale, hors périmètre)
        CONTINUER

    SI la requête porte une relation directe
        requête = NA (chargement légitime, intégrée au schéma)
        CONTINUER

    SI la requête est présente dans loaded_table_names
        requête = KO (table fantôme intermédiaire chargée à tort)
    SINON
        requête = OK (chargement correctement désactivé)

    ENREGISTRER le résultat avec la liste des requêtes qui la référencent
FIN POUR

SI au moins une requête KO
    règle = KO
SINON SI aucune requête intermédiaire identifiée
    règle = NA
SINON
    règle = OK

AFFICHER toutes les requêtes KO avec recommandation de désactivation du chargement
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-14 — Chargement des requêtes strictement intermédiaires │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ Lire model.tmdl → EXTRAIRE ref table     │
          └────────────────┬───────────────────────────┘
               ┌───────────┴───────────┐
               ▼                       ▼
         ╔═════════════╗       ┌──────────────────┐
         ║ Lisible ✅  ║       │ Introuvable ❌      │
         ╚══════╤══════╝       └─────────┬──────────┘
                │                        ▼
                │                ┌────────────────┐
                │                │ Retour :        │
                │                │ NON_EVALUE      │
                │                └────────────────┘
                ▼
     ┌─────────────────────────────────────────┐
     │ CONSTRUIRE le graphe de requêtes          │
     │ (tables + expressions, hors paramètres    │
     │ et fonctions utilitaires)                 │
     │ CONSTRUIRE referenced_by[nom]              │
     │ LIRE relationships.tmdl                    │
     └────────────────┬─────────────────────────────┘
                      ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque requête (boucle)                │
     └────────────────┬────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ Référencée par une autre        │
        │ requête ?                       │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ┌──────────┐   ╔═══════════╗
       │ NON = NA │   ║ OUI        ║
       │ (requête │   ╚═════╤══════╝
       │ terminale)│         ▼
       └──────────┘  ┌────────────────────────┐
                      │ Porte une relation        │
                      │ dans relationships.tmdl ? │
                      └──────────┬─────────────────┘
                           ┌──────┴──────┐
                           ▼             ▼
                     ┌──────────┐  ╔═══════════╗
                     │ OUI = NA │  ║ NON         ║
                     │(chargement│  ╚═════╤══════╝
                     │ légitime) │         ▼
                     └──────────┘  ┌────────────────────┐
                                    │ Présente dans          │
                                    │ ref table (loaded) ?   │
                                    └──────────┬─────────────┘
                                         ┌──────┴──────┐
                                         ▼             ▼
                                   ╔═══════════╗ ┌──────────┐
                                   ║ OUI = KO  ║ │ NON = OK  │
                                   ║ (table     ║ │(chargement│
                                   ║ fantôme)   ║ │ désactivé)│
                                   ╚═══════════╝ └──────────┘
                                         │             │
                                         └──────┬───────┘
                                               ▼
                              FIN DE BOUCLE (requête suivante)
                                               │
                                               ▼
                ┌────────────────────────────────────────────┐
                │ CALCUL DU RÉSULTAT FINAL                     │
                │ KO présent ?              → règle = KO       │
                │ Sinon NA seul (aucun OK)  → règle = NA       │
                │ Sinon                      → règle = OK      │
                └────────────────────┬──────────────────────────┘
                                     ▼
                     RETOUR rule_status (OK/KO/NA)
```
