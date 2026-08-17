# BP-32 — Préférence pour les mesures explicites (absence d'agrégation implicite)

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier qu'aucun visuel du rapport Power BI n'utilise une colonne numérique glissée directement dans une zone de valeurs avec agrégation automatique (l'icône Σ, dite « mesure implicite »), mais s'appuie systématiquement sur des mesures DAX explicites (`measure X = ...`). Une agrégation implicite masque le mode de calcul réel derrière un choix par défaut (souvent `Sum`) que l'auteur du visuel n'a pas nécessairement choisi consciemment, empêche toute réutilisation cohérente du même calcul dans d'autres visuels, et rend le modèle plus difficile à faire évoluer : si la colonne source change de type ou de granularité, toutes les agrégations implicites qui en dépendent doivent être revérifiées une par une, alors qu'une mesure explicite centralise la logique en un seul endroit.

Cette règle est le pendant, côté rapport, de [BP-22](22_DisableSummarization.md) (désactivation de `summarizeBy` côté modèle sémantique) : une colonne dont `summarizeBy` est correctement positionné à `none` ne peut techniquement plus être agrégée implicitement dans un nouveau visuel, mais des visuels existants créés avant ce réglage, ou important une colonne dont `summarizeBy` n'a pas encore été corrigé, peuvent encore contenir une référence d'agrégation implicite : BP-32 détecte ces cas résiduels directement dans les fichiers du rapport.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et de visuels ;
- du type de visuel (carte, tableau, graphique, slicer...) ;
- du nom des tables et des colonnes référencées.

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.Report\definition\pages\13e9e9fd2ae0e0e76591\visuals\680df9884e2991194178\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\58f1021603e406d600b2\visuals\025ffdc871d7265d28e3\visual.json
```

L'agent doit parcourir l'intégralité de l'arborescence `pages\*\visuals\*\visual.json` du rapport, chaque fichier décrivant un visuel indépendant avec ses propres projections de champs.

---

## 3. Élément(s) / propriété(s) à contrôler

Dans le bloc `query.queryState.<ZoneVisuel>.projections` de chaque `visual.json`, chaque projection porte un champ `field` qui distingue explicitement une référence à une **mesure** d'une référence à une **colonne**.

Exemple réel de référence à une **mesure explicite** (`Filters_Reminder_en`, conforme) :

```json
"projections": [
  {
    "field": {
      "Measure": {
        "Expression": { "SourceRef": { "Entity": "MEASURE" } },
        "Property": "Filters_Reminder_en"
      }
    },
    "queryRef": "MEASURE.Filters_Reminder_en"
  }
]
```

Exemple réel de référence à une **colonne** dans un slicer (cas légitime : les slicers/axes affichent des valeurs de colonne, pas des agrégations) :

```json
"projections": [
  {
    "field": {
      "Column": {
        "Expression": { "SourceRef": { "Entity": "D_USERS" } },
        "Property": "USER_JOB"
      }
    },
    "queryRef": "D_USERS.USER_JOB",
    "nativeQueryRef": "USER_JOB"
  }
]
```

Le cas problématique visé par cette règle est une référence `"Column"` placée dans une zone de **valeurs agrégées** (`Values`, `Y`, `Data` selon le type de visuel) et accompagnée d'une propriété d'agrégation implicite, généralement représentée par un nœud `Aggregation` enveloppant la colonne dans le champ (par exemple `{"Aggregation": {"Expression": {"Column": {...}}, "Function": 0}}` pour une somme) :

```json
"projections": [
  {
    "field": {
      "Aggregation": {
        "Expression": {
          "Column": {
            "Expression": { "SourceRef": { "Entity": "F_RESPONSES" } },
            "Property": "TESTED_KNOWLEDGE_SCORE"
          }
        },
        "Function": 0
      }
    },
    "queryRef": "Sum(F_RESPONSES.TESTED_KNOWLEDGE_SCORE)"
  }
]
```

Ce dernier motif — un nœud `"Aggregation"` enveloppant un `"Column"` — est la signature technique univoque d'une agrégation implicite créée par glisser-déposer d'une colonne numérique dans une zone de valeurs.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Champ en zone de valeurs (`Values`/`Y`/`Data`) référencé via `"Measure"` | `OK` | Mesure explicite, conforme à la bonne pratique. |
| Champ en zone de catégorie/axe/légende/slicer (`Category`, `Series`, `Rows`, `Values` d'un slicer) référencé via `"Column"` sans nœud `"Aggregation"` | `OK` | Usage attendu d'une colonne pour classer/filtrer, pas pour agréger. |
| Champ en zone de valeurs référencé via `"Aggregation"` enveloppant un `"Column"` | `KO` | Agrégation implicite détectée : une mesure explicite devrait être utilisée à la place. |
| Champ en zone de valeurs référencé via `"Column"` seul, sans `"Aggregation"` mais dans une zone qui impose techniquement une agrégation (visuel de type carte, jauge) | `KO` | Power BI appliquera une agrégation implicite par défaut même sans nœud explicite visible dans ce format d'export ; à traiter comme une agrégation implicite. |
| `visual.json` ne comporte aucune projection exploitable (visuel de type image, bouton, forme, zone de texte) | `NA` | Hors périmètre, aucun champ de données agrégé. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister toutes les pages sous `<REPORT_PATH>\definition\pages\`.
2. Pour chaque page, lister tous les fichiers `visuals\*\visual.json`.
3. Si aucune page ou aucun visuel n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Identifier les zones de valeurs agrégées de chaque visuel
Pour chaque `visual.json`, déterminer, à partir du `visualType` (`barChart`, `card`, `table`, `slicer`...), quelles clés de `queryState` correspondent à des zones d'agrégation (`Values`, `Y`, `Data`) par opposition aux zones de catégorisation (`Category`, `Series`, `Rows` d'un tableau, valeurs d'un slicer).

### Étape 3 — Inspecter chaque projection
Pour chaque projection de chaque zone de valeurs : déterminer si le champ `field` est de type `"Measure"` ou contient un nœud `"Aggregation"` enveloppant un `"Column"`, ou un `"Column"` nu placé dans une zone qui impose une agrégation.

### Étape 4 — Classer chaque projection
Appliquer la logique de la section 4. Ne pas s'arrêter au premier visuel non conforme : parcourir la totalité des pages et des visuels.

### Étape 5 — Terminer l'analyse
Produire le nombre total de projections en zone de valeurs analysées, le nombre conforme (`OK`), le nombre non conforme (`KO`) avec le détail (page, visuel, table, colonne, fonction d'agrégation détectée), et le nombre `NA`.

---

## 6. Détection robuste / normalisation

- Le nom exact des clés de `queryState` varie selon le type de visuel (`Values` pour un graphique en barres, `Y` pour un nuage de points, `Data` pour une carte/carte multiple, `Values` pour un tableau) : l'agent doit maintenir une table de correspondance `visualType -> zones d'agrégation` plutôt que de supposer un nom de clé unique.
- La fonction d'agrégation (`"Function": 0` pour Somme, `1` pour Moyenne, etc.) n'a pas besoin d'être décodée précisément pour cette règle : la seule présence du nœud `"Aggregation"` enveloppant un `"Column"` suffit à qualifier le cas de non-conformité, quelle que soit la fonction choisie.
- Un même visuel peut combiner plusieurs projections dans une même zone (ex. plusieurs mesures en `Values` d'un tableau) : chaque projection doit être évaluée indépendamment, pas seulement la première.
- La distinction entre zone de catégorisation et zone de valeurs doit être faite avant d'évaluer une projection : un `"Column"` en `Category` d'un graphique en barres est parfaitement légitime et ne doit jamais être signalé.
- Les visuels sans bloc `query` exploitable (images, formes, zones de texte, boutons de navigation) doivent être ignorés proprement, sans erreur de parsing bloquante.

```python
AGGREGATION_ZONES_BY_VISUAL_TYPE = {
    "barChart": {"Y"}, "columnChart": {"Y"}, "lineChart": {"Y"},
    "clusteredBarChart": {"Y"}, "clusteredColumnChart": {"Y"},
    "card": {"Values"}, "multiRowCard": {"Values"},
    "tableEx": {"Values"}, "pivotTable": {"Values"},
    "pieChart": {"Values"}, "donutChart": {"Values"},
    "gauge": {"Values"},
}

def is_implicit_aggregation(field_node):
    if "Aggregation" in field_node and "Column" in field_node["Aggregation"].get("Expression", {}):
        return True
    return False

def is_measure_reference(field_node):
    return "Measure" in field_node
```

---

## 7. Pseudo-code détaillé

```python
def analyze_explicit_measures(report_pages_path):
    ok_items, ko_items, na_items = [], [], []

    visual_files = find_all_visual_json(report_pages_path)
    if not visual_files:
        return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
                "reason": "Aucun visuel trouvé dans le rapport"}

    for visual_file in visual_files:
        visual = load_json(visual_file)
        visual_type = visual.get("visual", {}).get("visualType")
        query_state = visual.get("visual", {}).get("query", {}).get("queryState", {})

        if not query_state:
            na_items.append({"file": visual_file, "status": "NA",
                              "reason": "Aucune projection de données (visuel non-données)"})
            continue

        aggregation_zones = AGGREGATION_ZONES_BY_VISUAL_TYPE.get(visual_type, set(query_state.keys()))

        for zone_name, zone_content in query_state.items():
            is_value_zone = zone_name in aggregation_zones
            for projection in zone_content.get("projections", []):
                field = projection.get("field", {})

                if is_measure_reference(field):
                    if is_value_zone:
                        ok_items.append({
                            "file": visual_file, "zone": zone_name,
                            "queryRef": projection.get("queryRef"), "status": "OK",
                        })
                    continue

                if "Column" in field:
                    if is_value_zone:
                        ko_items.append({
                            "file": visual_file, "zone": zone_name,
                            "queryRef": projection.get("queryRef"), "status": "KO",
                            "reason": "Colonne en zone de valeurs sans mesure explicite",
                        })
                    continue

                if is_implicit_aggregation(field):
                    ko_items.append({
                        "file": visual_file, "zone": zone_name,
                        "queryRef": projection.get("queryRef"), "status": "KO",
                        "reason": "Agrégation implicite (Aggregation sur Column)",
                    })

    return ok_items, ko_items, na_items
```

---

## 8. Calcul du statut global

```python
if ko_items:
    rule_status = "KO"
elif not ok_items and not na_items:
    rule_status = "NON_EVALUE"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > OK`. Un seul visuel utilisant une agrégation implicite en zone de valeurs suffit à faire basculer la règle en `KO`, quel que soit le nombre total de visuels conformes.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les projections en zone de valeurs référencent une mesure explicite | `OK` |
| Au moins une projection en zone de valeurs référence une colonne avec agrégation implicite | `KO` |
| Aucun visuel avec projection de données dans tout le rapport | `NON_EVALUE` |

---

## 9. Structure du résultat

Exemple `OK` (état actuel du projet audité — aucun nœud `"Aggregation"` détecté dans les visuels du rapport) :

```json
{
  "rule_id": "BP-32",
  "rule_name": "Préférence pour les mesures explicites",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_visuals_analyzed": 47,
  "value_zone_projections_analyzed": 63,
  "ok_details_count": 63,
  "ko_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-32",
  "rule_name": "Préférence pour les mesures explicites",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_visuals_analyzed": 47,
  "value_zone_projections_analyzed": 64,
  "ko_details": [
    {
      "file": "pages/58f1021603e406d600b2/visuals/9a1c2f0e5b7d/visual.json",
      "zone": "Values",
      "queryRef": "Sum(F_RESPONSES.TESTED_KNOWLEDGE_SCORE)",
      "reason": "Agrégation implicite (Aggregation sur Column)"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-32 — Préférence pour les mesures explicites : OK

47 visuels analysés, 63 projections en zone de valeurs, toutes référencées
via des mesures explicites de la table MEASURE (ex. MEASURE.Filters_Reminder_en,
MEASURE.pct_RespondentsPerUsage). Aucune agrégation implicite détectée.
```

### Exemple `KO`

```text
BP-32 — Préférence pour les mesures explicites : KO

Agrégation implicite détectée :
- pages/58f1021603e406d600b2/visuals/9a1c2f0e5b7d/visual.json (zone Values) :
  la colonne F_RESPONSES[TESTED_KNOWLEDGE_SCORE] est agrégée automatiquement
  (Sum) directement dans le visuel, sans passer par une mesure explicite.

Correction attendue :
créer une mesure explicite dans la table MEASURE, par exemple
Total_Tested_Knowledge_Score = SUM(F_RESPONSES[TESTED_KNOWLEDGE_SCORE]),
puis remplacer la référence à la colonne par cette mesure dans le visuel
concerné.
```

---

## 11. Conditions empêchant un faux OK

- toutes les pages et tous les visuels du rapport ont été parcourus ;
- pour chaque visuel, les zones d'agrégation ont été correctement identifiées à partir de son `visualType`, sans supposer un nom de clé unique valable pour tous les types ;
- chaque projection de chaque zone de valeurs a été inspectée individuellement, y compris lorsque plusieurs projections coexistent dans la même zone ;
- la distinction entre `"Measure"`, `"Column"` nu et `"Aggregation"` enveloppant un `"Column"` a été appliquée systématiquement ;
- les colonnes légitimement utilisées en zone de catégorisation (axes, légendes, slicers) n'ont jamais été signalées à tort ;
- aucun visuel n'a été omis, y compris ceux situés dans des pages secondaires ou des bookmarks.

---

## 12. Résumé de la règle

```text
RÈGLE BP-32

POUR chaque page du rapport
    POUR chaque visuel de la page
        DÉTERMINER les zones d'agrégation selon le visualType

        POUR chaque zone de queryState
            POUR chaque projection de la zone
                SI field contient "Measure"
                    SI zone de valeurs -> projection = OK
                SINON SI field contient "Column" nu
                    SI zone de valeurs -> projection = KO (colonne sans mesure)
                    SINON -> hors périmètre (catégorisation légitime)
                SINON SI field contient "Aggregation" sur "Column"
                    projection = KO (agrégation implicite)
                ENREGISTRER le résultat
            FIN POUR
        FIN POUR
    FIN POUR
FIN POUR

SI au moins une projection KO
    règle = KO
SINON
    règle = OK
```
