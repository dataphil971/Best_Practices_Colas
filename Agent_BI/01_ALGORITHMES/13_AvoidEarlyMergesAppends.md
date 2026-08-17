# BP-13 — Réserver les merges/appends coûteux à la fin de la chaîne d'étapes M

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que les opérations M **structurellement coûteuses** — fusion de requêtes (`Table.NestedJoin`, `Table.Join`, `Table.FuzzyNestedJoin`) et concaténation de requêtes (`Table.Combine`, l'équivalent M de l'« Append » de l'interface Power Query) — sont positionnées **le plus tard possible** dans la chaîne d'étapes `let ... in ...` d'une requête, plutôt qu'en tout début de requête.

Ce positionnement a deux conséquences directes :

1. **Query folding** : lorsqu'une requête est adossée à une source repliable (SQL, Databricks, OData...), le repli s'interrompt dès la première étape non repliable rencontrée dans l'ordre d'exécution. Une fusion ou une concaténation entre deux requêtes de origines différentes casse quasi systématiquement le folding. Si cette étape est placée tôt, **toutes** les étapes suivantes (renommage, typage, sélection de colonnes...) s'exécutent alors en local dans le moteur Mashup, alors qu'elles auraient pu être repliées vers la source si la fusion avait été repoussée après elles.
2. **Volume traité localement** : une fusion ou un append coûte d'autant plus cher (temps CPU, mémoire) que les tables en entrée sont volumineuses. Filtrer les lignes (`Table.SelectRows`), réduire les colonnes (`Table.SelectColumns`) et corriger les types **avant** la fusion réduit mécaniquement le volume traité par l'opération lourde elle-même.

Cette règle est **complémentaire** de deux autres bonnes pratiques du référentiel, avec lesquelles elle ne doit pas être confondue :

- [BP-04](04_PushTransformUpstream.md) s'intéresse à la **source racine** de la requête (la transformation devrait-elle être déléguée à un dataflow, une couche gold, ou une requête native repliable ?) ;
- [BP-15](15_QueryFolding.md) s'intéresse au **repli effectif** vers la source (le folding est-il réellement préservé techniquement ?) ;
- **BP-13** ne regarde ni la source, ni le folding réel : elle regarde exclusivement **l'ordre relatif des étapes à l'intérieur d'une requête donnée** — une fusion peut être positionnée tardivement dans une requête dont la source n'est de toute façon pas repliable (SharePoint, Excel...), et la règle reste pertinente car elle réduit quand même le volume traité localement.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables et d'expressions partagées du modèle ;
- du connecteur utilisé en amont de la requête ;
- du nombre total d'étapes de chaque requête ;
- du nom des étapes (généré automatiquement par l'interface ou renommé manuellement) ;
- du fait que la requête soit une table physique du modèle ou une expression intermédiaire de `expressions.tmdl`.

---

## 2. Emplacement des fichiers concernés

L'agent doit lire le code M dans les deux mêmes emplacements que BP-04, car une opération de fusion/append peut se trouver aussi bien dans une table physique que dans une expression partagée intermédiaire :

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl        (partitions "= m", propriété source = ...)
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl      (blocs expression <NOM> = let ... in ...)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\expressions.tmdl   (contient SOURCE, F_MONORESPONSES, F_SCORERESPONSES...)
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
```

Aucun fichier du rapport (`<REPORT_PATH>`) n'est nécessaire pour cette règle : elle porte uniquement sur le code M du modèle sémantique.

---

## 3. Élément(s) / propriété(s) à contrôler

Pour chaque requête, l'agent doit extraire la **liste ordonnée des étapes** du bloc `let ... in ...`, dans l'ordre où elles apparaissent textuellement (cet ordre correspond à l'ordre d'exécution logique, sauf dépendances explicites entre étapes non consécutives, cas rare à signaler en `NA`).

Exemple réel — requête `SOURCE` (`expressions.tmdl`), 16 étapes numérotées de 0 à 15 :

```text
0  Lignes filtrées                         (Table.SelectRows)              LIGHT
1  Fichiers masqués filtrés1                (Table.SelectRows)              LIGHT
2  Appeler une fonction personnalisée1      (Table.AddColumn)               LIGHT
3  Colonnes renommées1                      (Table.RenameColumns)           LIGHT
4  Autres colonnes supprimées1              (Table.SelectColumns)           LIGHT
5  Colonne de tables développée1            (Table.ExpandTableColumn)       LIGHT
6  Type modifié                             (Table.TransformColumnTypes)    LIGHT
7  Colonnes renommées                       (Table.RenameColumns)           LIGHT
8  Texte extrait entre les délimiteurs      (Table.TransformColumns)        LIGHT
9  Changed Type                             (Table.TransformColumnTypes)    LIGHT
10 Extracted Text Before Delimiter          (Table.TransformColumns)        LIGHT
11 Merged Queries                           (Table.NestedJoin)              HEAVY  ← fusion
12 Expanded D_STRUCTURES                    (Table.ExpandTableColumn)       HEAVY  (suite du merge)
13 Added Custom                             (Table.AddColumn)               LIGHT
14 Changed Type1                            (Table.TransformColumnTypes)    LIGHT
15 Removed Other Columns                    (Table.SelectColumns)           LIGHT
```

Ici, la fusion (`Merged Queries`, `Table.NestedJoin` contre `D_STRUCTURES`) intervient à l'étape 11 sur 16, soit après 69 % des étapes : tout le nettoyage, le typage et le renommage ont déjà été effectués avant la fusion. C'est un exemple **conforme** à BP-13 (même si, par ailleurs, BP-04 la signale `KO` pour une autre raison : la source racine `SOURCE` reste un fichier SharePoint brut).

Les fonctions M qualifiant une étape de « lourde » pour cette règle sont :

```python
HEAVY_ORDERING_FUNCTIONS = {
    "Table.NestedJoin", "Table.Join", "Table.FuzzyNestedJoin",   # fusions
    "Table.Combine",                                              # append
}
```

Les fonctions qui suivent immédiatement une fusion pour en matérialiser le résultat (`Table.ExpandTableColumn` juste après un `Table.NestedJoin`) sont rattachées à la même opération logique et ne comptent pas comme une seconde étape lourde indépendante.

---

## 4. Règle(s) d'évaluation

Pour chaque requête contenant au moins une fusion ou un append, l'agent calcule :

- `position_ratio = index_première_étape_lourde / (nombre_total_étapes - 1)` (0 = tout au début, 1 = toute dernière étape) ;
- `reducing_steps_after` = nombre d'étapes `Table.SelectRows` / `Table.SelectColumns` / `Table.RemoveColumns` **après** la première étape lourde (occasions manquées de réduire le volume avant la fusion).

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Aucune fusion/append dans la requête | `NA` | La règle ne s'applique pas à cette requête. |
| `position_ratio >= 0.5` et `reducing_steps_after == 0` | `OK` | La fusion/append est positionnée dans la seconde moitié de la requête, après le nettoyage ; aucune réduction de volume n'a été omise en amont. |
| `position_ratio >= 0.5` et `reducing_steps_after > 0` | `WARN` | La fusion est globalement tardive, mais des étapes de filtrage/sélection de colonnes postérieures auraient pu être remontées avant la fusion pour en réduire le coût. |
| `position_ratio < 0.5` et `reducing_steps_after == 0` | `KO` | La fusion/append intervient dans la première moitié de la requête, avant l'essentiel du nettoyage. |
| `position_ratio < 0.25` (quel que soit `reducing_steps_after`) | `KO` | La fusion/append est quasiment la première opération de la requête — cas le plus pénalisant, à corriger en priorité. |
| Requête sans code M analysable (table calculée DAX, DirectQuery/DirectLake sans partition M) | `NA` | Analyse impossible sur cette requête. |

Exemple chiffré :

| Requête | Étape lourde | Position | Total étapes | `position_ratio` | Étapes réductrices après | Statut |
|---|---|---|---|---|---|---|
| `SOURCE` | `Merged Queries` (`Table.NestedJoin`) | 11 | 16 | 0.73 | 0 (`Removed Other Columns` en fin n'est pas « manquée », c'est la sélection finale normale) | `OK` |
| `D_USERS` | `Left Join between D_USER and D_STRUCTURES` (`Table.NestedJoin`) | 1 | 4 | 0.33 | 0 | `KO` |
| `F_RESPONSES` (hypothèse) | `Table.NestedJoin` en étape 0 | 0 | 8 | 0.0 | 3 | `KO` (position < 0.25) |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables/*.tmdl`.
2. Charger `expressions.tmdl` s'il existe.
3. Si aucun fichier de table n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Construire la liste des requêtes analysables
1. Extraire chaque table avec partition `= m`.
2. Extraire chaque expression de type requête de données (paramètres et fonctions utilitaires exclus).
3. Ne retenir que les requêtes atteignables depuis une table réellement chargée dans le modèle (mêmes principes de graphe que BP-04), afin d'ignorer les brouillons non utilisés.

### Étape 3 — Analyser chaque requête
Pour chaque requête retenue : extraire la liste ordonnée des étapes ; détecter toutes les étapes lourdes (`HEAVY_ORDERING_FUNCTIONS`) ; s'il n'y en a aucune, marquer `NA` et passer à la requête suivante ; sinon calculer `position_ratio` et `reducing_steps_after` ; appliquer la table de décision de la section 4 ; enregistrer le résultat avec preuve (nom de l'étape, index, total d'étapes).

### Étape 4 — Ne pas s'arrêter à la première anomalie
L'agent doit analyser **toutes** les requêtes contenant une opération lourde, même après avoir détecté un premier `KO` : le rapport final doit lister l'intégralité des requêtes non conformes, pas seulement la première rencontrée.

### Étape 5 — Terminer l'analyse
Produire le nombre total de requêtes analysées, le nombre de requêtes contenant au moins une fusion/append, la répartition `OK`/`WARN`/`KO`/`NA`, et le détail de chaque requête `KO` et `WARN`.

---

## 6. Détection robuste / normalisation

- Les étapes peuvent être nommées `#"Nom avec espaces"` ou `NomSimple` : l'agent doit extraire le nom d'étape indépendamment de cette syntaxe.
- Une étape peut appeler plusieurs fonctions imbriquées (`Table.ExpandTableColumn(Table.NestedJoin(...), ...)`) : dans ce cas, l'étape doit être classée `HEAVY` dès lors qu'une fonction de `HEAVY_ORDERING_FUNCTIONS` apparaît n'importe où dans son expression, même imbriquée.
- Les commentaires `//` et `/* ... */` doivent être ignorés lors du parsing des fonctions mais peuvent être conservés comme contexte.
- L'ordre des étapes est déterminé par l'ordre textuel de leur définition dans le bloc `let`, **pas** par un éventuel ordre alphabétique des noms d'étapes ni par leur ordre d'apparition dans une liste de dépendances.
- Si une étape référence une variable non immédiatement précédente (dépendance non linéaire, rare mais possible en M), l'agent doit résoudre l'ordre réel de dépendance avant de calculer `position_ratio` ; si cette résolution échoue, la requête est classée `NA` avec la raison « ordre des étapes non déterminable ».
- La casse des noms de fonctions M est fixe (`Table.NestedJoin`, jamais `table.nestedjoin`) : aucune normalisation de casse n'est nécessaire sur les noms de fonctions, mais les noms d'étapes définis par l'utilisateur peuvent contenir n'importe quelle casse et ne doivent jamais être comparés de façon sensible à la casse pour la détection de motifs (« Merged », « merged », « Fusion »...).
- Une requête encadrée par des triples backticks `` ``` `` (comme `D_STRUCTURES` dans `expressions.tmdl`) doit voir cette enveloppe retirée avant tout parsing des étapes.

---

## 7. Pseudo-code détaillé

```python
HEAVY_ORDERING_FUNCTIONS = {"Table.NestedJoin", "Table.Join", "Table.FuzzyNestedJoin", "Table.Combine"}
REDUCING_FUNCTIONS = {"Table.SelectRows", "Table.SelectColumns", "Table.RemoveColumns"}

def extract_ordered_steps(m_code):
    m_code = strip_triple_backtick_wrapper(m_code)
    raw_steps = parse_let_block(m_code)   # liste ordonnée: [(step_name, step_expression), ...]
    return raw_steps

def step_is_heavy(step_expression):
    called_functions = find_all_called_functions(step_expression)  # gère les appels imbriqués
    return bool(called_functions & HEAVY_ORDERING_FUNCTIONS)

def step_is_reducing(step_expression):
    called_functions = find_all_called_functions(step_expression)
    return bool(called_functions & REDUCING_FUNCTIONS)

def evaluate_query_step_order(query_name, m_code):
    steps = extract_ordered_steps(m_code)
    n = len(steps)
    if n == 0:
        return {"query": query_name, "status": "NA", "reason": "Aucune étape analysable"}

    heavy_indices = [i for i, (name, expr) in enumerate(steps) if step_is_heavy(expr)]
    if not heavy_indices:
        return {"query": query_name, "status": "NA", "reason": "Aucune fusion/append dans cette requête"}

    first_heavy_index = heavy_indices[0]
    position_ratio = first_heavy_index / max(n - 1, 1)

    reducing_after = sum(
        1 for i, (name, expr) in enumerate(steps)
        if i > first_heavy_index and step_is_reducing(expr)
    )

    evidence = {
        "query": query_name,
        "heavy_step_name": steps[first_heavy_index][0],
        "heavy_step_index": first_heavy_index,
        "total_steps": n,
        "position_ratio": round(position_ratio, 2),
        "reducing_steps_after": reducing_after,
    }

    if position_ratio < 0.25:
        return {**evidence, "status": "KO",
                "reason": "Fusion/append quasiment en tête de requête"}
    if position_ratio < 0.5:
        return {**evidence, "status": "KO",
                "reason": "Fusion/append avant l'essentiel du nettoyage de la requête"}
    if reducing_after > 0:
        return {**evidence, "status": "WARN",
                "reason": "Fusion tardive mais filtrage/sélection de colonnes postérieurs auraient pu être remontés avant"}
    return {**evidence, "status": "OK"}


ok_results, warn_results, ko_results, na_results = [], [], [], []

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

    result = evaluate_query_step_order(name, queries[name]["m_code"])
    {"OK": ok_results, "WARN": warn_results, "KO": ko_results, "NA": na_results}[result["status"]].append(result)
```

---

## 8. Calcul du statut global

```python
if ko_results:
    rule_status = "KO"
elif warn_results:
    rule_status = "WARN"
elif na_results and not ok_results:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > NA > OK`. Le statut `WARN` correspond à une recommandation d'optimisation non bloquante (la bonne pratique n'est pas violée sur le critère principal, mais une amélioration reste possible) ; il ne doit jamais masquer un `KO` détecté par ailleurs.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les requêtes avec fusion/append la positionnent tard, sans réduction manquée | `OK` |
| Au moins une requête présente une fusion/append tardive mais avec des réductions manquées | `WARN` |
| Au moins une requête présente une fusion/append en début de chaîne | `KO` |
| Aucune requête du modèle ne contient de fusion/append | `NA` (règle non applicable) |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-13",
  "rule_name": "Réserver les merges/appends coûteux à la fin de la chaîne d'étapes M",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_queries_with_merge_or_append": 3,
  "ok_queries": 3,
  "warn_queries": 0,
  "ko_queries": 0,
  "na_queries": 21,
  "ok_details": [
    {"query": "SOURCE", "heavy_step_name": "Merged Queries", "heavy_step_index": 11, "total_steps": 16, "position_ratio": 0.73}
  ],
  "ko_details": [],
  "warn_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-13",
  "rule_name": "Réserver les merges/appends coûteux à la fin de la chaîne d'étapes M",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_queries_with_merge_or_append": 3,
  "ok_queries": 1,
  "warn_queries": 0,
  "ko_queries": 2,
  "na_queries": 21,
  "ko_details": [
    {
      "query": "D_USERS",
      "heavy_step_name": "Left Join between D_USER and D_STRUCTURES",
      "heavy_step_index": 1,
      "total_steps": 4,
      "position_ratio": 0.33,
      "reason": "Fusion/append avant l'essentiel du nettoyage de la requête"
    },
    {
      "query": "F_RESPONSES",
      "heavy_step_name": "Source (Table.NestedJoin)",
      "heavy_step_index": 0,
      "total_steps": 8,
      "position_ratio": 0.0,
      "reason": "Fusion/append quasiment en tête de requête"
    }
  ],
  "warn_details": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-13 — Merges/appends en fin de chaîne : OK

3 requêtes contiennent une fusion ou un append ; dans les 3 cas, l'opération
est positionnée après le nettoyage, le typage et le renommage des colonnes
(ratio de position moyen : 0.71). Aucune réduction de volume n'a été omise
en amont de la fusion.
```

### Exemple `KO`

```text
BP-13 — Merges/appends en fin de chaîne : KO

1 requête conforme sur 3 requêtes contenant une fusion/append.

Requêtes non conformes :
- D_USERS : la fusion "Left Join between D_USER and D_STRUCTURES"
  (Table.NestedJoin) est la 2e étape sur 4 (ratio 0.33) — elle intervient
  avant tout nettoyage.
- F_RESPONSES : la fusion (Table.NestedJoin) est la toute première étape
  de la requête (ratio 0.0).

Correction attendue :
déplacer les étapes de sélection de colonnes, de filtrage et de typage
actuellement situées après la fusion (s'il y en a) avant celle-ci, et
repousser la fusion elle-même le plus près possible de la fin de la requête,
juste avant les étapes de présentation finale.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- tous les fichiers de tables et `expressions.tmdl` ont été lus et parsés sans erreur ;
- le graphe de requêtes atteignables depuis le modèle a été construit intégralement ;
- pour chaque requête retenue, la liste ordonnée complète des étapes a pu être extraite (pas de troncature) ;
- toutes les fonctions imbriquées de chaque étape ont été détectées, pas seulement la fonction de tête ;
- toutes les requêtes contenant au moins une fusion/append ont été évaluées, sans exception ;
- aucune requête n'a un `position_ratio < 0.5` ;
- aucune requête `WARN` n'a été reclassée silencieusement en `OK`.

L'agent ne doit jamais produire `OK` si l'ordre des étapes d'une requête n'a pas pu être déterminé de façon fiable (dépendances non linéaires non résolues) : dans ce cas, la requête doit être classée `NA` et signalée, pas ignorée.

---

## 12. Résumé de la règle

```text
RÈGLE BP-13

CONSTRUIRE la liste des requêtes atteignables (tables + expressions partagées)
POUR chaque requête

    EXTRAIRE la liste ordonnée des étapes (let ... in ...)
    DÉTECTER les étapes appelant Table.NestedJoin / Table.Join /
             Table.FuzzyNestedJoin / Table.Combine

    SI aucune étape lourde détectée
        requête = NA
        PASSER à la requête suivante

    position_ratio = index_première_étape_lourde / (nb_étapes - 1)
    reducing_after = nb d'étapes SelectRows/SelectColumns/RemoveColumns
                      situées après la première étape lourde

    SI position_ratio < 0.5
        requête = KO
    SINON SI reducing_after > 0
        requête = WARN
    SINON
        requête = OK

    ENREGISTRER le résultat avec preuve (nom d'étape, index, ratio)
FIN POUR

SI au moins une requête KO
    règle = KO
SINON SI au moins une requête WARN
    règle = WARN
SINON SI aucune requête ne contient de fusion/append
    règle = NA
SINON
    règle = OK

AFFICHER toutes les requêtes KO et WARN, avec recommandation de réordonnancement
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-13 — Merges/appends en fin de chaîne d'étapes M          │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
              ┌────────────────────────────────────┐
              │ Lister tables/*.tmdl                 │
              │ + charger expressions.tmdl           │
              └────────────────┬──────────────────────┘
                   ┌──────────┴──────────┐
                   ▼                     ▼
             ╔═════════════╗     ┌──────────────────┐
             ║ Fichiers    ║     │ Aucun fichier de   │
             ║ trouvés ✅  ║     │ table ❌            │
             ╚══════╤══════╝     └─────────┬──────────┘
                    │                      ▼
                    │              ┌────────────────┐
                    │              │ Retour :        │
                    │              │ NON_EVALUE      │
                    │              └────────────────┘
                    ▼
       ┌───────────────────────────────────────┐
       │ CONSTRUIRE le graphe de requêtes        │
       │ atteignables (tables + expressions)     │
       └────────────────┬─────────────────────────┘
                        ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque requête atteignable (boucle)   │
     └────────────────┬────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ Code M analysable ?            │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ┌──────────┐   ╔═══════════╗
       │ NON = NA │   ║ OUI        ║
       └──────────┘   ╚═════╤══════╝
                            ▼
              ┌─────────────────────────────┐
              │ EXTRAIRE la liste ordonnée    │
              │ des étapes (let ... in ...)   │
              └──────────────┬─────────────────┘
                            ▼
              ┌─────────────────────────────┐
              │ DÉTECTER les étapes lourdes   │
              │ (NestedJoin/Join/FuzzyJoin/   │
              │ Combine), y compris imbriquées │
              └──────────────┬─────────────────┘
                            ▼
                  ┌─────────┴─────────┐
                  ▼                   ▼
            ┌──────────┐        ╔═══════════╗
            │ Aucune    │        ║ Au moins   ║
            │ = NA      │        ║ une ✅     ║
            └──────────┘        ╚═════╤══════╝
                                      ▼
                    ┌──────────────────────────────┐
                    │ CALCULER position_ratio =      │
                    │ index_1re_étape_lourde/(n-1)   │
                    │ reducing_after = nb d'étapes    │
                    │ Select*/Remove* APRÈS           │
                    └──────────────┬─────────────────┘
                                  ▼
                       ┌──────────┴──────────┐
                       ▼                     ▼
                 ╔═══════════╗        ┌──────────────┐
                 ║ ratio<0.5 ║        │ ratio >= 0.5   │
                 ║ = KO      ║        └───────┬────────┘
                 ╚═══════════╝                ▼
                                      ┌────────┴────────┐
                                      ▼                 ▼
                                ╔═══════════╗     ┌──────────┐
                                ║reducing>0 ║     │reducing=0 │
                                ║ = WARN    ║     │ = OK      │
                                ╚═══════════╝     └──────────┘
                                      │                 │
                                      └────────┬─────────┘
                                              ▼
                              FIN DE BOUCLE (requête suivante)
                                              │
                                              ▼
                ┌────────────────────────────────────────────┐
                │ CALCUL DU RÉSULTAT FINAL                     │
                │ KO présent ?           → règle = KO          │
                │ Sinon WARN présent ?   → règle = WARN        │
                │ Sinon NA seul (aucun OK) → règle = NA        │
                │ Sinon                   → règle = OK         │
                └────────────────────┬──────────────────────────┘
                                     ▼
                     RETOUR rule_status (OK/WARN/KO/NA)
```
