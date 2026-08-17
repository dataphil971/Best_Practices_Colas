# BP-40 — Synchronisation des segments (slicers) entre pages

## 1. Objectif de la bonne pratique

Lorsqu'un même champ (ex. `D_USERS[USER_JOB]`) est utilisé comme segment (slicer) sur plusieurs pages d'un rapport, l'utilisateur s'attend naturellement à ce que sa sélection reste appliquée lorsqu'il navigue d'une page à l'autre. Sans synchronisation explicite via le panneau « Sync slicers » de Power BI, chaque occurrence du slicer conserve un état de sélection indépendant : un utilisateur qui filtre sur un poste donné sur la page « Vue d'ensemble » puis navigue vers la page « Détail » verra le slicer de cette seconde page réinitialisé, sans feedback visuel expliquant la perte de sa sélection. Ce comportement est une source fréquente de confusion et de perte de confiance dans les chiffres affichés (« pourquoi les chiffres ont changé en changeant de page ? »).

L'objectif de cette règle est de détecter les champs utilisés comme slicer sur plusieurs pages **sans** configuration de synchronisation associée, et de recommander soit la mise en place d'une synchronisation, soit une justification explicite de son absence (slicers volontairement indépendants selon le contexte de chaque page).

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et du nombre de slicers ;
- des identifiants techniques hexadécimaux des pages et des visuels ;
- du champ précis utilisé comme slicer (dimension utilisateur, dimension temporelle, dimension organisationnelle...).

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json   (slicers : visualType = "slicer", champ filtré)
<REPORT_PATH>\definition\pages\<pageId>\page.json                        (configuration de synchronisation des slicers, propriété à confirmer selon la version du schéma)
```

Exemple pour ce projet — le champ `D_USERS[USER_JOB]` est utilisé comme slicer sur au moins 7 des 8 pages du rapport :

```text
AI_BAROMETER_BI-CDS.Report\definition\pages\13e9e9fd2ae0e0e76591\visuals\680df9884e2991194178\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\23ff3fc10a020bb396d9\visuals\00f255b4b45ea6d983c6\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\58f1021603e406d600b2\visuals\94a7efa85053659a9330\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\681281ba4317edab1379\visuals\140392de704121556da6\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\6d13bf2424ca09747390\visuals\b47dd7660409c14d2c95\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\81a74ceaa660678035ae\visuals\77409654e8336b4b1844\visual.json
AI_BAROMETER_BI-CDS.Report\definition\pages\8ea91dc3e5e5ab0a43ae\visuals\bc4360b7095697643ea5\visual.json
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1. Identification d'un slicer et de son champ

```json
{
  "name": "680df9884e2991194178",
  "visual": {
    "visualType": "slicer",
    "query": {
      "queryState": {
        "Values": {
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
        }
      }
    }
  }
}
```

Propriété décisionnelle pour l'identification : `visual.visualType == "slicer"`, puis `visual.query.queryState.Values.projections[0].field` résolu en couple `(Entity, Property)` — ici `D_USERS.USER_JOB`.

### 3.2. Configuration de synchronisation

La synchronisation des slicers (groupe de synchronisation, portée « toutes les pages » / « pages sélectionnées », visibilité du slicer sur les pages synchronisées) est pilotée par le panneau « Sync slicers » de Power BI Desktop. Dans le format PBIR, cette configuration est rattachée soit au visuel du slicer, soit à la page — **la clé exacte et son emplacement précis sont une propriété à confirmer selon la version du schéma** ; l'agent doit rechercher, de façon tolérante, toute clé contenant `sync` (ex. `syncGroup`, `syncSlicer`) dans les fichiers `visual.json` des slicers identifiés, plutôt que de présumer un chemin unique figé :

```jsonpath
$.visual.syncGroup.groupName          # forme plausible, à confirmer
$.visual.syncGroup.syncFilterState    # portée de synchronisation (sélection) et de visibilité
```

Dans le projet audité, aucune occurrence de clé contenant `sync` n'a été trouvée dans les fichiers `visual.json`, ce qui indique qu'aucun des slicers du rapport n'est actuellement synchronisé entre les pages.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Champ utilisé comme slicer sur une seule page | `OK` | Aucune ambiguïté possible : la synchronisation n'a pas de sens pour un slicer présent sur une seule page. |
| Champ utilisé comme slicer sur plusieurs pages, avec une configuration de synchronisation détectée couvrant ces pages | `OK` | Cohérence de sélection garantie lors de la navigation. |
| Champ utilisé comme slicer sur plusieurs pages, **sans** aucune configuration de synchronisation détectée | `WARN` | Recommandation : synchroniser (ou documenter explicitement pourquoi les slicers doivent rester indépendants). Non bloquant car un cloisonnement volontaire par page peut être un choix de conception légitime. |
| Champ utilisé comme slicer sur plusieurs pages, avec synchronisation détectée mais ne couvrant qu'un sous-ensemble des pages concernées | `KO` | Configuration incohérente : certaines pages sont synchronisées, d'autres non, pour le même champ — comportement imprévisible pour l'utilisateur. |
| Slicer dont le champ ne peut pas être résolu (structure `query.queryState` absente ou non standard) | `NA` | Slicer non analysable avec cette lecture (ex. slicer avec paramètre, slicer hiérarchique complexe). |

---

## 5. Parcours complet du rapport

### Étape 1 — Localiser toutes les pages et tous les slicers
1. Lire `pages.json` pour la liste complète des pages.
2. Pour chaque page, lister tous les fichiers `visual.json` et ne retenir que ceux dont `visual.visualType == "slicer"`.

### Étape 2 — Résoudre le champ de chaque slicer
Pour chaque slicer : extraire le couple `(Entity, Property)` depuis `query.queryState` ; si non résolvable, classer `NA` et continuer.

### Étape 3 — Regrouper les slicers par champ filtré
Constituer, pour chaque couple `(Entity, Property)` rencontré, la liste des pages sur lesquelles ce champ est utilisé comme slicer.

### Étape 4 — Évaluer chaque champ utilisé sur plusieurs pages
1. Si le champ n'apparaît que sur une seule page, ignorer (hors périmètre, implicitement `OK`).
2. Si le champ apparaît sur plusieurs pages, rechercher une configuration de synchronisation sur chacun des slicers concernés.
3. Comparer l'ensemble des pages couvertes par la synchronisation à l'ensemble des pages où le champ est utilisé comme slicer.

### Étape 5 — Terminer l'analyse
Parcourir l'intégralité des pages et de leurs slicers avant de conclure. Produire : la liste des champs slicers multi-pages synchronisés (`OK`), non synchronisés (`WARN`), partiellement synchronisés (`KO`), et les slicers non analysables (`NA`).

---

## 6. Détection robuste / normalisation

- Les identifiants de page et de visuel sont des chaînes hexadécimales opaques : seuls les couples `(Entity, Property)` et les `displayName` de page doivent apparaître dans les messages restitués.
- L'absence de toute clé `sync*` dans un `visual.json` de slicer n'est pas une erreur de lecture : c'est l'état par défaut (« non synchronisé ») d'un slicer.
- Deux slicers peuvent porter sur le même champ métier mais avec un `nativeQueryRef` ou un libellé de titre différent : la comparaison doit se faire strictement sur le couple technique `(Entity, Property)`, jamais sur le titre affiché du visuel (`visualContainerObjects.title`), qui peut varier d'une page à l'autre sans changer le champ réellement filtré.
- Un slicer masqué (`isHidden: true` au niveau du conteneur, cf. exemple réel du projet) reste pris en compte dans le regroupement par champ : un slicer caché mais actif continue de filtrer et doit être synchronisé au même titre qu'un slicer visible.
- Les pages masquées (`HiddenInViewMode`) sont incluses dans le regroupement par champ mais peuvent être signalées séparément, une page technique n'ayant pas toujours vocation à partager l'état de sélection avec les pages de navigation utilisateur.

---

## 7. Pseudo-code détaillé

```python
def resolve_slicer_field(visual_json):
    try:
        projections = visual_json["visual"]["query"]["queryState"]["Values"]["projections"]
        field = projections[0]["field"]
        if "Column" in field:
            entity = field["Column"]["Expression"]["SourceRef"]["Entity"]
            return f"{entity}.{field['Column']['Property']}"
        if "Measure" in field:
            entity = field["Measure"]["Expression"]["SourceRef"]["Entity"]
            return f"{entity}.{field['Measure']['Property']}"
    except (KeyError, IndexError):
        return None
    return None


def detect_sync_config(visual_json):
    for key in visual_json.get("visual", {}).keys():
        if "sync" in key.lower():
            return visual_json["visual"][key]
    return None


def analyze_slicer_synchronization(report_path, pages):
    slicers_by_field = {}   # field_ref -> [{"page": ..., "visual_id": ..., "sync": ...}]
    na_slicers = []

    for page in pages:
        for vfile in list_visual_json_files(report_path, page.id):
            data = read_json(vfile)
            if data.get("visual", {}).get("visualType") != "slicer":
                continue

            field_ref = resolve_slicer_field(data)
            if field_ref is None:
                na_slicers.append({"page": page.display_name, "visual_id": data["name"]})
                continue

            sync_config = detect_sync_config(data)
            slicers_by_field.setdefault(field_ref, []).append({
                "page": page.display_name, "page_id": page.id,
                "visual_id": data["name"], "sync_config": sync_config,
            })

    ok_fields, warn_fields, ko_fields = [], [], []

    for field_ref, occurrences in slicers_by_field.items():
        if len(occurrences) <= 1:
            continue   # slicer sur une seule page : hors périmètre de la synchronisation

        synced_pages = {o["page_id"] for o in occurrences if o["sync_config"]}
        all_pages = {o["page_id"] for o in occurrences}

        if not synced_pages:
            warn_fields.append({
                "field": field_ref,
                "pages": [o["page"] for o in occurrences],
                "reason": "Champ slicer présent sur plusieurs pages, aucune synchronisation détectée",
            })
        elif synced_pages == all_pages:
            ok_fields.append({"field": field_ref, "pages": [o["page"] for o in occurrences]})
        else:
            ko_fields.append({
                "field": field_ref,
                "synced_pages": [p for p in occurrences if p["page_id"] in synced_pages],
                "unsynced_pages": [p for p in occurrences if p["page_id"] not in synced_pages],
                "reason": "Synchronisation partielle : incohérente entre pages",
            })

    return ok_fields, warn_fields, ko_fields, na_slicers
```

---

## 8. Calcul du statut global

```python
if ko_fields:
    rule_status = "KO"
elif na_slicers:
    rule_status = "NA"
elif warn_fields:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Tous les champs slicers multi-pages sont soit synchronisés intégralement, soit présents sur une seule page | `OK` |
| Au moins un champ est synchronisé sur un sous-ensemble incohérent des pages où il est utilisé | `KO` |
| Au moins un slicer n'a pas pu être résolu | `NA` |
| Aucun `KO`, mais au moins un champ multi-pages n'est jamais synchronisé | `WARN` |

---

## 9. Structure du résultat

Exemple `WARN` (situation réelle observée sur ce projet) :

```json
{
  "rule_id": "BP-40",
  "rule_name": "Synchronisation des segments (slicers) entre pages",
  "execution_status": "SUCCESS",
  "rule_status": "WARN",
  "multi_page_slicer_fields": 1,
  "ok_fields": [],
  "warn_fields": [
    {
      "field": "D_USERS.USER_JOB",
      "pages": ["About", "Perception", "Training", "Knowledge", "Usage", "Overview", "Adoption"],
      "reason": "Champ slicer présent sur plusieurs pages, aucune synchronisation détectée"
    }
  ],
  "ko_fields": [],
  "na_slicers": []
}
```

Exemple `KO` (synchronisation partielle) :

```json
{
  "rule_id": "BP-40",
  "rule_name": "Synchronisation des segments (slicers) entre pages",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "multi_page_slicer_fields": 1,
  "ok_fields": [],
  "warn_fields": [],
  "ko_fields": [
    {
      "field": "D_USERS.USER_JOB",
      "synced_pages": ["Overview", "Perception"],
      "unsynced_pages": ["Training", "Knowledge", "Usage", "Adoption", "About"],
      "reason": "Synchronisation partielle : incohérente entre pages"
    }
  ],
  "na_slicers": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `WARN`

```text
BP-40 — Synchronisation des segments (slicers) entre pages : WARN

Le champ D_USERS.USER_JOB est utilisé comme slicer sur 7 des 8 pages du
rapport (About, Perception, Training, Knowledge, Usage, Overview, Adoption),
sans aucune configuration de synchronisation détectée.

Un utilisateur qui filtre sur un métier donné dans une page verra ce filtre
réinitialisé en naviguant vers une autre page, ce qui peut être perçu comme
une incohérence des chiffres affichés.

Recommandation :
activer la synchronisation de ces slicers via le panneau "Sync slicers"
(Affichage > Sync slicers) sur les 7 pages concernées, sauf si
l'indépendance de la sélection par page est un choix de conception
délibéré — auquel cas il est recommandé de le documenter.
```

### Exemple `KO`

```text
BP-40 — Synchronisation des segments (slicers) entre pages : KO

Le champ D_USERS.USER_JOB est synchronisé entre les pages "Overview" et
"Perception", mais pas avec les pages "Training", "Knowledge", "Usage",
"Adoption" et "About", où le même champ est également utilisé comme slicer.

Cette configuration partielle est incohérente : elle laisse penser que la
synchronisation est active partout, alors qu'elle ne l'est que sur deux
pages sur sept.

Correction attendue :
étendre le groupe de synchronisation existant à l'ensemble des pages où
D_USERS.USER_JOB est utilisé comme slicer, ou retirer la synchronisation
partielle si elle n'est pas un choix assumé.
```

---

## 11. Conditions empêchant un faux OK

- toutes les pages du rapport ont été parcourues et tous les slicers (`visualType: "slicer"`) recensés, y compris les slicers masqués (`isHidden: true`) ;
- le champ filtré de chaque slicer a été résolu vers un couple `(Entity, Property)` technique, jamais déduit du titre affiché du visuel ;
- les slicers ont été regroupés par champ filtré sur l'ensemble du rapport, pas page par page isolément ;
- pour chaque champ utilisé sur plusieurs pages, la configuration de synchronisation de **chacune** des occurrences a été vérifiée, pas seulement la première rencontrée ;
- aucun champ multi-pages ne présente de synchronisation partielle (couvrant certaines pages mais pas d'autres).

---

## 12. Résumé de la règle

```text
RÈGLE BP-40

POUR chaque page
    POUR chaque visual.json de type "slicer"
        RÉSOUDRE le champ filtré (Entity.Property)
        DÉTECTER une éventuelle configuration de synchronisation
        REGROUPER par champ filtré
    FIN POUR
FIN POUR

POUR chaque champ filtré utilisé sur plusieurs pages
    SI aucune synchronisation détectée sur aucune occurrence
        champ = WARN (synchronisation recommandée)
    SINON SI synchronisation présente sur toutes les pages concernées
        champ = OK
    SINON (synchronisation présente sur une partie seulement)
        champ = KO (configuration incohérente)

SI au moins un champ KO
    règle = KO
SINON SI slicers non résolvables
    règle = NA
SINON SI au moins un champ WARN
    règle = WARN
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-40 — Synchronisation des segments (slicers)            │
│         entre pages                                               │
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
     │  POUR chaque visual.json de type "slicer"           │
     │   RÉSOUDRE le champ filtré (Entity.Property)         │
     │   DÉTECTER une éventuelle clé "sync*"                │
     └──────────────┬─────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ╔═════════════╗       ┌───────────────────┐
   ║ Champ        ║       │ Champ non          │
   ║ résolu       ║       │ résolvable -> NA   │
   ╚══════╤══════╝       └───────────────────┘
          ▼
 ┌────────────────────────────────────────┐
 │ REGROUPER les slicers par champ filtré  │
 │ sur l'ensemble du rapport                │
 └──────────────┬───────────────────────────┘
                ▼
       ┌────────┴─────────┐
       ▼                   ▼
╔═════════════════╗  ┌─────────────────────┐
║ Champ présent    ║  │ Champ présent sur    │
║ sur 1 seule page ║  │ plusieurs pages      │
║ -> hors périmètre║  └──────────┬────────────┘
║ (OK implicite)   ║             ▼
╚═════════════════╝     ┌────────────────────────────┐
                         │ Sync détectée sur QUELLES   │
                         │ pages parmi celles où le     │
                         │ champ est utilisé ?          │
                         └──────────────┬─────────────────┘
                              ┌──────────┼──────────┐
                              ▼          ▼           ▼
                       ╔═══════════╗ ┌─────────┐ ╔═══════════╗
                       ║ Aucune    ║ │ Toutes  │ ║ Une partie ║
                       ║ page      ║ │ les     │ ║ seulement  ║
                       ║ synchro   ║ │ pages   │ ║            ║
                       ║ -> WARN   ║ │ -> OK   │ ║ -> KO      ║
                       ╚═══════════╝ └─────────┘ ╚═══════════╝
                          (à documenter/                (config.
                           synchroniser)                 incohérente)
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
║ 1+ champ ║   │ 1+ slicer    │   │ 1+ champ     │  │ Tous les     │
║ KO       ║   │ non résolu   │   │ WARN, 0 KO   │  │ champs OK    │
║ -> KO    ║   │ -> NA        │   │ -> WARN      │  │ -> OK        │
╚═════════╝   └─────────────┘   └─────────────┘  └─────────────┘
                     │
                     ▼
        RETOUR rule_status (OK/KO/NA/WARN)
```
