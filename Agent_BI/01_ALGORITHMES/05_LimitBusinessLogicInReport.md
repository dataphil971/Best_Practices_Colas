# BP-05 — Limiter la logique métier complexe dans les mesures DAX du rapport

## 1. Objectif de la bonne pratique

Une mesure DAX doit rester un calcul d'agrégation ou de mise en forme, pas un moteur de règles métier. Lorsqu'une logique conditionnelle profonde (`IF`/`SWITCH` imbriqués sur plusieurs niveaux), des motifs de contexte de ligne avancés (`EARLIER`, `EARLIEST`), ou des schémas récursifs sont implémentés directement dans une mesure du modèle sémantique, plusieurs risques apparaissent : la logique devient **difficile à tester et à maintenir** (elle n'est plus visible ni versionnée au même endroit que le reste de la chaîne de transformation), elle est **recalculée à chaque interaction du rapport** au lieu d'être calculée une fois en ETL, et elle **dégrade les performances** du moteur de requête (le nombre de contextes de filtre évalués croît avec la profondeur d'imbrication). Une règle métier complexe et stable dans le temps a naturellement sa place en amont — dans l'ETL, une vue SQL, un dataflow ou une colonne calculée en Power Query — et non dans une mesure recalculée à la volée.

L'objectif de cette règle est de **mesurer objectivement la complexité de chaque mesure DAX** du modèle (profondeur d'imbrication des conditions, nombre de fonctions avancées utilisées, présence de motifs de contexte de ligne coûteux) et de comparer cette complexité à un seuil déterministe, afin d'identifier les mesures qui devraient être simplifiées ou dont la logique devrait être poussée en amont (cf. [BP-04](04_PushTransformUpstream.md), qui traite du même principe côté Power Query).

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de mesures du modèle ;
- du nom des tables et des mesures ;
- de la présence ou non d'un `displayFolder` ou d'une documentation `///` ;
- du style de formatage DAX utilisé (indentation, sauts de ligne, casse des mots-clés).

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Dans ce projet, les mesures DAX sont centralisées dans une table dédiée :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
```

mais certaines mesures peuvent également être définies directement dans des tables de faits ou de dimension. L'agent doit donc parcourir **tous** les fichiers `tables/*.tmdl` et extraire tous les blocs `measure`, indépendamment de la table qui les héberge.

---

## 3. Élément(s) / propriété(s) à contrôler

Chaque mesure est un bloc `measure <nom> = <expression DAX>` dans un fichier de table. Le corps de l'expression est soit sur une seule ligne, soit encadré par des triples backticks pour les expressions multi-lignes :

```tmdl
measure country_reminder = ```

		VAR nbSelectedCountry = DISTINCTCOUNT(D_USERS[USER_COUNTRY])
		VAR CountryConcat = CONCATENATEX(VALUES(D_USERS[USER_COUNTRY]), D_USERS[USER_COUNTRY], ", ")
		VAR AreaConcat = CONCATENATEX(VALUES(D_USERS[USER_AREA]), D_USERS[USER_AREA], ", ")
		VAR result =
		    IF(
		        ISFILTERED(D_USERS[USER_COUNTRY]),
		        IF(
		            nbSelectedCountry > 2,
		            "Multiple",
		            CountryConcat
		        ),
		        "ALL"
		    )
		RETURN result
		```
	displayFolder: FILTERS\REMINDER
	lineageTag: 198a5b7d-eff6-420e-b98e-611679f588e9
```

L'agent doit exclusivement analyser le **corps de l'expression DAX** (entre les backticks, ou après le `=` pour une mesure sur une seule ligne comme `measure Nb_Responses = COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN])`). Les propriétés `displayFolder`, `formatString`, `lineageTag` et les annotations ne participent jamais au calcul de complexité.

---

## 4. Règle(s) d'évaluation

La complexité d'une mesure est mesurée par trois indicateurs indépendants (détaillés en section 6) : la **profondeur maximale d'imbrication** des `IF`/`SWITCH`, le **nombre d'occurrences** de fonctions de contexte avancées (`EARLIER`, `EARLIEST`), et la **présence d'un appel récursif** (une mesure qui se référence elle-même, directement ou via une chaîne d'autres mesures).

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `Nb_Responses = COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN])`, profondeur 0, aucune fonction avancée | `OK` | Mesure d'agrégation simple, complexité minimale. |
| `Response_Rate = DIVIDE([Nb_Responses],[Sample_Total_Size])`, profondeur 0 | `OK` | Composition de mesures simples, pas de logique conditionnelle. |
| `country_reminder`, deux `IF` imbriqués (profondeur 2), aucun `EARLIER` | `OK` | Sous le seuil de tolérance (profondeur ≤ 2, aucune fonction avancée). |
| `NOTIF_Banner_Main`, `IF` imbriqués à 4 niveaux au sein d'une construction de chaîne SVG | `WARN` | Complexité élevée mais motivée par un besoin de mise en forme visuelle plutôt que par une règle métier ; à documenter et surveiller. |
| Mesure hypothétique `Eligibility_Score` combinant `SWITCH` imbriqué sur 5 niveaux avec des seuils métier codés en dur | `KO` | Logique métier complexe et opaque directement dans le rapport ; dépasse le seuil de complexité. |
| Mesure hypothétique `Cumulative_Rank` utilisant `EARLIER` pour calculer un rang par ligne | `KO` | Motif de contexte de ligne avancé, coûteux et difficile à maintenir ; alternative recommandée (`RANKX`, colonne calculée en amont). |
| Mesure hypothétique `Recursive_Chain` qui référence directement ou indirectement sa propre définition | `KO` | Récursion détectée : risque de calcul instable et de dépendance circulaire. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables/*.tmdl`.
2. Extraire tous les blocs `measure`, quelle que soit la table hôte.
3. Si aucune mesure n'est trouvée dans l'ensemble du modèle, retourner `NON_EVALUE`.

### Étape 2 — Extraire le corps DAX de chaque mesure
Pour chaque mesure : isoler le corps de l'expression (dépouiller les triples backticks le cas échéant) ; conserver la référence à la mesure d'origine (table, nom, `displayFolder`).

### Étape 3 — Calculer les indicateurs de complexité
Pour chaque mesure : calculer la profondeur d'imbrication `IF`/`SWITCH` ; compter les occurrences de fonctions avancées (`EARLIER`, `EARLIEST`) ; détecter une éventuelle référence circulaire en résolvant le graphe de dépendances entre mesures (une mesure peut référencer une autre mesure via `[NomMesure]`).

### Étape 4 — Appliquer la grille de décision
Comparer les indicateurs aux seuils définis (section 6) et classer chaque mesure `OK`, `WARN` ou `KO`.

### Étape 5 — Ne pas s'arrêter à la première mesure complexe
L'agent analyse l'intégralité des mesures du modèle, y compris celles situées dans des tables autres que `MEASURE`.

### Étape 6 — Terminer l'analyse
Produire : le nombre total de mesures analysées ; le nombre de mesures `OK`/`WARN`/`KO` ; la liste des mesures `KO` avec profondeur et fonctions avancées détectées ; la liste des mesures `WARN` avec justification possible (ex. construction de visuel SVG plutôt que règle métier).

---

## 6. Détection robuste / normalisation

**Calcul de la profondeur d'imbrication** — l'agent construit un arbre syntaxique simplifié de l'expression DAX en repérant les appels `IF(` et `SWITCH(` et en associant chaque parenthèse ouvrante à sa parenthèse fermante correspondante (comptage de parenthèses, en ignorant celles contenues dans des chaînes de caractères entre guillemets doubles). La profondeur d'une mesure est la profondeur maximale d'imbrication de `IF`/`SWITCH` les uns dans les autres — un `IF` utilisé comme argument d'un autre `IF` incrémente la profondeur ; un `IF` utilisé en série (non imbriqué) au sein de plusieurs `VAR` indépendantes ne l'incrémente pas.

```python
def compute_nesting_depth(dax_body):
    tokens = tokenize_ignoring_string_literals(dax_body)
    depth = 0
    max_depth = 0
    stack = []
    for token in tokens:
        if token.upper() in {"IF(", "SWITCH("}:
            depth += 1
            stack.append(token)
            max_depth = max(max_depth, depth)
        elif token == ")" and stack:
            stack.pop()
            depth -= 1
    return max_depth
```

**Seuils par défaut** (paramétrables) :

```text
NESTING_DEPTH_WARN_THRESHOLD = 3   # profondeur >= 3 : avertissement
NESTING_DEPTH_KO_THRESHOLD   = 4   # profondeur >= 4 : non conforme, sauf exemption documentée
ADVANCED_FUNCTIONS_KO = {"EARLIER", "EARLIEST"}
```

**Exemption des constructions de mise en forme** — une mesure dont le corps contient majoritairement des littéraux de balisage (`<svg`, `<rect`, `<text`, séquences `data:image/`) est reconnue comme une construction visuelle (icônes, bannières dynamiques) plutôt qu'une règle métier ; ce type de mesure est déclassé de `KO` à `WARN` même au-delà du seuil, car sa complexité est d'ordre présentationnel et non décisionnel — mais reste signalé, car cette pratique reste déconseillée et gagnerait à être déportée dans une image statique ou un visuel dédié.

```python
def looks_like_visual_construction(dax_body):
    markers = ("<svg", "<rect", "<text", "<path", "data:image/svg+xml")
    hits = sum(dax_body.count(m) for m in markers)
    return hits >= 3
```

**Détection de récursion** — l'agent construit le graphe de dépendances entre mesures (une mesure référence une autre via `[NomMesure]`) et détecte tout cycle, y compris indirect (`A` référence `B`, `B` référence `A`).

```python
def has_circular_reference(measure_name, dependency_graph, visited=None, stack=None):
    visited = visited or set()
    stack = stack or set()
    if measure_name in stack:
        return True
    if measure_name in visited:
        return False
    visited.add(measure_name)
    stack.add(measure_name)
    for dep in dependency_graph.get(measure_name, []):
        if has_circular_reference(dep, dependency_graph, visited, stack):
            return True
    stack.discard(measure_name)
    return False
```

**Normalisation du texte DAX** : suppression des commentaires `--` et `/* ... */` avant tokenisation (ils ne doivent jamais être comptés comme code) ; insensibilité à la casse des noms de fonctions DAX (`If(`, `IF(`, `if(` sont équivalents) ; tolérance aux espaces et retours à la ligne multiples entre les tokens.

---

## 7. Pseudo-code détaillé

```python
def extract_measures(table_files):
    measures = []
    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        for m in table.measures:
            measures.append({
                "table": table.name,
                "name": m.name,
                "dax_body": strip_backticks(m.expression),
                "display_folder": m.get_property("displayFolder"),
            })
    return measures


def build_dependency_graph(measures):
    graph = {}
    for m in measures:
        refs = extract_measure_references(m["dax_body"])  # motif [NomMesure]
        graph[m["name"]] = [r for r in refs if r in {x["name"] for x in measures}]
    return graph


def evaluate_measure(measure, dependency_graph):
    body = remove_comments(measure["dax_body"])

    depth = compute_nesting_depth(body)
    advanced_hits = [fn for fn in ADVANCED_FUNCTIONS_KO if contains_function_call(body, fn)]
    is_circular = has_circular_reference(measure["name"], dependency_graph)
    is_visual = looks_like_visual_construction(body)

    if is_circular:
        return {"status": "KO", "reason": "Référence circulaire détectée entre mesures", "depth": depth}

    if advanced_hits:
        return {"status": "KO", "reason": f"Fonctions de contexte de ligne avancées utilisées: {advanced_hits}", "depth": depth}

    if depth >= NESTING_DEPTH_KO_THRESHOLD:
        if is_visual:
            return {"status": "WARN", "reason": f"Profondeur d'imbrication {depth}, mais construction visuelle (SVG) plutôt que règle métier", "depth": depth}
        return {"status": "KO", "reason": f"Profondeur d'imbrication {depth} >= seuil {NESTING_DEPTH_KO_THRESHOLD}", "depth": depth}

    if depth >= NESTING_DEPTH_WARN_THRESHOLD:
        return {"status": "WARN", "reason": f"Profondeur d'imbrication {depth}, à surveiller", "depth": depth}

    return {"status": "OK", "depth": depth}


measures = extract_measures(table_files)
dependency_graph = build_dependency_graph(measures)
results = [
    {**m, **evaluate_measure(m, dependency_graph)}
    for m in measures
]
```

---

## 8. Calcul du statut global

```python
if any(r["status"] == "KO" for r in results):
    rule_status = "KO"
elif any(r["status"] == "WARN" for r in results):
    rule_status = "WARN"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > OK` (`WARN` est une recommandation non bloquante, distincte de `NA`, qui reste réservé aux cas où l'analyse d'une mesure est techniquement impossible, par exemple une expression DAX illisible ou tronquée).

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les mesures sous le seuil `WARN` | `OK` |
| Au moins une mesure `KO` (récursion, fonction avancée, ou profondeur excessive hors exemption visuelle) | `KO` |
| Aucun `KO`, mais au moins une mesure entre les seuils `WARN` et `KO`, ou exemptée en `WARN` | `WARN` |
| Une mesure n'a pas pu être parsée (expression tronquée, backticks non refermés) | `NA` pour cette mesure ; ne bloque pas les autres mesures |

---

## 9. Structure du résultat

Exemple lorsque la bonne pratique est respectée :

```json
{
  "rule_id": "BP-05",
  "rule_name": "Limiter la logique métier complexe dans les mesures DAX du rapport",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_measures": 41,
  "ok_measures": 38,
  "warn_measures": 3,
  "ko_measures": 0,
  "warn_details": [
    {"table": "MEASURE", "measure": "NOTIF_Banner_Main", "depth": 4, "reason": "Construction visuelle SVG (bannière de notification), pas une règle métier"},
    {"table": "MEASURE", "measure": "country_reminder", "depth": 2, "reason": "Sous le seuil KO mais à surveiller"}
  ],
  "ko_details": []
}
```

Exemple avec logique métier complexe détectée :

```json
{
  "rule_id": "BP-05",
  "rule_name": "Limiter la logique métier complexe dans les mesures DAX du rapport",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_measures": 44,
  "ok_measures": 39,
  "warn_measures": 2,
  "ko_measures": 3,
  "ko_details": [
    {"table": "MEASURE", "measure": "Eligibility_Score", "depth": 5, "reason": "Profondeur d'imbrication 5 >= seuil 4, seuils métier codés en dur"},
    {"table": "MEASURE", "measure": "Cumulative_Rank", "depth": 1, "reason": "Fonctions de contexte de ligne avancées utilisées: ['EARLIER']"},
    {"table": "MEASURE", "measure": "Recursive_Chain", "depth": 0, "reason": "Référence circulaire détectée entre mesures"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-05 — Logique métier dans les mesures DAX : OK

41 mesures analysées dans le modèle. Aucune mesure ne dépasse le
seuil de complexité bloquant (imbrication IF/SWITCH >= 4 niveaux,
usage de EARLIER/EARLIEST, ou référence circulaire).

3 mesures signalées en avertissement (profondeur 2 à 4), dont
NOTIF_Banner_Main : complexité liée à la construction d'un visuel
SVG et non à une règle métier — à surveiller mais non bloquant.
```

### Exemple `KO`

```text
BP-05 — Logique métier dans les mesures DAX : KO

39 mesures conformes sur 44 mesures analysées.

Mesures non conformes :
- MEASURE[Eligibility_Score] : 5 niveaux de SWITCH/IF imbriqués avec
  des seuils métier codés en dur dans l'expression DAX.
- MEASURE[Cumulative_Rank] : utilise EARLIER pour calculer un rang
  ligne à ligne, motif coûteux et fragile.
- MEASURE[Recursive_Chain] : référence circulaire détectée dans le
  graphe de dépendances des mesures.

Correction attendue :
déplacer le calcul du score d'éligibilité vers l'ETL ou une colonne
calculée en amont (dataflow / vue SQL) ; remplacer EARLIER par
RANKX ou par une colonne calculée en amont pour Cumulative_Rank ;
casser la dépendance circulaire de Recursive_Chain en isolant la
partie récursive dans une table calculée dédiée si elle est
réellement nécessaire.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- tous les fichiers `tables/*.tmdl` ont été chargés et tous les blocs `measure` ont été extraits, quelle que soit la table hôte ;
- le corps DAX de chaque mesure a été correctement isolé (dépouillement des triples backticks, suppression des commentaires) ;
- la profondeur d'imbrication `IF`/`SWITCH` a été calculée pour chaque mesure ;
- la présence de `EARLIER`/`EARLIEST` a été recherchée dans chaque mesure ;
- le graphe de dépendances entre mesures a été construit et contrôlé pour détecter toute référence circulaire ;
- aucune mesure ne dépasse le seuil `KO` sans exemption visuelle documentée et elle-même signalée en `WARN` ;
- aucune mesure n'a été ignorée faute de parsing réussi sans être comptabilisée en `NA`.

L'agent ne doit jamais produire `OK` en se limitant à l'inspection des mesures de la table `MEASURE` : des mesures définies directement dans des tables de faits ou de dimension doivent être incluses dans l'analyse.

---

## 12. Résumé de la règle

```text
RÈGLE BP-05

POUR chaque table du modèle
    POUR chaque mesure DAX de la table
        EXTRAIRE le corps de l'expression (sans commentaires ni backticks)
        CALCULER la profondeur d'imbrication IF/SWITCH
        RECHERCHER EARLIER / EARLIEST
        AJOUTER au graphe de dépendances (références [NomMesure])

CONSTRUIRE le graphe de dépendances complet
DÉTECTER les cycles (récursion) dans ce graphe

POUR chaque mesure
    SI référence circulaire détectée
        mesure = KO
    SINON SI EARLIER/EARLIEST utilisé
        mesure = KO
    SINON SI profondeur >= seuil KO
        SI construction visuelle (SVG) détectée
            mesure = WARN
        SINON
            mesure = KO
    SINON SI profondeur >= seuil WARN
        mesure = WARN
    SINON
        mesure = OK

    ENREGISTRER le résultat avec preuve
FIN POUR

SI au moins une mesure est KO
    règle = KO
SINON SI au moins une mesure est WARN
    règle = WARN
SINON
    règle = OK

AFFICHER toutes les mesures KO et WARN avec recommandation
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-05 — Logique métier complexe dans les mesures DAX   │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │ Lister tables/*.tmdl          │
          │ EXTRAIRE tous les blocs        │
          │ measure (toutes tables hôtes)  │
          └──────────────┬────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ ≥1 mesure ✅ ║    │ Aucune mesure trouvée ❌│
         ╚════╤════════╝    └──────────┬────────────┘
              │                        ▼
              │                ┌───────────────────┐
              │                │ Retour : NON_EVALUE│
              │                └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ CONSTRUIRE le graphe de dépendances entre    │
   │ mesures (références [NomMesure])             │
   │ DÉTECTER les cycles (récursion)               │
   └──────────────────┬──────────────────────────┘
                       ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque mesure (boucle)                 │
   │ EXTRAIRE le corps DAX (sans backticks/       │
   │ commentaires)                                │
   │ CALCULER profondeur imbrication IF/SWITCH    │
   │ RECHERCHER EARLIER / EARLIEST                │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ Référence circulaire détectée ?      │
        └───────┬──────────────────┬───────────┘
              oui│                  │non
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────────┐
         ║ mesure = KO   ║  │ EARLIER / EARLIEST utilisé ? │
         ╚═══════════════╝  └───────┬──────────────┬────────┘
                                  oui│                │non
                                     ▼                ▼
                          ╔═══════════════╗  ┌────────────────────────┐
                          ║ mesure = KO   ║  │ profondeur ≥ seuil KO (4) ?│
                          ╚═══════════════╝  └──────┬──────────┬────────┘
                                                   oui│           │non
                                                      ▼           ▼
                                    ┌────────────────────────┐  ┌────────────────────────┐
                                    │ Construction visuelle    │  │ profondeur ≥ seuil       │
                                    │ (SVG) détectée ?          │  │ WARN (3) ?               │
                                    └──────┬──────────┬─────────┘  └──────┬──────────┬────────┘
                                        oui│            │non          oui│            │non
                                           ▼            ▼                ▼            ▼
                                ╔═══════════════╗ ╔═══════════════╗ ╔═══════════════╗ ╔═══════════════╗
                                ║ mesure = WARN ║ ║ mesure = KO   ║ ║ mesure = WARN ║ ║ mesure = OK   ║
                                ╚═══════════════╝ ╚═══════════════╝ ╚═══════════════╝ ╚═══════════════╝
                       │
                       ▼ (ENREGISTRER avec preuve, boucle suivante — toutes les
                       │  mesures analysées, y compris hors table MEASURE)
   ┌──────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL (priorité KO > WARN > OK) │
   │ SI au moins une mesure KO      → règle = KO       │
   │ SINON SI au moins une mesure WARN → règle = WARN  │
   │ SINON                            → règle = OK     │
   │ (NA réservé aux mesures illisibles/non parsables,  │
   │  ne bloque pas les autres mesures)                 │
   └───────────────────────┬──────────────────────────┘
                            ▼
                RETOUR rule_status (OK / WARN / KO)
```
