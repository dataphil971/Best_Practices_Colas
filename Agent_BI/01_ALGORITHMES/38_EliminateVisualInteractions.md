# BP-38 — Élimination des interactions croisées inutiles entre visuels

## 1. Objectif de la bonne pratique

Par défaut, Power BI applique une interaction croisée (filtrage croisé ou surbrillance) entre **chaque paire de visuels** d'une même page : cliquer sur un point de données dans un visuel filtre ou met en surbrillance tous les autres visuels de la page. Sur une page dense (8, 10, 15 visuels), ce comportement par défaut produit un maillage combinatoire d'interactions qui n'a, dans la grande majorité des cas, aucune valeur analytique : un clic sur un segment d'un graphique peut, par exemple, filtrer un visuel de KPI global sans rapport logique avec la sélection, créant une confusion pour l'utilisateur qui ne comprend pas pourquoi un chiffre a changé.

L'objectif de cette règle est de vérifier que les interactions entre visuels ont été **explicitement revues** : soit conservées en filtrage croisé lorsque cela a un sens analytique, soit désactivées (`"None"`) lorsque l'interaction par défaut ne serait qu'une source de confusion. Une page où aucune interaction n'a jamais été retouchée par rapport au comportement par défaut de Power BI est un signal fort qu'aucune revue de ce type n'a été effectuée.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et du nombre de visuels par page ;
- des identifiants techniques hexadécimaux des pages et des visuels ;
- du type des visuels concernés (graphique, tableau, carte, slicer...).

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\pages\<pageId>\page.json     (bloc visualInteractions de la page)
```

Exemple pour ce projet, page « Overview » (`81a74ceaa660678035ae`) :

```text
AI_BAROMETER_BI-CDS.Report\definition\pages\81a74ceaa660678035ae\page.json
```

---

## 3. Élément(s) / propriété(s) à contrôler

Chaque page porte, à la racine de son `page.json`, un tableau `visualInteractions` recensant les interactions qui ont été **explicitement configurées** entre deux visuels (par défaut, une interaction non listée dans ce tableau reste implicitement active avec le comportement standard de Power BI — filtrage croisé bidirectionnel).

Extrait réel du projet audité (page « Overview ») :

```json
{
  "visualInteractions": [
    { "source": "2576a7aa58a50052d2b0", "target": "7218dfa2d79d437421cd", "type": "DataFilter" },
    { "source": "7218dfa2d79d437421cd", "target": "2576a7aa58a50052d2b0", "type": "DataFilter" },
    { "source": "40e24ea779a62934c9c1", "target": "377f8710bd7cb960ee08", "type": "DataFilter" },
    { "source": "40e24ea779a62934c9c1", "target": "2ad1485e9875c33189ee", "type": "DataFilter" },
    { "source": "08c6180fb692310a817a", "target": "40e24ea779a62934c9c1", "type": "DataFilter" }
  ]
}
```

- `source` : identifiant (`name`) du visuel dont l'action déclenche l'interaction.
- `target` : identifiant du visuel affecté.
- `type` : nature de l'interaction explicitement configurée. Les valeurs usuelles (propriété à confirmer exhaustivement selon la version du schéma) sont notamment `"DataFilter"` (filtrage croisé — comportement par défaut rendu explicite ou reconfirmé), `"Highlight"` (surbrillance au lieu du filtrage) et `"None"` (interaction désactivée entre les deux visuels).

Point clé pour l'évaluation : Power BI **n'écrit une entrée dans `visualInteractions` que pour les couples de visuels dont le comportement a été modifié ou explicitement validé via le ruban « Format > Modifier les interactions »**. Un couple de visuels absent de ce tableau fonctionne toujours avec le filtrage croisé par défaut, jamais revu.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Page avec peu de visuels (≤ 4) et `visualInteractions` vide ou absent | `OK` | Le nombre réduit de visuels limite le risque de confusion ; l'absence de revue explicite est acceptable. |
| Page avec un nombre élevé de visuels (> 4) et **aucune** entrée `visualInteractions` | `KO` | Aucune interaction n'a jamais été revue sur une page dense : toutes les combinaisons de filtrage croisé par défaut restent actives sans validation. |
| Page avec un nombre élevé de visuels et au moins une entrée `type: "None"` présente | `OK` | Preuve qu'une revue des interactions a été effectuée et que certaines ont été désactivées à bon escient. |
| Entrée `visualInteractions` référençant un `source` ou un `target` qui ne correspond à aucun `visual.json` existant sur la page | `KO` | Configuration obsolète : le visuel référencé a été supprimé sans nettoyer les interactions associées. |
| Page comportant un slicer et des visuels cibles sans aucune entrée associée à ce slicer | `WARN` | Recommandation de vérifier explicitement que le filtrage croisé du slicer vers chaque visuel est voulu (les slicers filtrent par défaut, ce cas n'est pas nécessairement une anomalie mais mérite une revue humaine ciblée). |

---

## 5. Parcours complet du rapport

### Étape 1 — Localiser les pages
1. Lire `<REPORT_PATH>\definition\pages\pages.json` pour obtenir la liste complète des pages.
2. Exclure éventuellement les pages masquées (`HiddenInViewMode`) du calcul du seuil « page dense », tout en les gardant dans le périmètre de vérification de cohérence des références.

### Étape 2 — Charger l'inventaire des visuels de chaque page
Pour chaque page, lister tous les fichiers `visuals\<visualId>\visual.json` afin de disposer de l'ensemble des identifiants de visuels réellement présents (nécessaire pour détecter les références obsolètes de l'étape 4).

### Étape 3 — Lire le bloc `visualInteractions`
1. Ouvrir `page.json`.
2. Extraire le tableau `visualInteractions` (tableau vide si absent).
3. Compter le nombre de visuels non-textbox de la page (les textbox ne participent pas au filtrage croisé analytique).

### Étape 4 — Évaluer la page
1. Si le nombre de visuels dépasse le seuil et qu'aucune entrée `visualInteractions` n'existe, marquer la page `KO`.
2. Si des entrées existent, vérifier que chaque `source` et chaque `target` correspond à un visuel réellement présent sur la page ; toute référence orpheline est un `KO`.
3. Vérifier la présence d'au moins une entrée `type: "None"` ou `"Highlight"` sur les pages denses comme indice de revue effective.
4. Passer à la page suivante, quel que soit le résultat.

### Étape 5 — Terminer l'analyse
Parcourir l'intégralité des pages avant de conclure. Produire : le nombre de pages analysées, le nombre de pages denses sans revue d'interaction (`KO`), le nombre de références obsolètes détectées, la liste des pages `WARN` pour revue humaine ciblée des slicers.

---

## 6. Détection robuste / normalisation

- Les identifiants `source`/`target` sont des chaînes hexadécimales opaques : ils doivent être résolus vers un nom de visuel lisible (`visualType`, titre du visuel dans `visualContainerObjects.title`, ou à défaut son identifiant) uniquement pour la restitution du message, jamais pour la logique de décision.
- L'absence de `visualInteractions` dans `page.json` n'est pas une erreur de lecture : c'est l'état par défaut d'une page où aucune interaction n'a jamais été retouchée.
- Le seuil de densité (nombre de visuels au-delà duquel l'absence de revue devient un `KO`) doit rester paramétrable (valeur par défaut proposée : 4 visuels analytiques hors textbox et hors groupes) et documenté dans le résultat, afin de rester adaptable à différents contextes de projet.
- Un même couple de visuels peut apparaître dans les deux sens (`A→B` et `B→A`) avec des types différents, l'interaction n'étant pas nécessairement symétrique : l'agent ne doit jamais fusionner les deux sens en une seule entrée.
- Les groupes de visuels (`visualGroup`, cf. BP-37) ne portent pas d'interactions propres : seuls les visuels feuilles (avec une clé `visual`) sont concernés par `source`/`target`.
- Les pages masquées en mode lecture restent vérifiées pour la cohérence des références (visuel supprimé), mais peuvent être exclues du calcul du seuil de densité si elles ne sont jamais consultées par l'utilisateur final.

---

## 7. Pseudo-code détaillé

```python
DENSITY_THRESHOLD = 4          # nombre de visuels analytiques au-delà duquel une revue est attendue
REVIEW_EVIDENCE_TYPES = {"None", "Highlight"}

def analyze_visual_interactions(report_path, pages):
    dense_pages_without_review = []
    orphan_reference_pages = []
    slicer_warning_pages = []
    analyzed_pages = []

    for page in pages:
        page_json = read_json(f"{report_path}/definition/pages/{page.id}/page.json")
        interactions = page_json.get("visualInteractions", [])

        visual_files = list_visual_json_files(report_path, page.id)
        known_visual_ids = set()
        analytical_visual_count = 0
        slicer_ids = []

        for vfile in visual_files:
            data = read_json(vfile)
            known_visual_ids.add(data["name"])
            visual_type = data.get("visual", {}).get("visualType")
            if visual_type and visual_type != "textbox":
                analytical_visual_count += 1
            if visual_type == "slicer":
                slicer_ids.append(data["name"])

        orphan_refs = [
            i for i in interactions
            if i["source"] not in known_visual_ids or i["target"] not in known_visual_ids
        ]
        if orphan_refs:
            orphan_reference_pages.append({
                "page": page.display_name,
                "orphan_interactions": orphan_refs,
            })

        has_review_evidence = any(i.get("type") in REVIEW_EVIDENCE_TYPES for i in interactions)

        if analytical_visual_count > DENSITY_THRESHOLD and not interactions:
            dense_pages_without_review.append({
                "page": page.display_name,
                "analytical_visual_count": analytical_visual_count,
                "reason": "Page dense sans aucune entrée visualInteractions : aucune revue effectuée",
            })
        elif analytical_visual_count > DENSITY_THRESHOLD and not has_review_evidence:
            dense_pages_without_review.append({
                "page": page.display_name,
                "analytical_visual_count": analytical_visual_count,
                "reason": "Interactions présentes mais aucune désactivation/surbrillance explicite détectée",
            })

        for slicer_id in slicer_ids:
            covered = any(i["source"] == slicer_id or i["target"] == slicer_id for i in interactions)
            if not covered and analytical_visual_count > DENSITY_THRESHOLD:
                slicer_warning_pages.append({"page": page.display_name, "slicer_id": slicer_id})

        analyzed_pages.append(page.display_name)

    return dense_pages_without_review, orphan_reference_pages, slicer_warning_pages, analyzed_pages
```

---

## 8. Calcul du statut global

```python
if orphan_reference_pages or dense_pages_without_review:
    rule_status = "KO"
elif slicer_warning_pages:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les pages denses portent une preuve de revue des interactions, aucune référence orpheline | `OK` |
| Au moins une page dense n'a aucune trace de revue des interactions | `KO` |
| Au moins une entrée `visualInteractions` référence un visuel inexistant | `KO` |
| Aucun cas ci-dessus, mais des slicers de pages denses sans entrée d'interaction associée | `WARN` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-38",
  "rule_name": "Élimination des interactions croisées inutiles",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_pages": 8,
  "dense_pages": 5,
  "dense_pages_without_review": [],
  "orphan_reference_pages": [],
  "slicer_warning_pages": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-38",
  "rule_name": "Élimination des interactions croisées inutiles",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_pages": 8,
  "dense_pages": 5,
  "dense_pages_without_review": [
    {
      "page": "Training",
      "analytical_visual_count": 7,
      "reason": "Page dense sans aucune entrée visualInteractions : aucune revue effectuée"
    }
  ],
  "orphan_reference_pages": [
    {
      "page": "Overview",
      "orphan_interactions": [
        {"source": "40e24ea779a62934c9c1", "target": "supprimeVisualId", "type": "DataFilter"}
      ]
    }
  ],
  "slicer_warning_pages": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-38 — Élimination des interactions croisées inutiles : OK

8 pages analysées, 5 pages denses (plus de 4 visuels analytiques).
Chacune de ces pages présente au moins une interaction explicitement
désactivée ou passée en surbrillance, preuve d'une revue effective du
filtrage croisé par défaut. Aucune référence obsolète détectée.
```

### Exemple `KO`

```text
BP-38 — Élimination des interactions croisées inutiles : KO

Page "Training" : 7 visuels analytiques, aucune entrée "visualInteractions"
dans page.json — le filtrage croisé par défaut de Power BI reste actif entre
chacun des 7 visuels (21 combinaisons possibles) sans qu'aucune revue n'ait
été effectuée.

Page "Overview" : une interaction référence un visuel qui n'existe plus
(source "40e24ea779a62934c9c1" -> cible introuvable), signe d'une
configuration obsolète après suppression d'un visuel.

Correction attendue :
1. Sur "Training", ouvrir chaque visuel via Format > Modifier les
   interactions et désactiver ("Aucun") ou passer en surbrillance les
   couples de visuels sans lien analytique pertinent.
2. Sur "Overview", nettoyer l'entrée d'interaction obsolète ou la
   reconfigurer si le visuel cible a été remplacé par un autre.
```

---

## 11. Conditions empêchant un faux OK

- toutes les pages du rapport ont été parcourues, y compris les pages masquées pour le contrôle de cohérence des références ;
- pour chaque page, l'inventaire complet des visuels réellement présents a été constitué (pas seulement ceux référencés dans `visualInteractions`) ;
- le nombre de visuels analytiques (hors textbox) de chaque page a été calculé pour appliquer le seuil de densité ;
- chaque page dense dispose d'au moins une entrée `visualInteractions` avec un type traduisant une revue explicite (`None` ou `Highlight`), pas seulement une reconfirmation implicite du `DataFilter` par défaut ;
- aucune entrée `visualInteractions` ne référence un `source` ou un `target` absent de l'inventaire des visuels de la page.

---

## 12. Résumé de la règle

```text
RÈGLE BP-38

POUR chaque page
    CHARGER l'inventaire réel des visuels (visuals/*/visual.json)
    LIRE visualInteractions dans page.json (peut être vide/absent)
    COMPTER les visuels analytiques (hors textbox)

    SI une entrée référence un visuel absent de l'inventaire
        page = KO (référence obsolète)

    SI nb_visuels_analytiques > SEUIL_DENSITE
        SI aucune entrée visualInteractions
            page = KO (aucune revue effectuée)
        SINON SI aucune entrée de type None/Highlight
            page = KO (interactions jamais désactivées explicitement)
        SINON
            page = OK (revue prouvée)
    SINON
        page = OK (page peu dense, revue non indispensable)

    POUR chaque slicer de la page sans entrée d'interaction associée
        page = WARN (à défaut de KO déjà posé) -> recommander une revue humaine ciblée
FIN POUR

SI au moins une page KO
    règle = KO
SINON SI au moins une page WARN
    règle = WARN
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-38 — Élimination des interactions croisées inutiles    │
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
     │  CHARGER inventaire réel des visuels                │
     │  (visuals\*\visual.json)                            │
     │  LIRE visualInteractions dans page.json (peut être  │
     │  vide/absent)                                        │
     │  COMPTER visuels analytiques (hors textbox)          │
     └──────────────┬─────────────────────────────────────┘
                     │
                     ▼
        ┌────────────┴─────────────┐
        ▼                          ▼
 ┌─────────────────────┐   ┌──────────────────────────┐
 │ Entrée référence un  │   │ Toutes les entrées        │
 │ visuel absent de     │   │ référencent des visuels    │
 │ l'inventaire ?       │   │ existants                  │
 └──────────┬────────────┘   └──────────────┬─────────────┘
      ┌──────┴──────┐                       │
      ▼             ▼                       │
╔═══════════╗ ┌─────────────┐               │
║ Oui -> KO ║ │ Non         │               │
║ (référence║ │ (continuer) │               │
║ obsolète) ║ └──────┬──────┘               │
╚═══════════╝        └───────────┬───────────┘
                                  ▼
                    ┌────────────────────────────────┐
                    │ nb_visuels_analytiques > SEUIL   │
                    │ (défaut : 4) ?                   │
                    └──────────────┬────────────────────┘
                          ┌─────────┴─────────┐
                          ▼                    ▼
                  ╔═══════════════╗    ┌───────────────────┐
                  ║ Page dense    ║    │ Page peu dense      │
                  ╚═══════╤═══════╝    │ -> OK implicite     │
                          ▼             └───────────────────┘
              ┌───────────────────────────────┐
              │ Entrée de type "None"/         │
              │ "Highlight" présente ?          │
              └──────────────┬────────────────────┘
                    ┌─────────┴─────────┐
                    ▼                   ▼
             ╔═════════════╗    ┌──────────────────────┐
             ║ Oui -> OK   ║    │ Non (absent ou        │
             ║ (revue      ║    │ jamais désactivé)      │
             ║ prouvée)    ║    │ -> KO                  │
             ╚═════════════╝    └──────────────────────┘
                          │
                          ▼
              ┌────────────────────────────────────┐
              │ Slicer(s) de la page sans entrée     │
              │ d'interaction associée ?             │
              └──────────────┬────────────────────────┘
                    ┌─────────┴─────────┐
                    ▼                   ▼
             ╔═════════════╗    ┌─────────────┐
             ║ Oui -> WARN ║    │ Non          │
             ╚═════════════╝    └─────────────┘
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
║ 1+ page KO  ║ │ 0 KO, 1+     │  │ Aucune page  │
║ (orpheline  ║ │ WARN -> WARN │  │ KO/WARN      │
║ ou dense    ║ └─────────────┘  │ -> OK        │
║ non revue)  ║                  └─────────────┘
║ -> KO       ║
╚═════════════╝
                     │
                     ▼
        RETOUR rule_status (OK/KO/WARN)
```
