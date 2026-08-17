# BP-27 — Disposition organisée du diagramme du modèle

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que la disposition visuelle des tables dans la vue des relations de Power BI Desktop (le « diagramme du modèle ») suit une organisation lisible et cohérente : tables de dimension et tables paramètres regroupées d'un côté (par convention en haut ou à gauche), tables de faits regroupées de l'autre (par convention en bas ou à droite), tables fonctionnellement proches disposées en clusters visuellement identifiables, et relations non enchevêtrées (peu ou pas de croisements de lignes entre tables non adjacentes). Un diagramme désorganisé (tables dispersées sans logique, chevauchements, tables isolées loin de leurs relations) ralentit la prise en main du modèle par un nouveau développeur et rend la maintenance des relations plus risquée.

Contrairement à la plupart des autres règles de ce corpus, cette bonne pratique ne porte pas sur une propriété métier du modèle (DAX, colonnes) mais sur des **coordonnées de mise en page**, stockées côté fichier de définition du modèle sémantique PBIP (`diagramLayout.json`) et non dans les fichiers TMDL eux-mêmes. Elle reste néanmoins évaluable de façon déterministe à partir de ces coordonnées et de la connaissance du rôle de chaque table (dimension, fait, paramètre) déduit du modèle TMDL.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables du modèle ;
- de la convention de nommage des tables (préfixes `D_`, `F_`, `T_`, `P_`... ou absence de préfixe) ;
- de l'échelle et du décalage global des coordonnées (translation/zoom du diagramme) ;
- du nombre de diagrammes définis (un modèle peut contenir plusieurs vues nommées).

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\diagramLayout.json
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\diagramLayout.json
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\relationships.tmdl
```

`diagramLayout.json` contient un tableau `diagrams`, chacun avec un nom (`name`), une liste de `nodes` (une entrée par table avec ses coordonnées `location.x` / `location.y` et sa taille `size.width` / `size.height`). Les fichiers TMDL des tables et le fichier des relations permettent de déterminer le rôle de chaque table (dimension, fait, paramètre) et les liens entre elles, nécessaires pour juger la cohérence de la disposition.

---

## 3. Élément(s) / propriété(s) à contrôler

Extrait réel de `diagramLayout.json` :

```json
{
  "diagrams": [
    {
      "nodes": [
        { "location": { "x": 988.26, "y": 9846.08 }, "nodeIndex": "F_RESPONSES", "size": { "height": 854.8, "width": 471.4 } },
        { "location": { "x": 1845.35, "y": 10113.45 }, "nodeIndex": "F_ADOPTION_QUESTION", "size": { "height": 306.7, "width": 234 } },
        { "location": { "x": 1542.75, "y": 10523.59 }, "nodeIndex": "D_CAMPAIGNS", "size": { "height": 289.7, "width": 234 } },
        { "location": { "x": 1547.05, "y": 9646.44 }, "nodeIndex": "D_USERS", "size": { "height": 373.1, "width": 234 } },
        { "location": { "x": 694.07, "y": 10520.02 }, "nodeIndex": "D_USAGE_FREQUENCY_LEVELS", "size": { "height": 271.4, "width": 234 } },
        { "location": { "x": 311.4, "y": 9821.39 }, "nodeIndex": "MEASURE", "size": { "height": 584.6, "width": 234 } }
      ],
      "name": "Toutes les tables"
    }
  ]
}
```

Chaque `nodeIndex` correspond au nom d'une table du modèle (`table <NOM>` en TMDL). L'agent doit classer chaque table par rôle :
- **fait** : table dont le nom commence par `F_`, ou détectée structurellement comme table de faits (nombreuses colonnes numériques, clés étrangères vers plusieurs dimensions, généralement la plus volumineuse) ;
- **dimension** : table dont le nom commence par `D_`, contenant des attributs descriptifs et étant du côté « un » d'une relation un-à-plusieurs vers une table de faits ;
- **paramètre / support** : table dont le nom commence par `P_`, `T_` (paramètre, table technique de notification/pagination), ou la table de mesures dédiée (cf. [BP-24](24_GroupMeasures.md)).

---

## 4. Règle(s) d'évaluation

L'évaluation porte sur trois axes indépendants, chacun contribuant au verdict global.

| Situation détectée | Statut | Interprétation |
|---|---|---|
| La position moyenne (`y` ou `x`, selon l'axe d'organisation dominant) des tables de dimension/paramètres est clairement distincte de celle des tables de faits, avec un ordre cohérent (dimensions groupées d'un côté, faits de l'autre) | `OK` | Séparation dimension/fait respectée. |
| Les tables de dimension et de faits sont mélangées sans séparation identifiable (positions entrelacées sans regroupement visible) | `KO` | Absence d'organisation en clusters lisibles. |
| Deux tables liées par une relation (`relationships.tmdl`) sont positionnées à une distance disproportionnée par rapport aux autres tables du diagramme (table isolée loin de ses relations) | `WARN` | La lisibilité de la relation concernée est dégradée sans invalider toute l'organisation. |
| Chevauchement de zones entre deux tables (rectangles définis par `location` + `size` qui s'intersectent) | `KO` | Chevauchement visuel direct, symptôme de désorganisation. |
| Le fichier `diagramLayout.json` est absent, vide, ou ne contient aucun diagramme avec des nœuds | `NA` | La disposition n'a jamais été personnalisée (position par défaut de Power BI Desktop), la conformité ne peut pas être évaluée. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lire `<SEMANTIC_MODEL_PATH>\diagramLayout.json`.
2. Si le fichier est absent ou si `diagrams` est vide, retourner `NA`.
3. Charger tous les fichiers `tables\*.tmdl` pour classer chaque table par rôle.
4. Charger `relationships.tmdl` pour connaître les paires de tables reliées.

### Étape 2 — Construire l'inventaire géométrique
Pour chaque diagramme de `diagrams` : pour chaque `node`, associer `nodeIndex` (nom de table), sa position `(x, y)`, sa taille `(width, height)` et son rôle (fait / dimension / paramètre).

### Étape 3 — Évaluer la séparation par rôle
Calculer la position moyenne (et l'étendue min/max) des tables de faits d'une part, des tables de dimension/paramètres d'autre part, sur l'axe jugé dominant (celui qui présente la plus grande variance entre les deux groupes). Vérifier que les intervalles ne se chevauchent pas de façon significative.

### Étape 4 — Détecter les chevauchements géométriques
Pour chaque paire de tables, calculer si leurs rectangles (`location`, `size`) s'intersectent. Répéter pour toutes les paires, sans s'arrêter à la première intersection trouvée.

### Étape 5 — Détecter les tables isolées par rapport à leurs relations
Pour chaque relation du modèle, calculer la distance euclidienne entre les centres des deux tables liées. Comparer cette distance à la distance moyenne observée sur l'ensemble des relations du diagramme ; signaler les valeurs très supérieures à la moyenne (ex. > 3x l'écart-type).

### Étape 6 — Terminer l'analyse
Parcourir la totalité des tables et relations avant de conclure. Produire la liste des chevauchements détectés, la liste des relations avec table isolée, et le résultat de la séparation par rôle.

---

## 6. Détection robuste / normalisation

- Les coordonnées sont exprimées dans un repère propre au diagramme, sans origine ni échelle garanties d'un modèle à l'autre : toute analyse doit être **relative** (comparaison de positions entre tables du même diagramme), jamais fondée sur des valeurs absolues fixes.
- Un modèle peut contenir plusieurs diagrammes nommés (`diagrams` est un tableau) : l'agent doit évaluer chaque diagramme séparément et peut se concentrer prioritairement sur celui désigné par `selectedDiagram`/`defaultDiagram`, tout en signalant les autres diagrammes s'ils existent.
- Certaines tables du modèle TMDL peuvent être absentes du diagramme (jamais glissées dans la vue relations) : elles doivent être signalées séparément, sans faire échouer l'évaluation des tables présentes.
- La classification du rôle d'une table doit s'appuyer en priorité sur le préfixe de nommage (`F_`, `D_`, `P_`, `T_`) lorsque la convention du projet est cohérente, avec une vérification croisée par la structure des relations (une table de faits est presque toujours du côté « plusieurs » d'une relation un-à-plusieurs).
- Le calcul de chevauchement entre deux rectangles doit utiliser une comparaison de type AABB (axis-aligned bounding box) :

```python
def rectangles_overlap(node_a, node_b):
    ax1, ay1 = node_a["location"]["x"], node_a["location"]["y"]
    ax2, ay2 = ax1 + node_a["size"]["width"], ay1 + node_a["size"]["height"]
    bx1, by1 = node_b["location"]["x"], node_b["location"]["y"]
    bx2, by2 = bx1 + node_b["size"]["width"], by1 + node_b["size"]["height"]
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1
```

---

## 7. Pseudo-code détaillé

```python
def classify_table_role(table_name, relationships):
    if table_name.startswith("F_"):
        return "fact"
    if table_name.startswith("D_"):
        return "dimension"
    if table_name.startswith(("P_", "T_")) or table_name == "MEASURE":
        return "parameter_support"
    # secours structurel : côté "plusieurs" majoritaire -> fait
    many_side_count = sum(1 for r in relationships if r.to_table == table_name and r.cardinality == "many")
    return "fact" if many_side_count >= 2 else "dimension"


def analyze_diagram_layout(diagram_layout_file, table_files, relationships_file):
    layout = load_json(diagram_layout_file)
    if not layout or not layout.get("diagrams"):
        return {"rule_status": "NA", "reason": "Aucun diagramme personnalisé trouvé"}

    relationships = parse_relationships(relationships_file)
    all_tables = {t.name for t in (parse_tmdl_table(f) for f in table_files)}

    diagram = select_primary_diagram(layout)
    nodes = diagram["nodes"]
    node_by_table = {n["nodeIndex"]: n for n in nodes}

    missing_tables = all_tables - set(node_by_table.keys())

    for node in nodes:
        node["role"] = classify_table_role(node["nodeIndex"], relationships)

    overlaps = []
    for i, node_a in enumerate(nodes):
        for node_b in nodes[i + 1:]:
            if rectangles_overlap(node_a, node_b):
                overlaps.append((node_a["nodeIndex"], node_b["nodeIndex"]))

    fact_nodes = [n for n in nodes if n["role"] == "fact"]
    other_nodes = [n for n in nodes if n["role"] != "fact"]
    separation_ok = evaluate_role_separation(fact_nodes, other_nodes)

    isolated_relations = []
    distances = [euclidean_distance(node_by_table[r.from_table], node_by_table[r.to_table])
                 for r in relationships
                 if r.from_table in node_by_table and r.to_table in node_by_table]
    if distances:
        mean_d, std_d = mean(distances), stdev(distances) if len(distances) > 1 else 0
        for r in relationships:
            if r.from_table not in node_by_table or r.to_table not in node_by_table:
                continue
            d = euclidean_distance(node_by_table[r.from_table], node_by_table[r.to_table])
            if std_d > 0 and d > mean_d + 3 * std_d:
                isolated_relations.append({"from": r.from_table, "to": r.to_table, "distance": d})

    return {
        "overlaps": overlaps,
        "separation_ok": separation_ok,
        "isolated_relations": isolated_relations,
        "missing_tables": sorted(missing_tables),
    }
```

---

## 8. Calcul du statut global

```python
if overlaps or not separation_ok:
    rule_status = "KO"
elif isolated_relations or missing_tables:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > OK`, avec `NA` en cas d'absence totale de diagramme personnalisé.

| Résultat de l'analyse | Statut global |
|---|---|
| Aucun chevauchement, séparation fait/dimension nette | `OK` |
| Au moins un chevauchement de tables ou aucune séparation identifiable | `KO` |
| Pas de chevauchement ni de problème de séparation, mais relation(s) isolée(s) ou table(s) absente(s) du diagramme | `WARN` |
| Aucun diagramme personnalisé dans `diagramLayout.json` | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-27",
  "rule_name": "Disposition organisée du diagramme du modèle",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "diagram_name": "Toutes les tables",
  "total_tables_in_model": 15,
  "total_tables_in_diagram": 15,
  "overlaps": [],
  "isolated_relations": [],
  "missing_tables": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-27",
  "rule_name": "Disposition organisée du diagramme du modèle",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "diagram_name": "Toutes les tables",
  "total_tables_in_model": 15,
  "total_tables_in_diagram": 15,
  "overlaps": [["F_RESPONSES", "D_USERS"]],
  "isolated_relations": [],
  "missing_tables": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-27 — Disposition organisée du diagramme du modèle : OK

Les 15 tables du modèle sont présentes dans le diagramme "Toutes les tables".
Les tables de faits (F_RESPONSES, F_ADOPTION_QUESTION) sont regroupées
distinctement des tables de dimension et de paramètres (D_USERS, D_CAMPAIGNS,
P_EVOLUTION_*, MEASURE). Aucun chevauchement ni relation isolée détecté.
```

### Exemple `KO`

```text
BP-27 — Disposition organisée du diagramme du modèle : KO

Chevauchement détecté entre F_RESPONSES et D_USERS : les rectangles des deux
tables se superposent dans le diagramme "Toutes les tables", ce qui rend la
lecture des relations difficile à cet endroit.

Correction attendue :
dans Power BI Desktop, ouvrir la vue des relations et déplacer D_USERS pour
supprimer le chevauchement avec F_RESPONSES, en conservant le regroupement
des tables de dimension côté droit/haut du diagramme.
```

---

## 11. Conditions empêchant un faux OK

- `diagramLayout.json` a été localisé et son contenu correctement interprété ;
- toutes les tables du modèle TMDL ont été confrontées à la liste des nœuds du diagramme (aucune table manquante non signalée) ;
- le rôle (fait / dimension / paramètre) de chaque table a été déterminé avant d'évaluer la séparation ;
- toutes les paires de tables ont été testées pour un éventuel chevauchement, pas seulement les paires adjacentes dans la liste ;
- toutes les relations du modèle ont été confrontées à la distance géométrique entre les tables concernées ;
- le diagramme évalué est bien celui utilisé par défaut (`defaultDiagram`) lorsque plusieurs diagrammes existent.

---

## 12. Résumé de la règle

```text
RÈGLE BP-27

SI diagramLayout.json absent ou sans diagramme
    règle = NA
SINON
    POUR chaque table du diagramme
        DÉTERMINER son rôle (fait / dimension / paramètre)
    FIN POUR

    VÉRIFIER la séparation géométrique entre tables de faits et
             tables de dimension/paramètres

    POUR chaque paire de tables
        SI chevauchement de rectangles -> KO
    FIN POUR

    POUR chaque relation du modèle
        SI distance entre les deux tables très supérieure à la moyenne -> WARN
    FIN POUR

    SI table du modèle absente du diagramme -> WARN

    SI chevauchement OU séparation non respectée
        règle = KO
    SINON SI relation isolée OU table manquante
        règle = WARN
    SINON
        règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-27 — Disposition organisée du diagramme du modèle │
└────────────────────────┬───────────────────────────────────────┘
                          ▼
           ┌───────────────────────────────────┐
           │ Lire diagramLayout.json              │
           └───────────────────┬─────────────────┘
                  ┌──────────────┴──────────────┐
                  ▼                              ▼
            ╔═════════════╗                ┌───────────────────┐
            ║ diagrams     ║                │ Fichier absent /   │
            ║ présent ✅   ║                │ diagrams vide ❌    │
            ╚══════╤═══════╝                └─────────┬──────────┘
                   │                                   ▼
                   │                           ┌────────────────┐
                   │                           │ Retour : NA     │
                   │                           └────────────────┘
                   ▼
        ┌───────────────────────────────────────────┐
        │ Charger tables\*.tmdl + relationships.tmdl   │
        │ Sélectionner le diagramme principal          │
        │ CLASSER chaque table : fait / dimension /     │
        │ paramètre-support (préfixe puis relations)    │
        └───────────────────┬─────────────────────────────┘
                            ▼
        ┌───────────────────────────────────────────┐
        │ POUR chaque paire de tables (nodes)         │
        │ (boucle sur toutes les paires)               │
        └───────────────────┬─────────────────────────┘
                            ▼
              ┌──────────────────────────────┐
              │ Rectangles (location+size)    │
              │ se chevauchent (AABB) ?        │
              └───────────────┬────────────────┘
             ┌──────────────────┴──────────────────┐
             ▼                                      ▼
       ╔═════════╗                             ┌────────────┐
       ║ OUI ❌  ║                             │ NON        │
       ╚════╤════╝                             └────────────┘
            ▼
    ┌────────────────────┐
    │ AJOUTER overlap      │
    └────────────────────┘
                            │ (après la boucle des paires)
                            ▼
        ┌───────────────────────────────────────────┐
        │ VÉRIFIER la séparation géométrique           │
        │ tables de faits vs dimension/paramètres       │
        └───────────────────┬─────────────────────────────┘
                            ▼
        ┌───────────────────────────────────────────┐
        │ POUR chaque relation du modèle               │
        │ Distance(centre A, centre B) très >          │
        │ moyenne + 3×écart-type ?                      │
        └───────────────────┬─────────────────────────────┘
             ┌──────────────────┴──────────────────┐
             ▼                                      ▼
       ╔═════════╗                             ┌────────────┐
       ║ OUI ⚠️  ║                             │ NON        │
       ╚════╤════╝                             └────────────┘
            ▼
    ┌────────────────────┐
    │ AJOUTER relation      │
    │ isolée (WARN)          │
    └────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────────┐
        │ Table du modèle absente du diagramme ?       │
        │ -> AJOUTER table manquante (WARN)             │
        └───────────────────┬─────────────────────────────┘
                            ▼
     ┌──────────────────────────────────────┐
     │ CALCUL DU STATUT GLOBAL                │
     │ Chevauchement OU séparation non        │
     │ respectée ?        -> règle = KO       │
     │ Sinon relation isolée OU table          │
     │ manquante ?        -> règle = WARN     │
     │ Sinon              -> règle = OK       │
     └────────────────────┬─────────────────────┘
                          ▼
                RETOUR rule_status
                (OK / KO / WARN / NA)
```
