# BP-41 — Détection des visuels redondants ou dupliqués

## 1. Objectif de la bonne pratique

Un rapport qui évolue au fil des itérations accumule parfois des visuels quasi identiques : un graphique dupliqué pour tester une variante puis oublié, un visuel copié-collé d'une page à l'autre sans réel besoin de le répéter, ou deux tableaux affichant strictement les mêmes champs et les mêmes filtres avec une présentation différente. Ces doublons alourdissent le temps de chargement du rapport (chaque visuel génère sa propre requête DAX), complexifient la maintenance (une correction doit être répercutée sur chaque copie) et n'apportent aucune valeur analytique supplémentaire à l'utilisateur final.

L'objectif de cette règle est de détecter les visuels dont la **signature analytique** — type de visuel, champs projetés sur chaque rôle (`Category`, `Values`, `Legend`, `Rows`, `Columns`...) et filtres propres au visuel — est strictement identique à celle d'un autre visuel, que ce soit sur la même page ou sur des pages différentes du rapport.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et de visuels ;
- des identifiants techniques hexadécimaux des pages et des visuels ;
- de la mise en forme (couleurs, titre, position, taille) des visuels comparés, qui n'entre pas dans la signature analytique.

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json
```

L'agent doit parcourir l'ensemble des visuels de l'ensemble des pages du rapport, par exemple :

```text
AI_BAROMETER_BI-CDS.Report\definition\pages\81a74ceaa660678035ae\visuals\40e24ea779a62934c9c1\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\23ff3fc10a020bb396d9\visuals\42429c460c8e29129420\visual.json
...
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1. Type de visuel et projections de champs

```json
{
  "visual": {
    "visualType": "columnChart",
    "query": {
      "queryState": {
        "Category": {
          "projections": [
            { "field": { "Column": { "Expression": { "SourceRef": { "Entity": "F_RESPONSES" } }, "Property": "AI_USAGE_FREQ_LEVEL" } },
              "queryRef": "F_RESPONSES.AI_USAGE_FREQ_LEVEL" }
          ]
        },
        "Y": {
          "projections": [
            { "field": { "Measure": { "Expression": { "SourceRef": { "Entity": "MEASURE" } }, "Property": "Nb_Responses" } },
              "queryRef": "MEASURE.Nb_Responses" }
          ]
        }
      }
    }
  }
}
```

Propriétés décisionnelles constituant la signature d'un visuel :
- `visual.visualType` ;
- pour chaque rôle visuel présent dans `visual.query.queryState` (`Category`, `Y`, `Values`, `Rows`, `Columns`, `Legend`, `Series`...) : l'ensemble ordonné des `queryRef` projetés sur ce rôle ;
- les filtres propres au visuel (`visual.filterConfig.filters[]`, résolus en couples `(Entity, Property)` + condition — cf. [BP-39](39_ConfigAndTestFilters.md) pour la structure détaillée).

Les propriétés de mise en forme (`objects`, `visualContainerObjects`, position, couleurs, titre) sont **exclues** de la signature : deux visuels avec des couleurs et des titres différents mais des champs et filtres strictement identiques restent des doublons fonctionnels.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Deux visuels de la page (ou de pages différentes) partagent le même `visualType`, les mêmes champs projetés sur chaque rôle et les mêmes filtres propres | `KO` | Doublon fonctionnel confirmé : les deux visuels affichent strictement la même information. |
| Deux visuels ont le même type et les mêmes champs mais des filtres de visuel différents | `OK` | Les visuels répondent à des questions analytiques différentes malgré une apparence proche (ex. même graphique, filtré sur des périodes différentes). |
| Deux visuels ont le même type et les mêmes champs sur `Category`/`Rows` mais des mesures différentes sur `Values`/`Y` | `OK` | Visuels complémentaires, pas redondants. |
| Visuel de type `textbox`, `image`, `shape` ou `actionButton` comparé à un autre visuel | `NA` (hors périmètre) | Ces types n'ont pas de signature analytique comparable : ils sont exclus de la détection de redondance. |
| Visuel sans bloc `query.queryState` interprétable (visuel custom, structure non standard) | `NA` | Signature non déterminable avec cette lecture. |

---

## 5. Parcours complet du rapport

### Étape 1 — Localiser tous les visuels
1. Lire `pages.json` pour la liste complète des pages.
2. Pour chaque page, lister tous les fichiers `visuals\<visualId>\visual.json`.

### Étape 2 — Construire la signature de chaque visuel
Pour chaque visuel analytique (hors `textbox`/`image`/`shape`/`actionButton`) : extraire `visualType` ; pour chaque rôle de `query.queryState`, extraire la liste triée des `queryRef` ; extraire et normaliser les filtres propres au visuel ; construire une signature canonique combinant ces trois éléments.

### Étape 3 — Comparer toutes les paires de visuels
Regrouper les visuels par signature identique, sur l'ensemble du rapport (pas seulement au sein d'une même page). Toute paire ou groupe de visuels partageant exactement la même signature est un doublon candidat.

### Étape 4 — Qualifier chaque doublon détecté
Pour chaque groupe de signature identique : vérifier qu'il s'agit bien d'au moins deux visuels distincts (pas une comparaison d'un visuel avec lui-même) ; enregistrer les pages et identifiants concernés.

### Étape 5 — Terminer l'analyse
Parcourir l'intégralité des pages et des visuels avant de conclure — ne jamais s'arrêter au premier doublon trouvé. Produire : le nombre total de visuels analytiques analysés, le nombre de groupes de doublons détectés, le détail de chaque groupe (pages et visuels concernés), le nombre de visuels exclus du périmètre (`NA`).

---

## 6. Détection robuste / normalisation

- Les identifiants de page et de visuel (hexadécimaux) ne doivent jamais entrer dans le calcul de la signature : deux visuels identiques sur deux pages différentes restent des doublons malgré des `name` totalement différents.
- L'ordre des rôles dans `query.queryState` n'est pas garanti stable d'un export à l'autre : la signature doit trier les rôles par nom avant comparaison.
- Au sein d'un même rôle, l'ordre des projections doit également être normalisé (trié par `queryRef`) avant comparaison, pour ne pas considérer comme différents deux visuels dont les champs sont identiques mais déclarés dans un ordre différent.
- Les filtres de visuel doivent être normalisés selon la même logique que celle décrite en [BP-39](39_ConfigAndTestFilters.md) (résolution en ensembles de valeurs autorisées/exclues) avant comparaison, plutôt qu'une comparaison textuelle brute du JSON, qui échouerait sur de simples différences de formatage ou d'ordre de conditions.
- Un visuel présent dans un groupe de visuels (`visualGroup`, cf. [BP-37](37_OrganizeVisualsBookmarks.md)) reste comparé normalement : l'appartenance à un groupe ne fait pas partie de la signature.
- Les pages masquées (`HiddenInViewMode`) sont incluses dans la comparaison : un visuel dupliqué entre une page technique et une page visible reste un doublon à signaler, même si son impact utilisateur est moindre.
- Deux visuels avec des `nativeQueryRef` (libellés lisibles) différents mais des `queryRef` techniques identiques doivent être considérés comme identiques : seule la référence technique compte, jamais le libellé d'affichage.

---

## 7. Pseudo-code détaillé

```python
NON_ANALYTICAL_TYPES = {"textbox", "image", "shape", "actionButton", "basicShape"}

def build_visual_signature(visual_json):
    visual = visual_json.get("visual", {})
    visual_type = visual.get("visualType")
    if visual_type in NON_ANALYTICAL_TYPES:
        return None

    query_state = visual.get("query", {}).get("queryState")
    if not query_state:
        return None

    role_signature = {}
    for role_name, role_data in query_state.items():
        refs = sorted(p.get("queryRef", "") for p in role_data.get("projections", []))
        role_signature[role_name] = tuple(refs)

    filters = visual.get("filterConfig", {}).get("filters", [])
    normalized_filters = tuple(sorted(normalize_filter(f) for f in filters))

    signature = (
        visual_type,
        tuple(sorted(role_signature.items())),
        normalized_filters,
    )
    return signature


def analyze_redundant_visuals(report_path, pages):
    signatures = {}   # signature -> [{"page": ..., "visual_id": ...}]
    na_visuals = []

    for page in pages:
        for vfile in list_visual_json_files(report_path, page.id):
            data = read_json(vfile)
            if "visualGroup" in data:
                continue   # conteneur de groupe, pas un visuel analytique

            signature = build_visual_signature(data)
            if signature is None:
                na_visuals.append({"page": page.display_name, "visual_id": data["name"]})
                continue

            signatures.setdefault(signature, []).append({
                "page": page.display_name, "visual_id": data["name"],
            })

    duplicate_groups = [
        {"visual_type": sig[0], "occurrences": occ, "count": len(occ)}
        for sig, occ in signatures.items()
        if len(occ) > 1
    ]

    return duplicate_groups, na_visuals
```

---

## 8. Calcul du statut global

```python
if duplicate_groups:
    rule_status = "KO"
elif na_visuals and not any_analytical_visual_found:
    rule_status = "NA"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Aucun groupe de visuels à signature identique détecté | `OK` |
| Au moins un groupe de deux visuels ou plus partage exactement la même signature | `KO` |
| Aucun visuel analytique comparable trouvé dans le rapport (uniquement textbox/images) | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-41",
  "rule_name": "Détection des visuels redondants ou dupliqués",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_analytical_visuals": 62,
  "duplicate_groups": [],
  "na_visuals": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-41",
  "rule_name": "Détection des visuels redondants ou dupliqués",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_analytical_visuals": 62,
  "duplicate_groups": [
    {
      "visual_type": "columnChart",
      "count": 2,
      "occurrences": [
        {"page": "Adoption", "visual_id": "4f36c5d7ccc129a12ccd"},
        {"page": "Adoption", "visual_id": "7645f16326d020ca0620"}
      ]
    },
    {
      "visual_type": "card",
      "count": 2,
      "occurrences": [
        {"page": "Overview", "visual_id": "5ab2ce08ed12dee71131"},
        {"page": "Usage", "visual_id": "2c471defb41934090d39"}
      ]
    }
  ],
  "na_visuals": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-41 — Détection des visuels redondants ou dupliqués : OK

62 visuels analytiques comparés sur l'ensemble du rapport. Aucun visuel ne
partage exactement le même type, les mêmes champs projetés et les mêmes
filtres qu'un autre — pas de doublon fonctionnel détecté.
```

### Exemple `KO`

```text
BP-41 — Détection des visuels redondants ou dupliqués : KO

2 groupes de visuels redondants détectés :
- Page "Adoption" : les visuels "4f36c5d7ccc129a12ccd" et
  "7645f16326d020ca0620" sont deux graphiques en colonnes (columnChart)
  affichant strictement les mêmes champs et les mêmes filtres.
- Page "Overview" / "Usage" : les cartes "5ab2ce08ed12dee71131" et
  "2c471defb41934090d39" affichent exactement le même indicateur avec les
  mêmes filtres, sur deux pages différentes.

Correction attendue :
supprimer l'un des deux visuels de chaque groupe, ou différencier leur
filtre/leurs champs s'ils répondent réellement à des questions analytiques
distinctes malgré une apparence actuellement identique.
```

---

## 11. Conditions empêchant un faux OK

- toutes les pages du rapport ont été parcourues et tous les visuels de chaque page lus, y compris sur les pages masquées ;
- pour chaque visuel analytique, la signature (type + champs par rôle + filtres normalisés) a été correctement construite, sans dépendre de l'ordre d'origine des projections ni des identifiants techniques ;
- la comparaison a été effectuée sur l'ensemble du rapport, pas uniquement au sein de chaque page prise isolément ;
- les filtres propres au visuel ont été normalisés (ensembles de valeurs) avant comparaison, pas comparés textuellement ;
- aucun groupe de deux visuels ou plus ne partage une signature strictement identique.

---

## 12. Résumé de la règle

```text
RÈGLE BP-41

POUR chaque page
    POUR chaque visual.json analytique (hors textbox/image/shape/bouton)
        CONSTRUIRE la signature : (visualType, champs par rôle triés, filtres normalisés triés)
        REGROUPER par signature sur l'ensemble du rapport
    FIN POUR
FIN POUR

POUR chaque groupe de signature identique
    SI le groupe contient 2 visuels ou plus
        groupe = doublon détecté (KO)

SI au moins un groupe de doublons détecté
    règle = KO
SINON SI aucun visuel analytique comparable trouvé
    règle = NA
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-41 — Détection des visuels redondants ou dupliqués     │
└────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │ Lire pages.json (liste pages)  │
          └──────────────┬──────────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────────────┐
     │ POUR chaque page                                   │
     │  POUR chaque visual.json (hors conteneur de groupe) │
     └──────────────┬─────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ╔═════════════════╗   ┌────────────────────────────┐
   │ textbox/image/    │   │ Visuel analytique           │
   │ shape/actionButton │   │ (query.queryState présent)  │
   │ -> NA (hors        │   └──────────────┬────────────────┘
   │ périmètre)          │                  ▼
   ╚═════════════════╝     ┌──────────────────────────────────┐
                            │ CONSTRUIRE la signature :         │
                            │ (visualType, champs par rôle      │
                            │ triés, filtres normalisés triés)  │
                            └──────────────┬───────────────────────┘
                                           ▼
                            ┌──────────────────────────────────┐
                            │ REGROUPER par signature identique │
                            │ sur l'ENSEMBLE du rapport          │
                            │ (toutes pages confondues)          │
                            └──────────────┬───────────────────────┘
                                           ▼
                                  ┌────────┴─────────┐
                                  ▼                   ▼
                           ╔═════════════════╗  ┌─────────────────────┐
                           ║ Groupe de        ║  │ Chaque signature     │
                           ║ signature avec    ║  │ apparaît une seule   │
                           ║ 2 visuels ou plus ║  │ fois                │
                           ║ -> doublon        ║  └─────────────────────┘
                           ╚════════╤═════════╝
                                    ▼
                              ┌─────────────┐
                              │ Groupe = KO │
                              └─────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL                  │
     │ Priorité : KO > NA > OK                   │
     └──────────────┬─────────────────────────────┘
                     │
    ┌────────────────┼─────────────────┐
    ▼                ▼                 ▼
╔═════════╗   ┌──────────────────┐  ┌─────────────┐
║ 1+ groupe║   │ Aucun visuel      │  │ Aucun groupe │
║ de       ║   │ analytique        │  │ dupliqué,    │
║ doublons ║   │ comparable trouvé │  │ visuels      │
║ -> KO    ║   │ -> NA             │  │ analysés     │
╚═════════╝   └──────────────────┘  │ -> OK        │
                                      └─────────────┘
                     │
                     ▼
        RETOUR rule_status (OK/KO/NA)
```
