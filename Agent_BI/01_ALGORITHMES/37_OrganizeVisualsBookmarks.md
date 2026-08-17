# BP-37 — Organisation des visuels (groupes) et des signets (bookmarks)

## 1. Objectif de la bonne pratique

Un rapport Power BI mature accumule rapidement des dizaines de visuels par page et des dizaines de signets pour piloter la navigation, les vues alternatives ou les états de filtre. Sans organisation explicite, le volet de sélection (« Selection pane ») affiche une liste plate de visuels nommés automatiquement (`Group1`, `TextBox3`, `Slicer12`...) et le volet de signets affiche une liste plate de signets sans hiérarchie, rendant la maintenance du rapport dépendante de la mémoire de son auteur d'origine.

L'objectif de cette règle est de vérifier que :

- les visuels apparentés sont **regroupés** (`visualGroup`) sous un nom explicite plutôt que laissés en éléments isolés portant un nom auto-généré ;
- les signets sont **organisés en dossiers/groupes de signets** (`bookmarks/bookmarks.json`, structure `items[].children[]`) portant un `displayName` explicite plutôt qu'un intitulé technique par défaut (`Bookmark 1`, `Bookmark 2`...).

Cette organisation facilite la maintenance (un contributeur reprend le rapport et comprend immédiatement la structure), réduit le risque d'erreur lors d'une modification (on manipule un groupe cohérent plutôt que des visuels épars) et améliore l'expérience de navigation lorsque les groupes de signets sont exposés dans un visuel de navigation.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages, de visuels et de signets ;
- des identifiants techniques hexadécimaux générés par l'outil pour les pages, visuels, groupes et signets ;
- du nombre de groupes de visuels ou de dossiers de signets effectivement créés.

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json     (visuels et groupes de visuels)
<REPORT_PATH>\definition\bookmarks\bookmarks.json                          (hiérarchie des signets)
<REPORT_PATH>\definition\bookmarks\<bookmarkId>.bookmark.json              (contenu de chaque signet)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.Report\definition\pages\81a74ceaa660678035ae\visuals\1a2d7452a63db41882ea\visual.json  (groupe de visuels)
AI_BAROMETER_BI-CDS.Report\definition\bookmarks\bookmarks.json
AI_BAROMETER_BI-CDS.Report\definition\bookmarks\00dae2a10218b562dc4a.bookmark.json
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1. Groupe de visuels — `visual.json` d'un conteneur de groupe

Un groupe de visuels est lui-même représenté par un fichier `visual.json` dans le dossier `visuals/` de la page, mais sans clé `visual` : il porte une clé `visualGroup` à la place, et les visuels qu'il contient référencent son identifiant via leur propre propriété `parentGroupName`.

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json",
  "name": "1a2d7452a63db41882ea",
  "position": { "x": 64, "y": 593.02, "z": 1000, "height": 456.25, "width": 1151.60, "tabOrder": 4000 },
  "visualGroup": {
    "displayName": "USAGE OF AI",
    "groupMode": "ScaleMode"
  }
}
```

Un visuel membre de ce groupe référence le groupe ainsi :

```json
{
  "name": "40e24ea779a62934c9c1",
  "visual": { "visualType": "columnChart", "...": "..." },
  "parentGroupName": "1a2d7452a63db41882ea"
}
```

Propriété décisionnelle : `visualGroup.displayName`. Un nom auto-généré non renommé par l'utilisateur suit typiquement un motif reconnaissable (`Group`, `Group1`, `Group 2`...), alors qu'un nom explicite décrit le contenu métier du groupe (`"USAGE OF AI"`, `"Filtres de page"`, `"KPIs synthèse"`...).

### 3.2. Hiérarchie des signets — `bookmarks.json`

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmarksMetadata/1.0.0/schema.json",
  "items": [
    {
      "name": "247ec431ac3ccd01a994",
      "displayName": "Nav Pane",
      "children": ["93894c76102e57062c89", "e550f6f21061dd61973d"]
    },
    {
      "name": "b44cdf3056b70aea9394",
      "displayName": "Evolution switch",
      "children": ["253af9bc2b019c689a8d", "00dae2a10218b562dc4a"]
    }
  ]
}
```

Propriétés décisionnelles :
- au niveau `items[]` (dossier/groupe de signets) : `displayName`, comparé au motif technique par défaut (`"Bookmark group"`, `"Group"`...) ;
- pour un signet individuel non rattaché à un groupe (élément d'`items[]` sans `children`, ou signet référencé nulle part), le contrôle porte directement sur son propre `displayName`.

### 3.3. Signet individuel — `<bookmarkId>.bookmark.json`

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/2.1.0/schema.json",
  "displayName": "Cumulated levels",
  "name": "00dae2a10218b562dc4a",
  "options": { "targetVisualNames": [], "suppressData": true },
  "explorationState": { "...": "..." }
}
```

Propriété décisionnelle : `displayName`, comparé au motif générique par défaut de Power BI Desktop (`"Bookmark 1"`, `"Bookmark 2"`, ...).

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Groupe de visuels avec `visualGroup.displayName` explicite (ex. `"USAGE OF AI"`) | `OK` | Le groupe est nommé de façon compréhensible pour un contributeur tiers. |
| Groupe de visuels avec un nom auto-généré non renommé (`"Group1"`, `"Group 2"`) | `KO` | Le nom par défaut n'apporte aucune information sur le contenu du groupe. |
| Plusieurs visuels apparentés sur une page (même thématique, même zone) ne sont dans **aucun** groupe | `WARN` | Regroupement recommandé mais non strictement obligatoire : l'absence de groupe n'est pas une erreur en soi si la page compte peu de visuels. |
| Dossier de signets (`items[]` avec `children`) avec `displayName` explicite (ex. `"Filter Pane Evolution"`) | `OK` | Organisation claire du volet de signets. |
| Dossier de signets ou signet isolé avec `displayName` par défaut (`"Bookmark 1"`) | `KO` | Le signet n'a pas été renommé après sa création, ce qui nuit à la navigation et à la maintenance. |
| `bookmarks.json` absent alors que des fichiers `*.bookmark.json` existent | `NA` | Incohérence structurelle : la hiérarchie ne peut pas être établie, mais les signets existent. |
| Aucun signet dans le rapport | `NA` (hors périmètre) | Rien à organiser : la règle ne s'applique pas. |

---

## 5. Parcours complet du rapport

### Étape 1 — Localiser les pages et les visuels
1. Lire `<REPORT_PATH>\definition\pages\pages.json` pour obtenir la liste complète des pages.
2. Pour chaque page, lister tous les fichiers `visuals\<visualId>\visual.json`.

### Étape 2 — Classer chaque conteneur : visuel simple ou groupe
Pour chaque `visual.json` : s'il contient une clé `visualGroup`, le traiter comme groupe (contrôle du `displayName`) ; sinon, s'il contient une clé `parentGroupName`, l'enregistrer comme membre d'un groupe existant ; sinon, l'enregistrer comme visuel isolé, hors groupe.

### Étape 3 — Évaluer chaque groupe de visuels détecté
Pour chaque groupe : comparer `visualGroup.displayName` au motif par défaut ; enregistrer `OK` ou `KO` avec le nom du groupe et la page concernée.

### Étape 4 — Signaler les concentrations de visuels isolés
Sur chaque page, si le nombre de visuels hors groupe dépasse un seuil (ex. plus de 5 visuels non-textbox non groupés), signaler un `WARN` de recommandation de regroupement — sans bloquer l'évaluation globale.

### Étape 5 — Localiser et lire les signets
1. Lire `<REPORT_PATH>\definition\bookmarks\bookmarks.json` s'il existe.
2. Lister tous les fichiers `*.bookmark.json` du dossier `bookmarks\`.
3. Croiser les deux : tout signet présent en fichier mais absent de la hiérarchie `bookmarks.json` (ni en racine, ni comme enfant d'un dossier) est signalé comme non organisé.

### Étape 6 — Évaluer chaque dossier de signets et chaque signet isolé
Pour chaque entrée de `items[]` : comparer `displayName` au motif par défaut. Pour chaque signet référencé par un `children[]`, comparer également son propre `displayName` (un dossier bien nommé peut contenir des signets eux-mêmes mal nommés).

### Étape 7 — Terminer l'analyse
Parcourir la totalité des pages, groupes, visuels isolés, dossiers de signets et signets individuels avant de conclure. Produire les listes complètes de `KO` (noms par défaut non renommés) et de `WARN` (regroupement recommandé) par catégorie (visuels / signets).

---

## 6. Détection robuste / normalisation

- Les noms techniques (`name` de page, de visuel, de groupe, de signet) sont des identifiants hexadécimaux opaques (`1a2d7452a63db41882ea`, `00dae2a10218b562dc4a`...) : ils ne doivent jamais être utilisés pour juger de la qualité du nommage — seul `displayName` (ou `visualGroup.displayName`) compte.
- Les motifs de nommage par défaut de Power BI Desktop doivent être reconnus par expression régulière tolérante (ex. `^Group\s?\d*$`, `^Bookmark\s?\d*$`, `^TextBox\s?\d*$`, `^Slicer\s?\d*$`), insensible à la casse et aux espaces, plutôt que par comparaison exacte à une liste figée.
- Un visuel de type `textbox` peut légitimement rester hors groupe (simple titre ou légende de page) : l'agent doit pondérer le seuil de déclenchement du `WARN` de regroupement en excluant les textbox du décompte des visuels « à regrouper ».
- L'absence de `parentGroupName` sur un visuel n'est pas une erreur de lecture : c'est un état normal pour un visuel volontairement isolé.
- Les pages masquées (`visibility: "HiddenInViewMode"`) restent analysées au même titre que les pages visibles : l'organisation interne d'une page technique reste une bonne pratique de maintenabilité.
- Un dossier de signets peut être imbriqué (un `children` peut lui-même pointer vers un autre dossier plutôt qu'un signet terminal, selon la version du schéma) : l'agent doit résoudre la hiérarchie de façon récursive et éviter les boucles infinies via un ensemble `visited`.

---

## 7. Pseudo-code détaillé

```python
DEFAULT_NAME_PATTERNS = {
    "group": re.compile(r"^group\s?\d*$", re.IGNORECASE),
    "bookmark": re.compile(r"^bookmark\s?\d*$", re.IGNORECASE),
    "textbox": re.compile(r"^text ?box\s?\d*$", re.IGNORECASE),
    "slicer": re.compile(r"^slicer\s?\d*$", re.IGNORECASE),
}

def is_default_name(display_name, kind):
    if not display_name:
        return True
    pattern = DEFAULT_NAME_PATTERNS.get(kind)
    return bool(pattern and pattern.match(display_name.strip()))


def analyze_visual_groups(report_path, pages):
    ok_groups, ko_groups, ungrouped_warnings = [], [], []

    for page in pages:
        visual_files = list_visual_json_files(report_path, page.id)
        groups, members, isolated = {}, [], []

        for vfile in visual_files:
            data = read_json(vfile)
            if "visualGroup" in data:
                groups[data["name"]] = {
                    "display_name": data["visualGroup"].get("displayName"),
                    "page": page.display_name,
                }
            elif "parentGroupName" in data:
                members.append(data)
            elif data.get("visual", {}).get("visualType") != "textbox":
                isolated.append(data)

        for group_id, group in groups.items():
            if is_default_name(group["display_name"], "group"):
                ko_groups.append({"page": group["page"], "group_id": group_id,
                                   "display_name": group["display_name"]})
            else:
                ok_groups.append({"page": group["page"], "group_id": group_id,
                                   "display_name": group["display_name"]})

        if len(isolated) > 5:
            ungrouped_warnings.append({
                "page": page.display_name,
                "ungrouped_visual_count": len(isolated),
                "reason": "Nombre élevé de visuels hors groupe sur la page",
            })

    return ok_groups, ko_groups, ungrouped_warnings


def analyze_bookmarks(report_path):
    bookmarks_meta_path = f"{report_path}/definition/bookmarks/bookmarks.json"
    bookmark_files = list_bookmark_files(report_path)

    if not bookmark_files:
        return {"execution_status": "SUCCESS", "rule_status": "NA",
                "reason": "Aucun signet dans le rapport"}

    if not file_exists(bookmarks_meta_path):
        return {"execution_status": "PARTIAL", "rule_status": "NA",
                "reason": "bookmarks.json introuvable alors que des signets existent"}

    hierarchy = read_json(bookmarks_meta_path)
    referenced_ids = set()
    ok_folders, ko_folders = [], []

    for item in hierarchy.get("items", []):
        referenced_ids.add(item["name"])
        if item.get("children"):
            if is_default_name(item.get("displayName"), "bookmark"):
                ko_folders.append({"id": item["name"], "display_name": item.get("displayName")})
            else:
                ok_folders.append({"id": item["name"], "display_name": item.get("displayName")})
            referenced_ids.update(item["children"])

    ok_bookmarks, ko_bookmarks, unorganized_bookmarks = [], [], []
    for bfile in bookmark_files:
        bookmark = read_json(bfile)
        entry = {"id": bookmark["name"], "display_name": bookmark.get("displayName")}
        if bookmark["name"] not in referenced_ids:
            unorganized_bookmarks.append(entry)
        if is_default_name(bookmark.get("displayName"), "bookmark"):
            ko_bookmarks.append(entry)
        else:
            ok_bookmarks.append(entry)

    return {
        "ok_folders": ok_folders, "ko_folders": ko_folders,
        "ok_bookmarks": ok_bookmarks, "ko_bookmarks": ko_bookmarks,
        "unorganized_bookmarks": unorganized_bookmarks,
    }
```

---

## 8. Calcul du statut global

```python
if ko_groups or ko_folders or ko_bookmarks:
    rule_status = "KO"
elif na_condition:          # bookmarks.json manquant, ou lecture partielle
    rule_status = "NA"
elif ungrouped_warnings or unorganized_bookmarks:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Tous les groupes de visuels et tous les signets/dossiers portent un nom explicite | `OK` |
| Au moins un groupe de visuels ou un dossier/signet porte encore un nom par défaut non renommé | `KO` |
| `bookmarks.json` introuvable alors que des fichiers `*.bookmark.json` existent | `NA` |
| Nommage correct partout mais concentration de visuels non groupés ou signets non rattachés à un dossier | `WARN` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-37",
  "rule_name": "Organisation des visuels et des signets",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_visual_groups": 4,
  "ko_visual_groups": 0,
  "total_bookmark_folders": 9,
  "ko_bookmark_folders": 0,
  "total_bookmarks": 22,
  "ko_bookmarks": 0,
  "ungrouped_visual_warnings": [],
  "unorganized_bookmarks": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-37",
  "rule_name": "Organisation des visuels et des signets",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_visual_groups": 4,
  "ko_visual_groups": 1,
  "ko_visual_group_details": [
    {"page": "Perception", "group_id": "3a9c6ea846666528c09c", "display_name": "Group 1"}
  ],
  "total_bookmark_folders": 9,
  "ko_bookmark_folders": 1,
  "ko_bookmark_folder_details": [
    {"id": "9f1a2b3c4d5e6f708192", "display_name": "Bookmark group 1"}
  ],
  "total_bookmarks": 22,
  "ko_bookmarks": 2,
  "ko_bookmark_details": [
    {"id": "a1b2c3d4e5f607182930", "display_name": "Bookmark 1"},
    {"id": "b2c3d4e5f60718293041", "display_name": "Bookmark 2"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-37 — Organisation des visuels et des signets : OK

4 groupes de visuels, 9 dossiers de signets et 22 signets analysés.
Tous portent un nom explicite (ex. "USAGE OF AI", "Filter Pane Evolution",
"Cumulated levels") — aucun nom auto-généré non renommé détecté.
```

### Exemple `KO`

```text
BP-37 — Organisation des visuels et des signets : KO

Éléments non renommés détectés :
- Page "Perception" : groupe de visuels "Group 1" (nom par défaut).
- Dossier de signets "Bookmark group 1" (nom par défaut).
- Signets "Bookmark 1" et "Bookmark 2" non renommés.

Ces noms par défaut ne permettent pas à un contributeur tiers de comprendre
le contenu du groupe ou du signet sans l'ouvrir.

Correction attendue :
renommer chaque groupe/dossier/signet avec un intitulé décrivant son contenu
métier (ex. "Filtres — Perception", "Vue synthèse KPI"), en cohérence avec
la convention déjà utilisée sur le reste du rapport.
```

---

## 11. Conditions empêchant un faux OK

- toutes les pages du rapport ont été parcourues et tous les fichiers `visual.json` lus ;
- chaque groupe de visuels détecté (`visualGroup`) a été comparé au motif de nom par défaut ;
- `bookmarks.json` a été lu avec succès et tous les fichiers `*.bookmark.json` du dossier ont été recensés ;
- chaque dossier de signets (`items[]` avec `children`) et chaque signet référencé a été comparé au motif de nom par défaut ;
- les signets présents en fichier mais absents de la hiérarchie `bookmarks.json` ont été identifiés ;
- aucun groupe, dossier ou signet ne porte un nom par défaut non renommé.

---

## 12. Résumé de la règle

```text
RÈGLE BP-37

POUR chaque page
    POUR chaque visual.json
        SI contient "visualGroup" -> évaluer displayName du groupe (nom par défaut ?)
        SINON SI contient "parentGroupName" -> membre d'un groupe, rien à évaluer directement
        SINON (hors textbox) -> visuel isolé, compter pour le seuil de regroupement
    FIN POUR
FIN POUR

LIRE bookmarks.json
POUR chaque dossier de signets (items[] avec children)
    ÉVALUER displayName (nom par défaut ?)
    POUR chaque signet enfant -> ÉVALUER displayName (nom par défaut ?)
FIN POUR
IDENTIFIER les signets présents en fichier mais absents de la hiérarchie

SI au moins un groupe/dossier/signet porte un nom par défaut
    règle = KO
SINON SI bookmarks.json manquant malgré des signets existants
    règle = NA
SINON SI visuels non groupés en nombre élevé OU signets non organisés
    règle = WARN
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-37 — Organisation des visuels (groupes) et signets     │
└────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │ Lire pages.json (liste pages)  │
          └──────────────┬──────────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────────────┐
     │ POUR chaque page, POUR chaque visual.json          │
     │   SI clé "visualGroup" -> conteneur de groupe       │
     │   SINON SI "parentGroupName" -> membre d'un groupe  │
     │   SINON (hors textbox) -> visuel isolé               │
     └──────────────┬─────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
 ┌─────────────────────┐  ┌──────────────────────────┐
 │ Groupe détecté       │  │ Visuels isolés > 5 sur    │
 │ displayName          │  │ la page (hors textbox)     │
 │ = motif par défaut ? │  └──────────────┬─────────────┘
 └──────────┬────────────┘                 ▼
   ┌────────┴────────┐               ┌─────────────┐
   ▼                 ▼               │ WARN         │
╔═════════╗   ┌─────────────┐        │ (regroupement│
║ Non ->OK║   │ Oui -> KO   │        │ recommandé)  │
╚═════════╝   └─────────────┘        └─────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │ Lire bookmarks\bookmarks.json  │
          │ + lister *.bookmark.json       │
          └──────────────┬──────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
       ┌───────────────┐     ╔═════════════════════╗
       │ Aucun signet   │     ║ Signets présents     ║
       │ -> NA (hors    │     ╚══════════╤═══════════╝
       │ périmètre)     │                │
       └───────────────┘        ┌────────┴────────┐
                                 ▼                 ▼
                          ╔═════════════╗   ┌────────────────────┐
                          ║ bookmarks.  ║   │ bookmarks.json      │
                          ║ json trouvé ║   │ manquant -> NA       │
                          ╚══════╤══════╝   └────────────────────┘
                                 ▼
                 ┌─────────────────────────────────────┐
                 │ POUR chaque dossier (items[])         │
                 │  ÉVALUER displayName (défaut ?)       │
                 │  POUR chaque signet enfant            │
                 │   ÉVALUER displayName (défaut ?)      │
                 │ IDENTIFIER signets orphelins           │
                 │ (fichier présent, absent hiérarchie)   │
                 └──────────────┬──────────────────────────┘
                                ▼
                       ┌────────┴─────────┐
                       ▼                   ▼
                ╔═════════════════╗  ┌─────────────────────┐
                ║ Nom par défaut   ║  │ Nom explicite / OK   │
                ║ détecté -> KO    ║  └─────────────────────┘
                ╚═════════════════╝
                          │
                          ▼
     ┌──────────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL                  │
     │ Priorité : KO > NA > WARN > OK            │
     └──────────────┬─────────────────────────────┘
                     │
    ┌────────────────┼─────────────────┬───────────────┐
    ▼                ▼                 ▼                ▼
╔═════════╗   ┌─────────────┐   ┌─────────────┐  ┌─────────────┐
║ 1+ nom   ║   │ bookmarks.  │   │ Visuels non  │  │ Tout nommé   │
║ défaut   ║   │ json manquant│  │ groupés/     │  │ explicitement│
║ -> KO    ║   │ -> NA        │  │ signets non  │  │ -> OK        │
╚═════════╝   └─────────────┘   │ organisés     │  └─────────────┘
                                 │ -> WARN       │
                                 └─────────────┘
                     │
                     ▼
        RETOUR rule_status (OK/KO/NA/WARN)
```
