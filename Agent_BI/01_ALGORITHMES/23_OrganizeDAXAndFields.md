# BP-23 — Organisation des mesures et colonnes dans des dossiers d'affichage (displayFolder)

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que les mesures et les colonnes exposées aux utilisateurs finaux dans le volet des champs de Power BI Desktop / Power BI Service sont rangées dans des dossiers d'affichage (`displayFolder` en TMDL), y compris, si nécessaire, des dossiers imbriqués (`Parent\Enfant`). Un modèle comptant plusieurs dizaines de mesures et de colonnes sans aucune organisation logique oblige l'utilisateur à parcourir une liste plate et non structurée, ce qui nuit directement à l'adoption du rapport et augmente le risque d'erreur (mauvais champ sélectionné, doublons apparents non identifiés).

Cette bonne pratique est complémentaire de [BP-24](24_GroupMeasures.md) (qui porte sur le regroupement des mesures dans des tables dédiées) et de [BP-25](25_HideTechnicalFields.md) (qui porte sur le masquage des champs techniques) : une fois les mesures centralisées et les champs techniques masqués, il reste à organiser les champs réellement visibles en catégories métier cohérentes.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables, de mesures et de colonnes ;
- du nom des tables, des mesures et des colonnes ;
- du nombre de niveaux d'imbrication des dossiers (`Dossier\SousDossier\SousSousDossier`) ;
- de l'ordre des propriétés dans les fichiers TMDL ;
- du fait que l'élément soit une mesure ou une colonne.

---

## 2. Emplacement des fichiers concernés

L'agent doit lire l'ensemble des fichiers de tables du modèle sémantique :

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
```

Les mesures et colonnes calculées peuvent se trouver dans n'importe quelle table (y compris une table dédiée comme `MEASURE`, cf. BP-24) : l'agent doit donc parcourir la totalité des fichiers du dossier `tables\`, sans présupposer qu'un seul fichier centralise toutes les mesures.

Aucun fichier du rapport (`<REPORT_PATH>`) n'est nécessaire pour cette règle : l'organisation en dossiers est une propriété du modèle sémantique, pas du rapport.

---

## 3. Élément(s) / propriété(s) à contrôler

Pour chaque bloc `measure` et chaque bloc `column`, l'agent doit rechercher la propriété :

```tmdl
displayFolder: <VALEUR>
```

Exemples réels tirés de `MEASURE.tmdl` :

```tmdl
measure pct_RespondentsPerUsage = ```
        VAR TotalRespondents =
            CALCULATE ( [Respondents_number], REMOVEFILTERS ( F_ADOPTION_QUESTION[USAGE LABEL]) )
        RETURN
            DIVIDE ( [Respondents_number], TotalRespondents )
        ```
    formatString: 0%;-0%;0%
    displayFolder: USAGE
    lineageTag: 320df796-1696-477b-9805-04d792997a70
```

Exemple de dossier imbriqué (deux niveaux, séparateur `\`) :

```tmdl
measure country_reminder = ```
        ...
        ```
    displayFolder: FILTERS\REMINDER
    lineageTag: 198a5b7d-eff6-420e-b98e-611679f588e9
```

Exemple avec trois niveaux d'imbrication :

```tmdl
measure NOTIF_BackgroundColor = ```
        ...
        ```
    isHidden
    displayFolder: NOTIFICATION BANNER\03 - COLOR
    lineageTag: 81583661-af12-46f9-882e-765fc4f662ce
```

Exemple d'une mesure **sans** `displayFolder` (non conforme si la mesure est visible) :

```tmdl
measure Nb_Responses = COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN])
    formatString: 0
    lineageTag: 41157889-d0e7-4d7b-92ff-d870f629f75f
```

La propriété décisive est donc `displayFolder`. La présence ou l'absence de la propriété `isHidden` sur le même bloc conditionne l'interprétation (voir section 4) : un champ masqué n'apparaît jamais dans le volet des champs, son organisation en dossier est donc hors de portée de cette bonne pratique.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Élément visible avec `displayFolder` non vide (ex. `USAGE`, `FILTERS\REMINDER`) | `OK` | L'élément est rangé dans un dossier d'affichage cohérent. |
| Élément visible sans propriété `displayFolder` | `KO` | L'élément apparaît à la racine du volet des champs, sans classement. |
| Élément visible avec `displayFolder` présent mais valeur vide (`displayFolder:` sans valeur, ou `displayFolder: ""`) | `KO` | La propriété est déclarée mais inutilisable. |
| Élément visible avec `displayFolder` mal formé (ex. `\FILTERS`, `FILTERS\`, `FILTERS\\REMINDER`) | `WARN` | Le dossier existe mais un séparateur superflu ou en tête/fin de chaîne peut créer un sous-dossier vide ou dupliqué dans l'IHM. |
| Élément masqué (`isHidden` présent) | `NA` | L'élément n'apparaît pas dans le volet des champs ; son organisation en dossier n'a pas d'impact utilisateur. |
| Colonne technique de la table `MEASURE` créée automatiquement par Power BI (colonne unique `Column` de la table calculée support) | `NA` | Colonne technique interne sans usage métier, hors périmètre de la bonne pratique. |

---

## 5. Parcours complet du modèle

L'agent doit parcourir l'intégralité du modèle sans s'arrêter à la première anomalie.

### Étape 1 — Localiser les tables
1. Accéder à `<SEMANTIC_MODEL_PATH>\definition\tables\`.
2. Récupérer la liste complète des fichiers `*.tmdl`.
3. Si aucun fichier n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Lire chaque table
Pour chaque fichier TMDL : identifier le nom de la table ; recenser tous les blocs `measure` ; recenser tous les blocs `column` ; passer au fichier suivant.

### Étape 3 — Évaluer chaque mesure et chaque colonne
Pour chaque élément détecté : déterminer s'il est masqué (`isHidden`) ; si masqué, classer `NA` et passer à l'élément suivant ; sinon, rechercher `displayFolder` dans le bloc ; appliquer la logique de la section 4 ; enregistrer le résultat avec la valeur brute du dossier détecté.

### Étape 4 — Terminer l'analyse
Une fois toutes les tables parcourues, produire : le nombre total d'éléments visibles analysés ; le nombre d'éléments `OK`, `KO`, `WARN`, `NA` ; la liste complète des éléments `KO` (mesure/colonne, table d'origine) ; la liste complète des éléments `WARN` avec la valeur brute du dossier problématique.

---

## 6. Détection robuste / normalisation

- L'ordre des propriétés (`formatString`, `displayFolder`, `lineageTag`, `isHidden`) varie d'un bloc à l'autre : l'agent doit rechercher `displayFolder` n'importe où dans le bloc `measure`/`column`, pas uniquement sur la ligne suivant `measure <nom> =`.
- Une mesure peut être définie sur une seule ligne (`measure Nb_Responses = COUNT(...)`) ou encadrée par des triples backticks multi-lignes (`` measure X = ``` ... ``` ``) : dans les deux cas, les propriétés (`displayFolder`, `formatString`, etc.) apparaissent **après** la fin de l'expression DAX, qu'elle soit sur une ligne ou encadrée. L'agent doit localiser la fin du bloc d'expression (fermeture des triples backticks, ou fin de ligne si expression simple) avant de chercher les propriétés qui suivent, à l'indentation du bloc.
- La comparaison de la valeur de `displayFolder` doit être insensible à la casse pour détecter les incohérences de nommage (`Usage` vs `USAGE` vs `usage`) qui créeraient deux dossiers distincts dans l'IHM alors qu'un seul était voulu — ce cas est signalé en `WARN`, pas en `KO`, car chaque valeur individuelle reste syntaxiquement valide.
- Les espaces en début/fin de valeur doivent être retirés avant traitement (`strip()`).
- Le séparateur de niveaux est le caractère `\` (backslash) ; l'agent doit tolérer d'éventuels espaces autour de ce séparateur sans les considérer comme une erreur bloquante.
- `isHidden` peut apparaître seul sur sa ligne (propriété booléenne sans valeur explicite) : sa simple présence dans le bloc suffit à qualifier l'élément de masqué.

```python
def normalize_folder(raw_value):
    if raw_value is None:
        return None
    return raw_value.strip()

def is_malformed_folder(value):
    return value.startswith("\\") or value.endswith("\\") or "\\\\" in value
```

---

## 7. Pseudo-code détaillé

```python
def analyze_display_folders(table_files):
    ok_items, ko_items, warn_items, na_items = [], [], [], []
    folder_names_seen = {}  # normalisation casse -> liste des variantes rencontrées

    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        elements = list(table.measures) + list(table.columns)

        for element in elements:
            kind = "measure" if element.block_type == "measure" else "column"
            is_hidden = element.has_flag("isHidden")

            if is_hidden:
                na_items.append({
                    "table": table.name, "name": element.name, "kind": kind,
                    "status": "NA", "reason": "Élément masqué, absent du volet des champs",
                })
                continue

            if table.name == "MEASURE" and kind == "column" and element.name == "Column":
                na_items.append({
                    "table": table.name, "name": element.name, "kind": kind,
                    "status": "NA", "reason": "Colonne technique de la table calculée support",
                })
                continue

            raw_folder = element.get_property("displayFolder")
            folder = normalize_folder(raw_folder)

            if not folder:
                ko_items.append({
                    "table": table.name, "name": element.name, "kind": kind,
                    "status": "KO", "reason": "displayFolder absent ou vide",
                })
                continue

            if is_malformed_folder(folder):
                warn_items.append({
                    "table": table.name, "name": element.name, "kind": kind,
                    "displayFolder": folder, "status": "WARN",
                    "reason": "Séparateur \\ superflu en tête/fin ou dupliqué",
                })
                continue

            key = folder.lower()
            folder_names_seen.setdefault(key, set()).add(folder)

            ok_items.append({
                "table": table.name, "name": element.name, "kind": kind,
                "displayFolder": folder, "status": "OK",
            })

    # Détection de variantes de casse pour un même dossier logique
    for key, variants in folder_names_seen.items():
        if len(variants) > 1:
            warn_items.append({
                "status": "WARN",
                "reason": f"Variantes de casse détectées pour un même dossier logique : {sorted(variants)}",
            })

    return ok_items, ko_items, warn_items, na_items
```

---

## 8. Calcul du statut global

```python
if ko_items:
    rule_status = "KO"
elif warn_items:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > OK`. Les éléments `NA` ne participent jamais au calcul du statut global.

| Résultat de l'analyse | Statut global |
|---|---|
| Tous les éléments visibles ont un `displayFolder` valide | `OK` |
| Au moins un élément visible n'a pas de `displayFolder` | `KO` |
| Aucun `KO`, mais un ou plusieurs `displayFolder` mal formés / incohérents en casse | `WARN` |
| Aucun élément visible dans le modèle (tout est masqué) | `NA`, avec message explicite |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-23",
  "rule_name": "Organisation des mesures et colonnes dans des dossiers d'affichage",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_visible_elements": 42,
  "ok_elements": 42,
  "ko_elements": 0,
  "warn_elements": 0,
  "na_elements": 15,
  "ko_details": [],
  "warn_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-23",
  "rule_name": "Organisation des mesures et colonnes dans des dossiers d'affichage",
  "execution_status": "PARTIAL",
  "rule_status": "KO",
  "total_visible_elements": 42,
  "ok_elements": 39,
  "ko_elements": 2,
  "warn_elements": 1,
  "na_elements": 15,
  "ko_details": [
    {"table": "MEASURE", "name": "Nb_Responses", "kind": "measure", "reason": "displayFolder absent ou vide"},
    {"table": "F_RESPONSES", "name": "WORRY_COLOUR", "kind": "column", "reason": "displayFolder absent ou vide"}
  ],
  "warn_details": [
    {"reason": "Variantes de casse détectées pour un même dossier logique : ['USAGE', 'Usage']"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-23 — Organisation des mesures et colonnes dans des dossiers d'affichage : OK

42 éléments visibles analysés, tous rangés dans un dossier d'affichage cohérent
(USAGE, PERCEPTION, TRAINING, CAMPAIGNS STATS, FILTERS\REMINDER,
NOTIFICATION BANNER\...). 15 éléments masqués sont hors périmètre.
```

### Exemple `KO`

```text
BP-23 — Organisation des mesures et colonnes dans des dossiers d'affichage : KO

39 éléments conformes sur 42 éléments visibles analysés.

Éléments non conformes :
- MEASURE[Nb_Responses] : aucun displayFolder défini, la mesure apparaît à la
  racine du volet des champs.
- F_RESPONSES[WORRY_COLOUR] : aucun displayFolder défini.

Avertissement (non bloquant) :
- Variantes de casse détectées pour un même dossier logique : USAGE / Usage.
  Power BI créera deux dossiers distincts dans le volet des champs.

Correction attendue :
définir la propriété displayFolder sur MEASURE[Nb_Responses] (ex. : CAMPAIGNS
STATS, cohérent avec les autres mesures du même thème) et sur
F_RESPONSES[WORRY_COLOUR], puis harmoniser la casse des valeurs USAGE/Usage.
```

---

## 11. Conditions empêchant un faux OK

- le dossier `tables\` a été localisé et tous les fichiers `.tmdl` ont été lus ;
- chaque bloc `measure` et `column` de chaque table a été identifié, quel que soit le format de l'expression (ligne unique ou triple backticks) ;
- le statut masqué/visible (`isHidden`) a été déterminé pour chaque élément avant de juger la nécessité d'un `displayFolder` ;
- la propriété `displayFolder` a été recherchée dans l'intégralité du bloc, indépendamment de sa position ;
- aucune valeur vide ou absente n'a été comptée par erreur comme conforme ;
- les incohérences de casse entre valeurs de dossier ont été détectées sur l'ensemble du modèle, pas seulement au sein d'une même table ;
- aucun élément visible n'a été omis de l'analyse.

---

## 12. Résumé de la règle

```text
RÈGLE BP-23

POUR chaque table du modèle sémantique
    POUR chaque mesure et chaque colonne de la table
        SI élément masqué (isHidden)
            élément = NA
        SINON
            LIRE displayFolder

            SI displayFolder absent ou vide
                élément = KO
            SINON SI displayFolder mal formé (\ en tête/fin, \\ dupliqué)
                élément = WARN
            SINON
                élément = OK
                MÉMORISER la variante de casse du nom de dossier

        ENREGISTRER le résultat
    FIN POUR
FIN POUR

SI variantes de casse détectées pour un même dossier logique
    AJOUTER un WARN global

SI au moins un élément KO
    règle = KO
SINON SI au moins un WARN
    règle = WARN
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-23 — Organisation des mesures et colonnes en           │
│         dossiers d'affichage (displayFolder)                      │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
                ┌───────────────────────────────────┐
                │ Lister tables\*.tmdl                │
                └──────────────────┬────────────────────┘
                       ┌────────────┴────────────┐
                       ▼                          ▼
                 ╔═════════════╗          ┌───────────────┐
                 ║ Fichiers    ║          │ Aucun fichier  │
                 ║ trouvés ✅  ║          │ trouvé ❌       │
                 ╚══════╤══════╝          └───────┬────────┘
                        │                          ▼
                        │                  ┌────────────────┐
                        │                  │ Retour :        │
                        │                  │ NON_EVALUE      │
                        │                  └────────────────┘
                        ▼
       ┌───────────────────────────────────────────────┐
       │ POUR chaque table                               │
       │   POUR chaque bloc measure / column              │
       │   (boucle sur tous les éléments du modèle)       │
       └───────────────────────┬─────────────────────────┘
                                ▼
                 ┌──────────────────────────┐
                 │ Élément masqué            │
                 │ (isHidden présent) ?      │
                 └──────────────┬──────────────┘
                    ┌────────────┴────────────┐
                    ▼                          ▼
               ╔═════════╗               ┌──────────┐
               ║ OUI     ║               │ NON      │
               ╚════╤════╝               └────┬─────┘
                    ▼                          ▼
            ┌───────────────┐      ┌─────────────────────────────┐
            │ élément = NA   │      │ Colonne technique de support  │
            └───────────────┘      │ (MEASURE[Column]) ?           │
                                    └───────────────┬─────────────────┘
                                        ┌─────────────┴─────────────┐
                                        ▼                           ▼
                                   ╔═════════╗                ┌──────────┐
                                   ║ OUI     ║                │ NON      │
                                   ╚════╤════╝                └────┬─────┘
                                        ▼                          ▼
                                ┌───────────────┐   ┌────────────────────────────┐
                                │ élément = NA   │   │ LIRE displayFolder          │
                                └───────────────┘   └───────────────┬──────────────┘
                                                                     ▼
                                                     ┌────────────────────────────┐
                                                     │ displayFolder absent/vide ?  │
                                                     └───────────────┬──────────────┘
                                                    ┌─────────────────┴─────────────────┐
                                                    ▼                                    ▼
                                              ╔═════════╗                          ┌──────────┐
                                              ║ OUI ❌  ║                          │ NON      │
                                              ╚════╤════╝                          └────┬─────┘
                                                   ▼                                     ▼
                                           ┌───────────────┐          ┌───────────────────────────────┐
                                           │ élément = KO   │          │ Mal formé (\ en tête/fin, \\) ? │
                                           └───────────────┘          └───────────────┬─────────────────┘
                                                                       ┌────────────────┴────────────────┐
                                                                       ▼                                  ▼
                                                                 ╔═════════╗                        ┌──────────┐
                                                                 ║ OUI ⚠️  ║                        │ NON ✅   │
                                                                 ╚════╤════╝                        └────┬─────┘
                                                                      ▼                                   ▼
                                                              ┌────────────────┐              ┌────────────────────────┐
                                                              │ élément = WARN  │              │ élément = OK             │
                                                              └────────────────┘              │ + mémoriser la casse du  │
                                                                                               │   nom de dossier         │
                                                                                               └────────────────────────┘
                          │ (après le parcours complet de toutes les tables/éléments)
                          ▼
          ┌────────────────────────────────────────────────┐
          │ Variantes de casse détectées pour un même        │
          │ dossier logique (ex. USAGE / Usage) ?             │
          └───────────────────────┬─────────────────────────┘
                       ┌─────────────┴─────────────┐
                       ▼                            ▼
                 ╔═════════╗                  ┌──────────┐
                 ║ OUI     ║                  │ NON      │
                 ╚════╤════╝                  └────┬─────┘
                      ▼                             │
          ┌────────────────────┐                    │
          │ AJOUTER un WARN     │                    │
          │ global               │                    │
          └──────────┬───────────┘                    │
                      └───────────────┬─────────────────┘
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ CALCUL DU STATUT GLOBAL                  │
                  │ (les éléments NA ne comptent jamais)     │
                  │ KO présent ?         -> règle = KO       │
                  │ Sinon WARN présent ? -> règle = WARN     │
                  │ Sinon                -> règle = OK       │
                  └────────────────────┬─────────────────────┘
                                       ▼
                             RETOUR rule_status
                             (OK / KO / WARN)
```
