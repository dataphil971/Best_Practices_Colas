# BP-43 — Désactivation des en-têtes de visuel non nécessaires

## 1. Objectif de la bonne pratique

Chaque visuel Power BI peut afficher, au survol, un en-tête flottant proposant des icônes d'action : menu contextuel (« … »), filtre, épingler dans un tableau de bord, exporter les données, développer/réduire, agrandir. Cet en-tête est utile dans un contexte d'exploration libre (rapport analytique destiné à des utilisateurs qui interagissent activement avec les données), mais devient un artefact visuel superflu — voire une source de confusion ou un risque de gouvernance (export de données non souhaité) — dans un rapport orienté présentation ou lecture, où l'utilisateur n'est pas censé manipuler chaque visuel individuellement.

L'objectif de cette règle est de vérifier que l'en-tête de visuel (`visualContainerObjects.visualHeader`) a fait l'objet d'un choix explicite et cohérent avec la vocation de chaque page : désactivé sur les visuels de restitution pure (cartes de synthèse, textboxes, visuels de mise en page), et laissé actif uniquement là où une interaction réelle de l'utilisateur (export, filtre ponctuel, agrandissement) apporte une valeur reconnue.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et de visuels ;
- des identifiants techniques hexadécimaux des pages et des visuels ;
- du type précis de chaque visuel.

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json
```

Exemple réel de ce projet, visuel en-tête désactivé (page « Overview ») :

```text
AI_BAROMETER_BI-CDS.Report\definition\pages\81a74ceaa660678035ae\visuals\40e24ea779a62934c9c1\visual.json
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1. Propriété de visibilité de l'en-tête

Extrait réel du projet audité — en-tête explicitement désactivé sur un graphique en colonnes :

```json
{
  "visual": {
    "visualType": "columnChart",
    "visualContainerObjects": {
      "visualHeader": [
        {
          "properties": {
            "show": { "expr": { "Literal": { "Value": "false" } } },
            "transparency": { "expr": { "Literal": { "Value": "0D" } } }
          }
        }
      ]
    }
  }
}
```

Propriété décisionnelle : `visual.visualContainerObjects.visualHeader[0].properties.show.expr.Literal.Value`, dont la valeur littérale attendue est `"true"` ou `"false"` (chaîne représentant un booléen DAX).

### 3.2. Cas d'absence de configuration explicite

```json
{
  "visual": {
    "visualType": "card",
    "visualContainerObjects": {
      "title": [ { "properties": { "text": { "expr": { "Literal": { "Value": "'Total répondants'" } } } } } ]
    }
  }
}
```

Lorsque la clé `visualHeader` est totalement absente du bloc `visualContainerObjects`, l'en-tête reste au comportement **par défaut de Power BI, qui est activé** (affiché au survol). L'absence de la clé équivaut donc à un en-tête actif non revu, et non à un en-tête désactivé.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `visualHeader[0].properties.show` = `"false"` sur un visuel de restitution (carte, jauge, indicateur KPI, textbox) | `OK` | En-tête désactivé sur un visuel où il n'apporte pas de valeur d'interaction — rendu épuré cohérent. |
| `visualHeader[0].properties.show` = `"true"` ou clé absente sur un visuel de restitution pure d'une page orientée présentation | `KO` | En-tête resté actif par défaut sans revue, sur un type de visuel où il n'a généralement pas d'utilité pour l'utilisateur final. |
| `visualHeader[0].properties.show` = `"true"` sur un visuel où l'export ou le filtre ponctuel est une fonctionnalité voulue (tableau détaillé, page d'exploration libre) | `OK` | Choix cohérent : l'en-tête reste actif là où l'interaction a une valeur reconnue. |
| Visuel de type `textbox`, `shape`, `image`, `actionButton` avec en-tête actif | `WARN` | Ces types n'affichent jamais de données exportables ; un en-tête actif n'a quasiment aucune utilité, mais son impact visuel est mineur (recommandation, non bloquant). |
| Groupe de visuels (`visualGroup`) : la clé `visualHeader` ne s'applique pas | `NA` (hors périmètre) | Un conteneur de groupe n'a pas d'en-tête individuel ; seuls les visuels membres sont concernés. |

---

## 5. Parcours complet du rapport

### Étape 1 — Localiser toutes les pages et tous les visuels
1. Lire `pages.json` pour la liste complète des pages.
2. Pour chaque page, lister tous les fichiers `visuals\<visualId>\visual.json`, en excluant les conteneurs de groupe (clé `visualGroup` sans clé `visual`).

### Étape 2 — Lire l'état de l'en-tête de chaque visuel
Pour chaque visuel : rechercher `visual.visualContainerObjects.visualHeader[0].properties.show` ; extraire sa valeur littérale ; si absente, considérer l'en-tête comme actif par défaut.

### Étape 3 — Qualifier chaque visuel selon son type et le contexte de la page
1. Déterminer si le visuel appartient à une catégorie de restitution pure (`card`, `multiRowCard`, `gauge`, `kpi`, `textbox`) ou à une catégorie où l'export/filtre reste généralement utile (`tableEx`, `matrix`, `pivotTable`).
2. Comparer l'état de l'en-tête à l'attendu de sa catégorie.

### Étape 4 — Terminer l'analyse
Parcourir l'intégralité des pages et des visuels avant de conclure — ne jamais s'arrêter au premier en-tête actif trouvé. Produire : le nombre total de visuels analysés, le nombre d'en-têtes désactivés/actifs par catégorie, la liste des visuels `KO` (en-tête actif non justifié sur un visuel de restitution pure), la liste des `WARN` (textbox/shape avec en-tête actif).

---

## 6. Détection robuste / normalisation

- La valeur de `show` est portée par une structure `{"expr": {"Literal": {"Value": "..."}}}` : l'agent doit extraire la valeur littérale finale (`"true"`/`"false"`) et la normaliser (minuscule, sans guillemets ni espace) avant comparaison, plutôt que de comparer la structure brute.
- L'absence de la clé `visualHeader` ne doit jamais être interprétée comme un `NA` technique : c'est un signal métier exploitable (« en-tête actif par défaut, jamais revu »).
- La classification d'un visuel en « restitution pure » versus « interaction utile » repose sur son `visualType` : cette liste doit rester paramétrable (certains projets peuvent légitimement vouloir désactiver les en-têtes même sur les tableaux), et tout `visualType` non répertorié doit être traité prudemment, en `WARN` plutôt qu'en `KO` automatique, pour éviter un faux positif sur un type de visuel personnalisé (custom visual) dont l'usage de l'en-tête n'est pas connu a priori.
- Les visuels de groupes (`visualGroup`) sont exclus du périmètre direct : seuls leurs membres (portant une clé `visual`) sont évalués.
- Les pages masquées (`HiddenInViewMode`) sont incluses dans l'analyse : un en-tête non désactivé sur une page technique reste un défaut de configuration, même si son impact utilisateur final est réduit.

---

## 7. Pseudo-code détaillé

```python
RESTITUTION_ONLY_TYPES = {"card", "multiRowCard", "gauge", "kpi", "textbox"}
INTERACTION_USEFUL_TYPES = {"tableEx", "matrix", "pivotTable"}
NON_DATA_TYPES = {"textbox", "shape", "image", "actionButton", "basicShape"}

def extract_header_visibility(visual_json):
    try:
        header_block = visual_json["visual"]["visualContainerObjects"]["visualHeader"][0]
        raw_value = header_block["properties"]["show"]["expr"]["Literal"]["Value"]
        return str(raw_value).strip().strip("'").lower() == "true"
    except (KeyError, IndexError):
        return True   # absence de configuration explicite => comportement par défaut : en-tête actif


def analyze_visual_headers(report_path, pages):
    ok_visuals, ko_visuals, warn_visuals = [], [], []

    for page in pages:
        for vfile in list_visual_json_files(report_path, page.id):
            data = read_json(vfile)
            if "visualGroup" in data:
                continue   # conteneur de groupe hors périmètre direct

            visual_type = data.get("visual", {}).get("visualType")
            if not visual_type:
                continue

            header_active = extract_header_visibility(data)
            entry = {"page": page.display_name, "visual_id": data["name"],
                     "visual_type": visual_type, "header_active": header_active}

            if visual_type in NON_DATA_TYPES:
                if header_active:
                    warn_visuals.append({**entry, "reason": "En-tête actif sur un visuel sans données exportables"})
                else:
                    ok_visuals.append(entry)
            elif visual_type in RESTITUTION_ONLY_TYPES:
                if header_active:
                    ko_visuals.append({**entry, "reason": "En-tête actif sur un visuel de restitution pure"})
                else:
                    ok_visuals.append(entry)
            elif visual_type in INTERACTION_USEFUL_TYPES:
                ok_visuals.append(entry)   # actif ou non : choix légitime selon le contexte
            else:
                warn_visuals.append({**entry, "reason": "Type de visuel non répertorié : vérification manuelle recommandée"})

    return ok_visuals, ko_visuals, warn_visuals
```

---

## 8. Calcul du statut global

```python
if ko_visuals:
    rule_status = "KO"
elif warn_visuals:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Aucun visuel de restitution pure n'a d'en-tête actif non justifié | `OK` |
| Au moins un visuel de restitution pure (carte, jauge, textbox...) a un en-tête actif non désactivé | `KO` |
| Aucun `KO`, mais au moins un visuel non-data (shape/textbox) ou de type non répertorié à vérifier manuellement | `WARN` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-43",
  "rule_name": "Désactivation des en-têtes de visuel non nécessaires",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_visuals": 62,
  "ko_visuals": [],
  "warn_visuals": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-43",
  "rule_name": "Désactivation des en-têtes de visuel non nécessaires",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_visuals": 62,
  "ko_visuals": [
    {"page": "Overview", "visual_id": "5ab2ce08ed12dee71131", "visual_type": "card",
     "header_active": true, "reason": "En-tête actif sur un visuel de restitution pure"},
    {"page": "Usage", "visual_id": "2c471defb41934090d39", "visual_type": "card",
     "header_active": true, "reason": "En-tête actif sur un visuel de restitution pure"}
  ],
  "warn_visuals": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-43 — Désactivation des en-têtes de visuel non nécessaires : OK

62 visuels analysés. Les en-têtes de visuel sont désactivés sur l'ensemble
des cartes, jauges et zones de texte du rapport ; ils restent actifs
uniquement sur les tableaux/matrices, où l'export et le filtrage ponctuel
conservent une utilité pour l'utilisateur.
```

### Exemple `KO`

```text
BP-43 — Désactivation des en-têtes de visuel non nécessaires : KO

En-têtes actifs non justifiés détectés :
- Page "Overview" : carte "5ab2ce08ed12dee71131" (visualHeader.show = true).
- Page "Usage" : carte "2c471defb41934090d39" (visualHeader.show absent,
  donc actif par défaut).

Ces visuels de restitution pure n'exposent aucune interaction utile derrière
leur en-tête (pas de données tabulaires à exporter, pas de filtre pertinent
au clic), l'en-tête flottant n'est ici qu'un artefact visuel superflu.

Correction attendue :
sur chacun de ces visuels, désactiver l'en-tête via le volet Format >
En-tête du visuel > Afficher = Désactivé.
```

---

## 11. Conditions empêchant un faux OK

- toutes les pages du rapport ont été parcourues et tous les visuels (hors conteneurs de groupe) lus, y compris sur les pages masquées ;
- pour chaque visuel, l'état de l'en-tête a été déterminé explicitement, en traitant l'absence de la clé `visualHeader` comme « actif par défaut » et non comme un cas ignoré ;
- chaque visuel a été classé selon son `visualType` dans l'une des catégories définies (restitution pure / interaction utile / non-data / non répertorié) ;
- aucun visuel de restitution pure ne conserve un en-tête actif non justifié ;
- les visuels de type non répertorié ont été signalés en `WARN` plutôt qu'ignorés silencieusement.

---

## 12. Résumé de la règle

```text
RÈGLE BP-43

POUR chaque page
    POUR chaque visual.json (hors conteneur de groupe)
        LIRE visualContainerObjects.visualHeader[0].properties.show
        SI absent -> en-tête considéré actif par défaut

        SI visualType ∈ visuels de restitution pure (card, gauge, kpi, textbox...)
            SI en-tête actif -> KO
            SINON -> OK
        SINON SI visualType ∈ visuels sans données (shape, image, bouton...)
            SI en-tête actif -> WARN
            SINON -> OK
        SINON SI visualType ∈ visuels où l'interaction reste utile (tableau, matrice...)
            -> OK (choix contextuel légitime)
        SINON
            -> WARN (type non répertorié, vérification manuelle recommandée)
    FIN POUR
FIN POUR

SI au moins un visuel KO
    règle = KO
SINON SI au moins un visuel WARN
    règle = WARN
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-43 — Désactivation des en-têtes de visuel non          │
│         nécessaires                                               │
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
     │   LIRE visualContainerObjects.visualHeader[0]        │
     │        .properties.show                              │
     │   SI absent -> en-tête considéré ACTIF par défaut    │
     └──────────────┬─────────────────────────────────────┘
                     │
                     ▼
        ┌────────────┴─────────────┐
        ▼                          ▼
 ╔═══════════════════╗   ┌──────────────────────────────┐
 │ visualType ∈        │   │ visualType ∈ restitution pure  │
 │ non-data (shape,     │   │ (card, gauge, kpi, textbox)    │
 │ image, actionButton, │   └──────────────┬────────────────────┘
 │ textbox)              │                  ▼
 ╚══════════╤═══════════╝         ┌────────┴─────────┐
            ▼                     ▼                   ▼
   ┌────────┴────────┐    ╔═════════════╗     ┌─────────────┐
   ▼                 ▼    ║ En-tête      ║     │ En-tête      │
╔═════════╗  ┌─────────┐  ║ actif -> KO  ║     │ désactivé    │
║ Actif    ║  │ Désactivé║ ╚═════════════╝     │ -> OK        │
║ -> WARN  ║  │ -> OK    ║                     └─────────────┘
╚═════════╝  └─────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────┐
     │ visualType ∈ interaction utile             │
     │ (tableEx, matrix, pivotTable)              │
     │ -> OK quel que soit l'état (choix          │
     │    contextuel légitime)                     │
     └──────────────────────────────────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────┐
     │ visualType non répertorié                  │
     │ -> WARN (vérification manuelle recommandée)│
     └──────────────────────────────────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL                  │
     │ Priorité : KO > WARN > OK                 │
     └──────────────┬─────────────────────────────┘
                     │
       ┌─────────────┼─────────────────┐
       ▼              ▼                 ▼
╔═════════════╗ ┌─────────────┐  ┌─────────────┐
║ 1+ visuel   ║ │ 0 KO, 1+     │  │ Aucun visuel │
║ restitution ║ │ WARN -> WARN │  │ KO/WARN      │
║ pure avec   ║ └─────────────┘  │ -> OK        │
║ en-tête     ║                  └─────────────┘
║ actif ->KO  ║
╚═════════════╝
                     │
                     ▼
        RETOUR rule_status (OK/KO/WARN)
```
