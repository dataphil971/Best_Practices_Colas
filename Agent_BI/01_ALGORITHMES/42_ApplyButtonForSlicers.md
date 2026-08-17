# BP-42 — Bouton « Appliquer » pour les pages à segments nombreux

## 1. Objectif de la bonne pratique

Par défaut, chaque changement de sélection sur un segment (slicer) déclenche immédiatement le recalcul de tous les visuels affectés de la page. Sur une page qui compte de nombreux slicers — en particulier lorsqu'ils portent sur des colonnes à forte cardinalité ou alimentent des visuels coûteux (mesures complexes, gros volumes, agrégations multiples) — cette réévaluation immédiate à chaque clic peut dégrader sensiblement la fluidité perçue par l'utilisateur, surtout lorsqu'il ajuste plusieurs filtres successivement avant de vouloir réellement observer le résultat final.

Power BI permet d'activer, sur un slicer, un mode d'application différée : l'utilisateur compose sa sélection puis valide explicitement via un bouton « Appliquer », qui ne déclenche qu'un seul recalcul global au lieu d'un recalcul par clic. L'objectif de cette règle est d'identifier les pages où le nombre de slicers dépasse un seuil justifiant ce mode d'application différée, et de vérifier que ce mode est effectivement activé sur les slicers concernés.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et du nombre de slicers par page ;
- des identifiants techniques hexadécimaux des pages et des visuels ;
- des champs précis utilisés par chaque slicer.

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json   (type de visuel, propriété du mode d'application)
```

Exemple pour ce projet — page « Adoption » (`8ea91dc3e5e5ab0a43ae`), qui compte plusieurs slicers :

```text
AI_BAROMETER_BI-CDS.Report\definition\pages\8ea91dc3e5e5ab0a43ae\visuals\bc4360b7095697643ea5\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\8ea91dc3e5e5ab0a43ae\visuals\d5cc497d6268c0a3700d\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\8ea91dc3e5e5ab0a43ae\visuals\2f4e2e56873505c97e34\visual.json
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1. Identification d'un slicer

```json
{
  "visual": {
    "visualType": "slicer",
    "objects": {
      "data": [ { "properties": { "mode": { "expr": { "Literal": { "Value": "'Basic'" } } } } } ],
      "selection": [ { "properties": { "singleSelect": { "expr": { "Literal": { "Value": "false" } } } } } ],
      "general": [ { "properties": {} } ]
    }
  }
}
```

### 3.2. Mode d'application différée (bouton « Appliquer »)

Le mode d'application différée d'un slicer se pilote via une propriété portée par le bloc `visual.objects` du slicer. **La clé exacte et sa localisation précise sont une propriété à confirmer selon la version du schéma PBIR** : selon les versions observées, elle peut apparaître comme une propriété booléenne dédiée dans le bloc `general` du slicer (forme plausible ci-dessous) plutôt que comme une clé nommée `isInvertedSelectionMode` (qui, dans le schéma des propriétés de sélection Power BI, régit un tout autre comportement — l'inversion de la sélection — et ne doit pas être confondue avec le mode d'application différée) :

```jsonpath
$.visual.objects.general[].properties.isApplyModeEnabled   # forme plausible, à confirmer selon la version du schéma
```

En l'absence de certitude absolue sur le nom exact de cette clé pour la version du schéma du projet audité, l'agent doit :
1. rechercher, de façon tolérante, toute propriété du bloc `objects` du slicer dont le nom contient `apply` (insensible à la casse) ;
2. si aucune propriété de ce type n'est trouvée sur un slicer, considérer par défaut que le mode d'application différée n'est **pas** activé (comportement standard de Power BI Desktop, qui recalcule à chaque clic sauf activation explicite) ;
3. documenter explicitement, dans la preuve technique du résultat, que cette détection repose sur une recherche par mot-clé et non sur une clé garantie, afin qu'une revue humaine puisse confirmer visuellement l'état du bouton « Appliquer » dans Power BI Desktop en cas de doute.

Dans le projet audité, aucune propriété contenant `apply` n'a été trouvée sur les slicers examinés : le mode d'application différée ne semble activé sur aucun slicer du rapport.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Page avec un nombre de slicers inférieur ou égal au seuil (ex. ≤ 3) | `OK` | Le nombre réduit de segments limite l'impact des recalculs successifs ; le mode d'application différée n'est pas indispensable. |
| Page avec un nombre de slicers supérieur au seuil, tous en mode d'application différée détecté | `OK` | Bonne pratique respectée : la page évite les recalculs répétés lors de la composition d'une sélection multi-critères. |
| Page avec un nombre de slicers supérieur au seuil, **aucun** en mode d'application différée | `KO` | Chaque clic sur l'un des nombreux slicers déclenche un recalcul complet de la page, ce qui dégrade l'expérience sur une page à filtrage riche. |
| Page avec un nombre de slicers supérieur au seuil, mode d'application différée activé sur une partie seulement des slicers de la page | `WARN` | Configuration partielle : recommandé d'harmoniser (le gain de fluidité n'est réel que si l'ensemble des slicers de la page bascule ensemble). |
| Détection du mode d'application reposant sur une clé non garantie par le schéma (cf. section 3.2) | — (n'abaisse pas le statut) | À signaler comme information de confiance dans la preuve technique, en recommandant une confirmation visuelle humaine si le statut calculé est `KO`. |

---

## 5. Parcours complet du rapport

### Étape 1 — Localiser toutes les pages et tous les slicers
1. Lire `pages.json` pour la liste complète des pages.
2. Pour chaque page, lister tous les `visual.json` et ne retenir que ceux dont `visual.visualType == "slicer"`.

### Étape 2 — Compter les slicers par page
Pour chaque page, dénombrer ses slicers (visibles et masqués — un slicer masqué, cf. exemple réel de ce projet avec `isHidden: true`, continue de déclencher un recalcul lorsqu'il est piloté via un signet ou une autre interaction).

### Étape 3 — Évaluer le mode d'application pour les pages au-dessus du seuil
Pour chaque page dont le nombre de slicers dépasse le seuil : pour chaque slicer de la page, rechercher une propriété de mode d'application différée ; comparer le nombre de slicers en mode différé au nombre total de slicers de la page.

### Étape 4 — Qualifier la page
1. Aucun slicer en mode différé → `KO`.
2. Tous les slicers en mode différé → `OK`.
3. Une partie seulement → `WARN`.

### Étape 5 — Terminer l'analyse
Parcourir l'intégralité des pages avant de conclure. Produire : le nombre de pages au-dessus du seuil, le détail par page (nombre de slicers, nombre en mode différé), la liste des pages `KO` et `WARN`.

---

## 6. Détection robuste / normalisation

- Le seuil de déclenchement (nombre de slicers à partir duquel le mode différé est recommandé) doit être paramétrable et documenté dans le résultat (valeur par défaut proposée : 4 slicers sur une même page) plutôt que codé en dur sans traçabilité.
- Un même champ utilisé comme slicer sur plusieurs visuels distincts de la même page (rare mais possible) compte pour autant de slicers que d'occurrences, chaque occurrence déclenchant indépendamment un recalcul.
- Les slicers masqués (`isHidden: true`) sont comptés au même titre que les slicers visibles : ils continuent de filtrer et de déclencher des recalculs lorsqu'ils sont pilotés par un signet (cf. [BP-37](37_OrganizeVisualsBookmarks.md)) ou une autre interaction.
- L'absence de toute propriété liée à `apply` sur un slicer ne doit jamais être traitée comme une erreur de lecture (`NA`) : c'est le comportement par défaut d'un slicer non configuré en application différée, donc un signal exploitable pour la règle (`KO`/`WARN` selon le contexte de la page).
- Les pages masquées (`HiddenInViewMode`) sont incluses dans le comptage : une page technique riche en slicers reste soumise à la même recommandation si elle est occasionnellement consultée.
- Étant donné l'incertitude documentée sur le nom exact de la propriété (section 3.2), l'agent doit toujours restituer, dans le message final, une invitation à vérifier visuellement le statut du bouton « Appliquer » dans Power BI Desktop avant de considérer un `KO` comme définitivement acquis.

---

## 7. Pseudo-code détaillé

```python
SLICER_COUNT_THRESHOLD = 4

def detect_apply_mode(slicer_visual_json):
    objects = slicer_visual_json.get("visual", {}).get("objects", {})
    for block_name, block_entries in objects.items():
        for entry in block_entries:
            for prop_name in entry.get("properties", {}).keys():
                if "apply" in prop_name.lower():
                    value = extract_literal_value(entry["properties"][prop_name])
                    return {"detected_key": f"{block_name}.{prop_name}", "value": value}
    return None   # aucune propriété liée à "apply" trouvée : considéré comme mode différé désactivé


def analyze_apply_button_usage(report_path, pages):
    ok_pages, ko_pages, warn_pages = [], [], []

    for page in pages:
        slicers = []
        for vfile in list_visual_json_files(report_path, page.id):
            data = read_json(vfile)
            if data.get("visual", {}).get("visualType") == "slicer":
                slicers.append(data)

        if len(slicers) <= SLICER_COUNT_THRESHOLD:
            continue   # page hors périmètre : peu de slicers, le mode différé n'est pas indispensable

        apply_mode_results = [detect_apply_mode(s) for s in slicers]
        enabled_count = sum(1 for r in apply_mode_results if r and truthy(r["value"]))

        page_summary = {
            "page": page.display_name,
            "slicer_count": len(slicers),
            "apply_mode_enabled_count": enabled_count,
            "detection_confidence": "clé non garantie par le schéma — confirmation visuelle recommandée",
        }

        if enabled_count == 0:
            ko_pages.append({**page_summary, "reason": "Aucun slicer en mode d'application différée"})
        elif enabled_count == len(slicers):
            ok_pages.append(page_summary)
        else:
            warn_pages.append({**page_summary, "reason": "Mode d'application différée partiel sur la page"})

    return ok_pages, ko_pages, warn_pages
```

---

## 8. Calcul du statut global

```python
if ko_pages:
    rule_status = "KO"
elif warn_pages:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Aucune page au-dessus du seuil, ou toutes les pages au-dessus du seuil ont le mode différé activé sur tous leurs slicers | `OK` |
| Au moins une page au-dessus du seuil n'a aucun slicer en mode différé | `KO` |
| Aucun `KO`, mais au moins une page au-dessus du seuil a une activation partielle | `WARN` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-42",
  "rule_name": "Bouton Appliquer pour les pages à segments nombreux",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "slicer_count_threshold": 4,
  "pages_above_threshold": 0,
  "ko_pages": [],
  "warn_pages": []
}
```

Exemple `KO` (situation plausible sur une page riche en slicers de ce projet) :

```json
{
  "rule_id": "BP-42",
  "rule_name": "Bouton Appliquer pour les pages à segments nombreux",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "slicer_count_threshold": 4,
  "pages_above_threshold": 1,
  "ko_pages": [
    {
      "page": "Adoption",
      "slicer_count": 5,
      "apply_mode_enabled_count": 0,
      "reason": "Aucun slicer en mode d'application différée",
      "detection_confidence": "clé non garantie par le schéma — confirmation visuelle recommandée"
    }
  ],
  "warn_pages": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-42 — Bouton Appliquer pour les pages à segments nombreux : OK

Aucune page du rapport ne dépasse le seuil de 4 slicers simultanés. Le mode
d'application différée n'est pas indispensable dans la configuration
actuelle.
```

### Exemple `KO`

```text
BP-42 — Bouton Appliquer pour les pages à segments nombreux : KO

Page "Adoption" : 5 slicers actifs, aucun n'a de mode d'application
différée détecté. Chaque clic sur l'un de ces 5 segments déclenche
immédiatement le recalcul des visuels de la page.

Correction attendue :
activer le mode d'application différée (bouton "Appliquer") sur les 5
slicers de la page "Adoption" via le volet Format du slicer, afin que
l'utilisateur puisse composer sa sélection multi-critères avant de
déclencher un unique recalcul.

Remarque méthodologique : la détection de ce mode repose sur une clé de
schéma non garantie à 100% ; il est recommandé de confirmer visuellement
l'état du bouton "Appliquer" dans Power BI Desktop avant correction.
```

---

## 11. Conditions empêchant un faux OK

- toutes les pages du rapport ont été parcourues et tous les slicers de chaque page recensés, y compris les slicers masqués ;
- le seuil de déclenchement a été appliqué de façon homogène et est documenté dans le résultat ;
- pour chaque page au-dessus du seuil, la recherche de propriété de mode différé a été effectuée sur **chacun** des slicers de la page, pas seulement le premier ;
- la limite de confiance de la détection (clé non garantie par le schéma) a été explicitement signalée, sans jamais affirmer à tort une certitude absolue sur l'état du bouton « Appliquer » ;
- aucune page au-dessus du seuil ne présente une absence totale ou partielle de mode différé.

---

## 12. Résumé de la règle

```text
RÈGLE BP-42

POUR chaque page
    COMPTER les slicers (visibles et masqués)
    SI nb_slicers <= SEUIL
        page hors périmètre -> OK implicite
    SINON
        POUR chaque slicer de la page
            RECHERCHER une propriété liée à "apply" dans visual.objects
        FIN POUR
        SI aucun slicer en mode différé
            page = KO
        SINON SI tous les slicers en mode différé
            page = OK
        SINON
            page = WARN (activation partielle)
FIN POUR

SI au moins une page KO
    règle = KO
SINON SI au moins une page WARN
    règle = WARN
SINON
    règle = OK

RAPPELER que la clé de détection n'est pas garantie par le schéma :
recommander une confirmation visuelle humaine en cas de KO
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-42 — Bouton « Appliquer » pour pages à segments        │
│         nombreux                                                  │
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
     │  COMPTER les slicers (visibles ET masqués)          │
     └──────────────┬─────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ┌───────────────────┐  ╔═══════════════════╗
   │ nb_slicers <=      │  ║ nb_slicers >       ║
   │ SEUIL (défaut : 4) │  ║ SEUIL               ║
   │ -> page hors        │  ╚══════════╤═════════╝
   │ périmètre           │             ▼
   │ (OK implicite)       │  ┌──────────────────────────────┐
   └───────────────────┘  │ POUR chaque slicer de la page   │
                            │  RECHERCHER une propriété        │
                            │  contenant "apply" (tolérant,     │
                            │  clé non garantie par le schéma)  │
                            └──────────────┬───────────────────────┘
                                           ▼
                            ┌──────────────────────────────────┐
                            │ COMPTER slicers en mode différé   │
                            │ vs nombre total de slicers         │
                            └──────────────┬───────────────────────┘
                                           ▼
                                  ┌────────┼─────────┐
                                  ▼         ▼          ▼
                           ╔═══════════╗ ┌─────────┐ ╔═══════════╗
                           ║ Aucun     ║ │ Certains │ ║ Tous       ║
                           ║ slicer    ║ │ slicers  │ ║ slicers    ║
                           ║ en mode   ║ │ seulement│ ║ en mode    ║
                           ║ différé   ║ │          │ ║ différé    ║
                           ║ -> KO     ║ │ -> WARN  │ ║ -> OK      ║
                           ╚═══════════╝ └─────────┘ ╚═══════════╝
                          │
                          ▼
     ┌──────────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL                  │
     │ Priorité : KO > WARN > OK                 │
     │ (WARN = recommandation, confirmation       │
     │  visuelle humaine requise en cas de KO)    │
     └──────────────┬─────────────────────────────┘
                     │
       ┌─────────────┼─────────────────┐
       ▼              ▼                 ▼
╔═════════════╗ ┌─────────────┐  ┌─────────────┐
║ 1+ page KO  ║ │ 0 KO, 1+     │  │ Aucune page  │
║ -> KO       ║ │ WARN -> WARN │  │ KO/WARN      │
╚═════════════╝ └─────────────┘  │ -> OK        │
                                  └─────────────┘
                     │
                     ▼
        RETOUR rule_status (OK/KO/WARN)
        + RAPPEL : validation visuelle humaine recommandée si KO
```
