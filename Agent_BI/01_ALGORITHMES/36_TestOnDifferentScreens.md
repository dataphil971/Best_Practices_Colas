# BP-36 — Test et validation visuelle du rapport sur différents écrans, résolutions et navigateurs

## 1. Objectif de la bonne pratique

Un rapport Power BI est consulté dans des contextes très hétérogènes : poste de travail avec un ou plusieurs écrans, portail Power BI Service dans un navigateur, application mobile (téléphone, tablette), écran de salle de réunion, export PDF/PowerPoint. Un rapport conçu et validé sur une seule résolution (typiquement le canevas d'édition 1920×1080) peut présenter, dans ces autres contextes, des visuels tronqués, du texte illisible, des segments qui se chevauchent ou une mise en page mobile absente qui contraint l'utilisateur à naviguer sur une version bureau non adaptée à un petit écran.

L'objectif de cette bonne pratique est double :

- vérifier que la **cohérence structurelle** minimale nécessaire à un rendu correct multi-support est respectée (dimensions de page homogènes, présence d'une mise en page mobile dédiée pour les pages clés) ;
- documenter clairement les limites de ce qu'un agent d'audit peut établir **statiquement**, à partir des seuls fichiers du projet PBIP, par opposition à une validation visuelle réelle (rendu effectif dans Power BI Service, sur Safari iOS, sur Edge, sur l'application mobile Power BI...), qui reste une tâche de QA humaine.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et de leur ordre dans `pageOrder` ;
- de l'identifiant technique (hexadécimal) de chaque page et de chaque visuel ;
- du fait qu'une page soit visible ou masquée en mode lecture (`visibility: "HiddenInViewMode"`) ;
- de l'existence ou non d'une documentation de plan de test externe au projet.

Cette fiche ne remplace donc pas une session de test manuelle multi-écrans/multi-navigateurs : elle formalise ce qu'un agent peut vérifier de façon fiable et fixe, pour le reste, un statut `WARN` accompagné d'une recommandation de validation humaine.

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\pages\pages.json                 (ordre des pages, page active, page d'atterrissage)
<REPORT_PATH>\definition\pages\<pageId>\page.json          (dimensions, displayOption, visibilité, éventuelle mise en page mobile)
<TEST_PLAN_PATH>                                           (document de plan de test, hors périmètre PBIP — chemin/nom à confirmer projet par projet)
```

Exemple pour ce projet (`AI_BAROMETER_BI-CDS.Report`) :

```text
AI_BAROMETER_BI-CDS.Report\definition\pages\pages.json
AI_BAROMETER_BI-CDS.Report\definition\pages\81a74ceaa660678035ae\page.json   (page "Overview", landingPageName)
AI_BAROMETER_BI-CDS.Report\definition\pages\13e9e9fd2ae0e0e76591\page.json   (page "About", HiddenInViewMode)
AI_BAROMETER_BI-CDS.Report\definition\pages\77c7ef1fa3804d5640e8\page.json
```

`pages.json` du projet audité :

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
  "pageOrder": [
    "81a74ceaa660678035ae", "681281ba4317edab1379", "58f1021603e406d600b2",
    "8ea91dc3e5e5ab0a43ae", "23ff3fc10a020bb396d9", "6d13bf2424ca09747390",
    "13e9e9fd2ae0e0e76591", "77c7ef1fa3804d5640e8"
  ],
  "activePageName": "81a74ceaa660678035ae",
  "landingPageName": "81a74ceaa660678035ae"
}
```

La page désignée par `landingPageName` (ici `81a74ceaa660678035ae`, « Overview ») est la première page vue par tout utilisateur : c'est la page pour laquelle l'absence de mise en page mobile ou une incohérence de dimensions a l'impact le plus visible, elle doit donc être traitée en priorité dans l'analyse.

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1. Dimensions déclarées de chaque page

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
  "name": "81a74ceaa660678035ae",
  "displayName": "Overview",
  "displayOption": "FitToPage",
  "height": 1080,
  "width": 1920,
  "visibility": null
}
```

- `height` / `width` : dimensions du canevas de conception de la page (en pixels logiques).
- `displayOption` : mode de rendu du canevas dans le conteneur du client (`"FitToPage"`, `"FitToWidth"`, `"ActualSize"` — valeurs à confirmer exhaustivement selon la version du schéma). Un mode `"ActualSize"` combiné à un client à petite fenêtre (navigateur en résolution réduite, application mobile) dégrade fortement l'expérience si aucune mise en page mobile n'est prévue.
- `visibility` : `"HiddenInViewMode"` si la page est masquée aux utilisateurs finaux (page technique, page « About », brouillon). Ces pages sont exclues de l'obligation de mise en page mobile mais restent incluses dans le contrôle de cohérence des dimensions déclarées.

### 3.2. Mise en page mobile dédiée

Power BI permet de définir, pour une page donnée, une disposition alternative des visuels optimisée pour un écran de téléphone (canevas étroit, empilement vertical). Dans le format PBIR, cette information est rattachée à la page — la structure exacte (bloc `mobileState` embarqué dans `page.json`, ou fichier séparé selon la version du schéma de définition de rapport) **est une propriété à confirmer selon la version du schéma** ; l'agent doit donc rechercher, de façon tolérante, toute clé ou tout fichier dont le nom contient `mobile` ou `mobileState` associé à l'identifiant de la page, plutôt que de supposer un chemin unique figé :

```jsonpath
$.mobileState                                   # si embarqué dans page.json
<REPORT_PATH>\definition\pages\<pageId>\mobile.json   # si porté par un fichier dédié (nom à confirmer)
```

Dans le projet audité, aucune occurrence de `mobileState` (ni fichier ni clé) n'a été trouvée dans `AI_BAROMETER_BI-CDS.Report\definition\pages\` : aucune page ne dispose actuellement d'une mise en page mobile dédiée.

### 3.3. Plan de test documenté

L'agent recherche, en dehors du dossier `.Report` (racine du dépôt projet ou dossier de documentation), un fichier décrivant un plan de test cross-device/cross-browser (nom non standardisé : `test-plan.md`, `QA_CHECKLIST.md`, `TESTS.md`...). Sa seule présence ne garantit pas que les tests ont été exécutés ; elle est traitée comme un indice de gouvernance, pas comme une preuve d'exécution.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Toutes les pages visibles déclarent les mêmes `width`/`height` | `OK` (sur ce critère) | Base de conception homogène, pas de risque de rupture de mise à l'échelle entre pages. |
| Une ou plusieurs pages visibles déclarent des `width`/`height` différents des autres sans raison apparente | `KO` | Incohérence de canevas : la navigation entre pages produira un saut de zoom/mise à l'échelle perceptible par l'utilisateur. |
| `height`/`width` absents ou non numériques sur une page | `NA` | Dimension non déterminable pour cette page. |
| Page d'atterrissage (`landingPageName`) ou pages visibles à fort trafic sans mise en page mobile détectée | `WARN` | Recommandation : concevoir une mise en page mobile dédiée pour les pages les plus consultées ; à défaut, l'affichage sur l'application mobile Power BI utilisera une mise à l'échelle automatique souvent dégradée. |
| Mise en page mobile détectée pour la page d'atterrissage et les pages principales | `OK` (sur ce critère) | Un rendu mobile a été anticipé pour les pages les plus consultées. |
| Aucun document de plan de test cross-device/cross-browser trouvé dans le projet | `WARN` | Recommandation : documenter un plan de test (liste des résolutions, navigateurs et supports à valider avant mise en production). |
| Rendu réel sur navigateur, application mobile, tablette, salle de réunion | `WARN` (non automatisable) | Validation visuelle humaine requise : l'agent ne peut ni ouvrir un navigateur ni observer un rendu pixel par pixel depuis les fichiers du projet. |

---

## 5. Parcours complet du rapport

### Étape 1 — Localiser les pages
1. Ouvrir `<REPORT_PATH>\definition\pages\pages.json`.
2. Récupérer `pageOrder` (liste complète des pages), `activePageName` et `landingPageName`.
3. Si le fichier est introuvable ou illisible, arrêter l'évaluation avec un statut technique `NON_EVALUE`.

### Étape 2 — Lire chaque page, sans exception
Pour chaque identifiant de `pageOrder` :
1. Ouvrir `<REPORT_PATH>\definition\pages\<pageId>\page.json`.
2. Extraire `displayName`, `height`, `width`, `displayOption`, `visibility`.
3. Rechercher une mise en page mobile associée (clé embarquée ou fichier séparé).
4. Continuer même si une page est masquée : elle est simplement classée à part pour l'obligation de mise en page mobile, mais reste comptée pour la cohérence des dimensions.

### Étape 3 — Comparer les pages entre elles
1. Constituer l'ensemble des couples `(height, width)` déclarés par les pages visibles.
2. Si cet ensemble contient plus d'une valeur distincte, signaler chaque page divergente.
3. Identifier les pages sans mise en page mobile parmi les pages visibles, en distinguant la page d'atterrissage des autres pages.

### Étape 4 — Rechercher un plan de test documenté
1. Explorer la racine du projet (hors dossiers `.Report`/`.SemanticModel` techniques) à la recherche d'un document de plan de test.
2. Consigner sa présence ou son absence — sans tenter d'en évaluer le contenu au-delà de la simple existence.

### Étape 5 — Terminer l'analyse
Produire : le nombre total de pages analysées (visibles et masquées) ; la liste des pages avec dimensions divergentes ; la liste des pages visibles sans mise en page mobile (avec mention spéciale pour la page d'atterrissage) ; la présence/absence d'un plan de test documenté ; le rappel explicite que la validation visuelle réelle sur écrans/navigateurs physiques reste hors périmètre automatisable.

L'agent ne s'arrête jamais à la première page en anomalie : toutes les pages du `pageOrder` doivent être parcourues avant de conclure.

---

## 6. Détection robuste / normalisation

- Les identifiants de page sont des chaînes hexadécimales générées par l'outil (`81a74ceaa660678035ae`, `77c7ef1fa3804d5640e8`...) : l'agent ne doit jamais les interpréter comme porteurs de sens métier ; seul `displayName` est lisible pour l'humain et doit être utilisé dans les messages restitués.
- `visibility` peut être absente (page visible par défaut) ou valoir `"HiddenInViewMode"` : l'absence de la clé équivaut à une page visible, ce n'est pas une anomalie.
- L'absence de bloc/fichier de mise en page mobile n'est pas une erreur de lecture : c'est un signal métier (« pas de mise en page mobile définie ») à traiter comme tel, pas comme un `NA` technique.
- Le nom exact et l'emplacement de la structure de mise en page mobile n'étant pas garantis dans toutes les versions du schéma PBIR, l'agent doit adopter une recherche tolérante (présence de toute clé/fichier contenant `mobile`) plutôt qu'un chemin unique strict, et consigner explicitement dans la preuve technique la méthode de détection utilisée.
- Le plan de test peut porter des noms très variables : l'agent doit chercher par mots-clés (`test`, `qa`, `plan`, `checklist`) insensibles à la casse plutôt qu'un nom de fichier unique.
- Les pages masquées (`HiddenInViewMode`) ne doivent pas déclencher de `WARN` pour absence de mise en page mobile : une page technique/de préparation n'a pas vocation à être consultée sur mobile.

---

## 7. Pseudo-code détaillé

```python
def analyze_screen_compatibility(report_path):
    pages_meta_path = f"{report_path}/definition/pages/pages.json"
    if not file_exists(pages_meta_path):
        return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
                "reason": "pages.json introuvable"}

    pages_meta = read_json(pages_meta_path)
    page_order = pages_meta.get("pageOrder", [])
    landing_page = pages_meta.get("landingPageName")

    if not page_order:
        return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
                "reason": "Aucune page déclarée dans pageOrder"}

    pages_info = []
    for page_id in page_order:
        page_json_path = f"{report_path}/definition/pages/{page_id}/page.json"
        if not file_exists(page_json_path):
            pages_info.append({"page_id": page_id, "status": "NA",
                                "reason": "page.json introuvable"})
            continue

        page = read_json(page_json_path)
        pages_info.append({
            "page_id": page_id,
            "display_name": page.get("displayName", page_id),
            "height": page.get("height"),
            "width": page.get("width"),
            "display_option": page.get("displayOption"),
            "is_hidden": page.get("visibility") == "HiddenInViewMode",
            "has_mobile_layout": detect_mobile_layout(report_path, page_id, page),
            "is_landing_page": page_id == landing_page,
        })

    visible_pages = [p for p in pages_info if not p.get("is_hidden") and p.get("height") and p.get("width")]

    dimension_set = {(p["height"], p["width"]) for p in visible_pages}
    inconsistent_pages = []
    if len(dimension_set) > 1:
        majority_dims = most_common(dimension_set, visible_pages)
        inconsistent_pages = [p for p in visible_pages
                               if (p["height"], p["width"]) != majority_dims]

    missing_mobile_layout = [p for p in visible_pages if not p["has_mobile_layout"]]
    landing_without_mobile = any(p["is_landing_page"] and not p["has_mobile_layout"]
                                  for p in visible_pages)

    test_plan_found = find_test_plan_document(project_root(report_path))

    na_pages = [p for p in pages_info if p.get("status") == "NA"]

    return build_result(inconsistent_pages, missing_mobile_layout,
                         landing_without_mobile, test_plan_found,
                         na_pages, total=len(pages_info))


def detect_mobile_layout(report_path, page_id, page_json):
    if "mobileState" in page_json:
        return True
    for candidate in list_files(f"{report_path}/definition/pages/{page_id}"):
        if "mobile" in candidate.lower():
            return True
    return False
```

---

## 8. Calcul du statut global

Cette bonne pratique combine des constats bloquants (incohérence réelle de dimensions, qui casse le rendu) et des recommandations non bloquantes (mise en page mobile absente, plan de test non documenté, validation visuelle humaine). Le statut global suit donc la priorité `KO > NA > WARN > OK` :

```python
if inconsistent_pages:
    rule_status = "KO"
elif na_pages:
    rule_status = "NA"
elif missing_mobile_layout or not test_plan_found:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les pages visibles partagent les mêmes dimensions, mise en page mobile présente pour la page d'atterrissage, plan de test documenté | `OK` |
| Au moins une page visible a des dimensions divergentes | `KO` |
| Une ou plusieurs pages n'ont pas pu être lues | `NA` |
| Dimensions homogènes mais mise en page mobile absente et/ou plan de test non documenté | `WARN` |

Dans tous les cas, la validation visuelle effective sur des écrans, navigateurs et applications réels reste signalée comme recommandation humaine, même lorsque le statut global calculé est `OK` sur les critères automatisables.

---

## 9. Structure du résultat

Exemple `OK` (sur les critères automatisables) :

```json
{
  "rule_id": "BP-36",
  "rule_name": "Test et validation sur différents écrans/navigateurs",
  "execution_status": "SUCCESS",
  "rule_status": "WARN",
  "total_pages": 8,
  "visible_pages": 7,
  "hidden_pages": 1,
  "inconsistent_dimension_pages": [],
  "pages_without_mobile_layout": [
    "Overview", "Perception", "Training", "Knowledge", "Adoption", "Usage", "Conclusion"
  ],
  "landing_page_without_mobile_layout": true,
  "test_plan_document_found": false,
  "human_validation_required": true
}
```

Exemple `KO` (incohérence de dimensions) :

```json
{
  "rule_id": "BP-36",
  "rule_name": "Test et validation sur différents écrans/navigateurs",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_pages": 8,
  "visible_pages": 7,
  "hidden_pages": 1,
  "inconsistent_dimension_pages": [
    {"page": "Conclusion", "height": 900, "width": 1600, "expected": {"height": 1080, "width": 1920}}
  ],
  "pages_without_mobile_layout": ["Overview", "Perception", "Training", "Knowledge", "Adoption", "Usage"],
  "landing_page_without_mobile_layout": true,
  "test_plan_document_found": false,
  "human_validation_required": true
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `WARN`

```text
BP-36 — Test et validation sur différents écrans/navigateurs : WARN

Cohérence structurelle : les 7 pages visibles déclarent toutes le même canevas
1920x1080 (aucune incohérence de dimensions détectée).

Points d'attention :
- aucune mise en page mobile dédiée n'a été trouvée, y compris pour la page
  d'atterrissage "Overview" : l'application mobile Power BI affichera cette
  page en mise à l'échelle automatique, ce qui dégrade souvent la lisibilité
  des visuels denses.
- aucun document de plan de test cross-device/cross-browser n'a été trouvé
  dans le projet.

Ces deux points sont des recommandations, pas des anomalies bloquantes.

Recommandation :
1. concevoir une mise en page mobile pour "Overview" et les pages les plus
   consultées ;
2. documenter et exécuter un plan de test manuel couvrant au minimum :
   Power BI Service (Chrome, Edge), application mobile (iOS/Android),
   résolution bureau réduite (1366x768) et grand écran de salle de réunion.

Rappel : le rendu visuel réel sur ces supports ne peut pas être vérifié depuis
les seuls fichiers du projet et nécessite une validation humaine.
```

### Exemple `KO`

```text
BP-36 — Test et validation sur différents écrans/navigateurs : KO

Incohérence de canevas détectée :
- page "Conclusion" : 1600x900, alors que les 6 autres pages visibles
  utilisent 1920x1080.

Cette divergence provoque un saut de mise à l'échelle visible lors de la
navigation entre pages et doit être corrigée avant toute campagne de test
visuel, sans quoi les écarts observés seront en partie dus à cette
incohérence de configuration plutôt qu'à un problème de rendu du client.

Correction attendue :
harmoniser la propriété "height"/"width" de la page "Conclusion" sur
1920x1080, comme les autres pages du rapport.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit conclure `OK` sur les critères automatisables que si toutes les conditions suivantes sont réunies :

- `pages.json` a été lu et `pageOrder` contient au moins une page ;
- chaque page listée dans `pageOrder` a été ouverte et ses dimensions extraites ;
- aucune page visible ne présente de dimensions divergentes par rapport aux autres ;
- la page d'atterrissage dispose d'une mise en page mobile détectée ;
- toutes les pages visibles à fort trafic disposent d'une mise en page mobile détectée ;
- un document de plan de test a été localisé dans le projet.

L'agent doit systématiquement rappeler, y compris en cas de `OK`, que la validation visuelle réelle sur navigateurs/appareils physiques reste une étape humaine non couverte par cette lecture statique — un `OK` ne signifie donc jamais « testé visuellement », uniquement « structurellement cohérent et documenté ».

---

## 12. Résumé de la règle

```text
RÈGLE BP-36

LIRE pages.json (pageOrder, landingPageName)
POUR chaque page du pageOrder
    LIRE page.json (height, width, displayOption, visibility)
    DÉTECTER la présence d'une mise en page mobile dédiée
    ENREGISTRER les informations de la page
FIN POUR

COMPARER les dimensions des pages visibles
SI des dimensions divergent
    règle = KO
SINON SI des pages n'ont pas pu être lues
    règle = NA
SINON SI mise en page mobile absente (page d'atterrissage incluse)
     OU aucun plan de test documenté trouvé
    règle = WARN
SINON
    règle = OK

RAPPELER systématiquement que le rendu réel sur écrans/navigateurs physiques
reste une validation humaine hors périmètre de cette lecture statique
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-36 — Test et validation multi-écrans/navigateurs       │
└────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │ Lire pages.json                │
          │ (pageOrder, landingPageName)   │
          └──────────────┬──────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────┐
         ║ Trouvé ✅   ║    │ Introuvable/vide ❌│
         ╚════╤════════╝    └────────┬───────────┘
              │                      ▼
              │              ┌─────────────────────┐
              │              │ Retour : NON_EVALUE  │
              │              └─────────────────────┘
              ▼
 ┌───────────────────────────────────────────┐
 │ POUR chaque page de pageOrder              │
 │  LIRE page.json (height, width,            │
 │  displayOption, visibility)                │
 │  DÉTECTER mise en page mobile (mobile*)    │
 └──────────────┬───────────────────────────────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
╔═════════════╗   ┌───────────────┐
║ page.json ✅║   │ Introuvable ❌ │
╚═════╤═══════╝   └───────┬────────┘
      │                   ▼
      │           ┌──────────────┐
      │           │ Page = NA    │
      │           └──────────────┘
      ▼
 ┌────────────────────────────────────────┐
 │ COMPARER (height,width) des pages       │
 │ visibles entre elles                    │
 └──────────────┬───────────────────────────┘
                ▼
       ┌────────┴─────────┐
       ▼                   ▼
╔═════════════════╗  ┌─────────────────────┐
║ Dimensions       ║  │ 1+ page divergente   │
║ homogènes        ║  │                      │
╚════════╤═════════╝  └──────────┬────────────┘
         │                        ▼
         │                ┌──────────────┐
         │                │ KO (rupture   │
         │                │ de mise à     │
         │                │ l'échelle)    │
         │                └──────────────┘
         ▼
 ┌────────────────────────────────────────┐
 │ Page d'atterrissage / pages visibles    │
 │ sans mise en page mobile ?              │
 │ Plan de test documenté trouvé ?         │
 └──────────────┬───────────────────────────┘
                ▼
       ┌────────┴─────────┐
       ▼                   ▼
╔═════════════════╗  ┌─────────────────────────┐
║ Mobile OK ET     ║  │ Mobile absent OU plan    │
║ plan trouvé      ║  │ de test absent -> WARN   │
╚════════╤═════════╝  └─────────────────────────┘
         ▼
     ┌──────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL              │
     │ Priorité : KO > NA > WARN > OK        │
     └──────────────┬─────────────────────────┘
                     │
    ┌────────────────┼─────────────────┬───────────────┐
    ▼                ▼                 ▼                ▼
╔═════════╗   ┌─────────────┐   ┌─────────────┐  ┌─────────────┐
║ Dimensions║  │ Page(s) non  │   │ Mobile/plan │  │ Tout OK      │
║ divergentes│  │ lues -> NA   │   │ absent      │  │ -> OK        │
║ -> KO      ║  └─────────────┘   │ -> WARN     │  └─────────────┘
╚═════════╝                       └─────────────┘
                     │
                     ▼
        RETOUR rule_status (OK/KO/NA/WARN)
        + RAPPEL : validation visuelle réelle = hors périmètre
```
