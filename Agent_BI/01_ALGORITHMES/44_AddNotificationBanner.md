# BP-44 — Bandeau de notification aux utilisateurs

## 1. Objectif de la bonne pratique

Un rapport Power BI en production évolue dans le temps : limitations connues sur un jeu de données, retard ponctuel de rafraîchissement, maintenance planifiée, changement de méthodologie de calcul. Sans mécanisme de communication intégré au rapport lui-même, ces informations restent portées par des canaux externes (email, Teams) que l'utilisateur qui ouvre le rapport plusieurs semaines plus tard n'a pas nécessairement vus. Un bandeau de notification affiché directement dans le rapport, piloté par une source de données dédiée plutôt que codé en dur, permet de communiquer ces messages au bon moment, sans nécessiter de republier le rapport pour chaque mise à jour du message.

Ce projet dispose déjà, côté modèle sémantique, de deux tables techniques dédiées à ce mécanisme :

- `T_NOTIFICATION` : référentiel des styles de notification (type, couleur du texte, couleur de fond, icône) ;
- `T_NOTIFICATION_TEXT` : contenu des messages, avec un rattachement à une page (`PageNb`) et un statut d'activation (`Status`).

L'objectif de cette règle est de vérifier la **cohérence de bout en bout** entre cette configuration de notification côté modèle et sa restitution effective côté rapport : un message configuré comme actif doit être effectivement affiché par un visuel du rapport, et un visuel de bandeau présent dans le rapport doit être alimenté par une source de notification cohérente.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et de messages de notification configurés ;
- des identifiants techniques hexadécimaux des pages et des visuels ;
- du nom exact donné aux tables de notification, tant que leur rôle peut être identifié.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\T_NOTIFICATION.tmdl          (référentiel de style de notification)
<SEMANTIC_MODEL_PATH>\definition\tables\T_NOTIFICATION_TEXT.tmdl     (contenu des messages, page ciblée, statut)
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json   (visuel de bandeau consommant ces tables)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\T_NOTIFICATION.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\T_NOTIFICATION_TEXT.tmdl
AI_BAROMETER_BI-CDS.Report\definition\pages\81a74ceaa660678035ae\visuals\...\visual.json
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1. Table de configuration du contenu — `T_NOTIFICATION_TEXT`

Extrait réel du modèle audité :

```tmdl
table T_NOTIFICATION_TEXT
    isHidden
    lineageTag: 31516a61-15b6-4f81-ae55-7a333f0b4ee3

    column PageNb
        dataType: int64
        summarizeBy: none
        sourceColumn: PageNb

    column Message
        dataType: string
        summarizeBy: none
        sourceColumn: Message

    column Status
        dataType: string
        summarizeBy: none
        sourceColumn: Status

    partition T_NOTIFICATION_TEXT = m
        mode: import
        source =
            let
                Source = SharePoint.Tables(...),
                #"Filtered Rows" = Table.SelectRows(#"Changed Type",
                    each ([Message] = "Bandeau de notif pour l'update de BAROMETRE IA#(lf) ")),
                #"Removed Other Columns1" = Table.SelectColumns(#"Filtered Rows",
                    {"PageNb", "Message", "Status"})
            in
                #"Removed Other Columns1"
```

Propriétés décisionnelles pour le contrôle depuis le modèle :
- présence des colonnes `PageNb`, `Message`, `Status` (ou équivalents fonctionnels) ;
- la partition M filtre déjà la source sur un message précis (`Table.SelectRows(... [Message] = "..."`) : cela indique que le contenu réel du/des message(s) actifs est piloté en amont (SharePoint) et non visible directement dans le TMDL — l'agent doit donc considérer que **la présence de la table avec cette structure suffit à établir que le mécanisme de configuration existe**, sans pouvoir lire la valeur runtime de `Status` (donnée, pas métadonnée).

### 3.2. Table de style — `T_NOTIFICATION`

```tmdl
table T_NOTIFICATION
    isHidden
    lineageTag: a6d4f545-dd6c-4a11-bc08-49f63c07f561

    column TYPE
        dataType: string
        summarizeBy: none

    column COLOR
        dataType: string
        summarizeBy: none

    column BACKGROUND_COLOR
        dataType: string
        summarizeBy: none

    column ICON
        dataType: string
        summarizeBy: none
```

### 3.3. Visuel de bandeau côté rapport

Un visuel de bandeau de notification consomme typiquement `T_NOTIFICATION_TEXT[Message]` (et parfois `[Status]`) comme champ affiché, filtré sur le numéro de la page courante (`PageNb`), sous forme d'un visuel `textbox` dynamique, d'une carte, ou d'un visuel personnalisé dédié :

```jsonpath
$.visual.query.queryState.*.projections[].field.Column.Expression.SourceRef.Entity == "T_NOTIFICATION_TEXT"
```

ou, pour un textbox à texte dynamique référençant une mesure construite sur cette table :

```jsonpath
$.visual.objects.general[].properties.paragraphs[].textRuns[].value.expr.Measure.Expression.SourceRef.Entity == "T_NOTIFICATION_TEXT"
```

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Tables `T_NOTIFICATION`/`T_NOTIFICATION_TEXT` (ou équivalent fonctionnel) présentes dans le modèle **et** au moins un visuel du rapport référence `T_NOTIFICATION_TEXT` dans ses projections ou son texte dynamique | `OK` | Le mécanisme de notification est configuré de bout en bout : source de données et restitution visuelle sont cohérentes. |
| Tables de notification présentes dans le modèle mais **aucun** visuel du rapport ne les référence | `KO` | Le mécanisme de configuration existe côté modèle mais n'est jamais affiché à l'utilisateur — les messages de notification, quel que soit leur statut, ne peuvent jamais apparaître. |
| Visuel de bandeau détecté dans le rapport (motif de nommage/structure évocateur) référençant une table de notification qui n'existe plus dans le modèle | `KO` | Configuration cassée : le visuel de bandeau ne pourra jamais afficher de contenu (champ inexistant). |
| Aucune table de notification dans le modèle et aucun visuel de bandeau détecté dans le rapport | `NA` | Le mécanisme de notification n'est pas mis en place dans ce projet — hors périmètre, ne peut pas être jugé non conforme par défaut. |
| Table de notification présente mais colonnes clés (`Message`, `Status`, `PageNb` ou équivalents) manquantes | `NA` | Structure de table incomplète, cohérence non déterminable avec cette lecture. |

---

## 5. Parcours complet du rapport

### Étape 1 — Détecter le mécanisme de notification côté modèle
1. Parcourir `<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl`.
2. Identifier toute table dont le nom, les colonnes (`Message`, `Status`, `Type`, `Color`, `Icon`, `PageNb`...) ou le contenu évoquent une fonction de notification/bandeau.
3. Si aucune table de ce type n'est trouvée, noter l'absence et passer directement à l'étape 3 (le mécanisme peut être simplement absent du projet).

### Étape 2 — Qualifier la structure de la table de contenu
Pour la table identifiée comme porteuse du contenu des messages (type `T_NOTIFICATION_TEXT` ou équivalent) : vérifier la présence des colonnes fonctionnellement nécessaires (message, statut d'activation, éventuellement ciblage par page).

### Étape 3 — Localiser tous les visuels du rapport et rechercher une référence à cette table
1. Lire `pages.json` pour la liste complète des pages.
2. Pour chaque page, lister tous les `visual.json`.
3. Pour chaque visuel, rechercher toute référence (`SourceRef.Entity`) à la table de notification identifiée à l'étape 1, dans les projections de requête comme dans les textes dynamiques des textboxes.

### Étape 4 — Croiser les deux constats
1. Table présente + visuel trouvé → `OK`.
2. Table présente + aucun visuel trouvé → `KO`.
3. Visuel de bandeau détecté référençant une table absente → `KO`.
4. Aucune table + aucun visuel de bandeau → `NA`.

### Étape 5 — Terminer l'analyse
Parcourir l'intégralité des tables du modèle et des pages/visuels du rapport avant de conclure. Produire : la table de notification identifiée (le cas échéant), la liste des visuels qui la référencent, le verdict de cohérence.

---

## 6. Détection robuste / normalisation

- Le nom exact des tables de notification n'est pas garanti identique d'un projet à l'autre : l'agent doit identifier leur rôle par un faisceau d'indices (nom de table contenant `NOTIF`, colonnes `Message`/`Status`/`Type`/`Color`/`Icon`), pas par une correspondance exacte de nom.
- Les tables de notification sont typiquement masquées (`isHidden`) dans le modèle : cette propriété ne doit jamais être utilisée pour les exclure de l'analyse, une table technique masquée reste pleinement fonctionnelle.
- Le contenu réel du message (valeur de la colonne `Message` au moment de l'audit) est une **donnée**, pas une métadonnée disponible dans les fichiers TMDL/PBIR : l'agent ne doit jamais tenter d'évaluer si le message actuellement actif est pertinent ou à jour — seule la cohérence structurelle de configuration est du ressort de cette règle statique. L'exactitude du contenu du message reste une vérification humaine.
- Un visuel de bandeau peut être un simple `textbox` avec texte dynamique (mesure DAX affichant le message), un visuel `card`, ou un visuel personnalisé : l'agent doit rechercher la référence à la table de notification dans toutes les structures possibles (`query.queryState`, `objects.general[].properties.paragraphs[].textRuns[].value.expr`), pas uniquement dans les visuels de graphique classiques.
- La détection ne doit pas se limiter à une seule page : un bandeau peut être dupliqué sur chaque page (visuel copié) ou centralisé sur un visuel de mise en page globale — les deux configurations sont valides du point de vue de cette règle.

---

## 7. Pseudo-code détaillé

```python
NOTIFICATION_TABLE_HINTS = re.compile(r"notif", re.IGNORECASE)
NOTIFICATION_COLUMN_HINTS = {"message", "status", "type", "color", "icon", "pagenb", "page"}

def detect_notification_tables(semantic_model_path):
    candidates = []
    for table_file in find_all_tmdl_files(f"{semantic_model_path}/definition/tables/"):
        table = parse_tmdl_table(table_file)
        name_hint = bool(NOTIFICATION_TABLE_HINTS.search(table.name))
        column_names = {c.name.lower() for c in table.columns}
        column_hint_count = len(column_names & NOTIFICATION_COLUMN_HINTS)

        if name_hint or column_hint_count >= 2:
            candidates.append({
                "table": table.name,
                "columns": sorted(column_names),
                "has_message_column": "message" in column_names,
                "has_status_column": "status" in column_names,
            })
    return candidates


def find_visual_references_to_table(report_path, pages, table_name):
    references = []
    for page in pages:
        for vfile in list_visual_json_files(report_path, page.id):
            data = read_json(vfile)
            if references_entity(data, table_name):
                references.append({"page": page.display_name, "visual_id": data.get("name")})
    return references


def references_entity(visual_json, table_name):
    serialized = to_searchable_text(visual_json)   # parcours récursif de toutes les clés SourceRef.Entity
    return contains_entity_reference(serialized, table_name)


def analyze_notification_banner(report_path, semantic_model_path, pages):
    candidate_tables = detect_notification_tables(semantic_model_path)

    if not candidate_tables:
        visual_banner_hints = find_visuals_with_banner_pattern(report_path, pages)
        if not visual_banner_hints:
            return {"execution_status": "SUCCESS", "rule_status": "NA",
                     "reason": "Aucun mécanisme de notification détecté (ni table modèle, ni visuel)"}
        return {"execution_status": "SUCCESS", "rule_status": "KO",
                "reason": "Visuel évoquant un bandeau détecté sans table de notification correspondante dans le modèle",
                "visual_hints": visual_banner_hints}

    content_table = next((t for t in candidate_tables if t["has_message_column"]), None)
    if content_table is None:
        return {"execution_status": "PARTIAL", "rule_status": "NA",
                "reason": "Table(s) de notification trouvée(s) mais colonne Message absente",
                "candidate_tables": candidate_tables}

    references = find_visual_references_to_table(report_path, pages, content_table["table"])

    if not references:
        return {"execution_status": "SUCCESS", "rule_status": "KO",
                "reason": "Table de notification configurée mais jamais affichée par aucun visuel du rapport",
                "content_table": content_table["table"]}

    return {"execution_status": "SUCCESS", "rule_status": "OK",
            "content_table": content_table["table"],
            "displaying_visuals": references}
```

---

## 8. Calcul du statut global

```python
if content_table_missing_columns or unresolvable_banner_visual:
    rule_status = "NA"
elif no_notification_mechanism_found:
    rule_status = "NA"
elif table_present_but_never_displayed or visual_references_missing_table:
    rule_status = "KO"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Table de notification présente et effectivement affichée par au moins un visuel | `OK` |
| Table de notification présente mais jamais référencée par aucun visuel du rapport | `KO` |
| Visuel évoquant un bandeau présent mais référençant une table de notification inexistante | `KO` |
| Structure de table incomplète (colonne message absente) | `NA` |
| Aucun mécanisme de notification détecté ni côté modèle ni côté rapport | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-44",
  "rule_name": "Bandeau de notification aux utilisateurs",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "content_table": "T_NOTIFICATION_TEXT",
  "style_table": "T_NOTIFICATION",
  "displaying_visuals": [
    {"page": "Overview", "visual_id": "77409654e8336b4b1844"}
  ]
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-44",
  "rule_name": "Bandeau de notification aux utilisateurs",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "content_table": "T_NOTIFICATION_TEXT",
  "style_table": "T_NOTIFICATION",
  "displaying_visuals": [],
  "reason": "Table de notification configurée mais jamais affichée par aucun visuel du rapport"
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-44 — Bandeau de notification aux utilisateurs : OK

Le mécanisme de notification est cohérent de bout en bout : les tables
T_NOTIFICATION_TEXT (contenu) et T_NOTIFICATION (style) sont présentes dans
le modèle sémantique, et le visuel "77409654e8336b4b1844" de la page
"Overview" référence T_NOTIFICATION_TEXT pour afficher son contenu.

Rappel : le contenu et la pertinence actuelle du message affiché sont des
données runtime non vérifiables depuis les fichiers du projet — seule la
cohérence de configuration est couverte par ce contrôle.
```

### Exemple `KO`

```text
BP-44 — Bandeau de notification aux utilisateurs : KO

Les tables T_NOTIFICATION_TEXT et T_NOTIFICATION sont présentes dans le
modèle sémantique et correctement structurées (colonnes Message, Status,
PageNb, Type, Color, Icon), mais aucun visuel du rapport ne référence
T_NOTIFICATION_TEXT dans ses projections ou son texte dynamique.

Le mécanisme de notification est donc configuré côté modèle mais invisible
pour l'utilisateur final : quel que soit le statut ou le contenu du message
préparé, il ne peut actuellement jamais s'afficher.

Correction attendue :
ajouter un visuel de bandeau (textbox à texte dynamique ou visuel dédié) sur
la ou les pages concernées, alimenté par une mesure basée sur
T_NOTIFICATION_TEXT[Message], filtrée sur le statut actif et, le cas
échéant, sur le numéro de page courante.
```

---

## 11. Conditions empêchant un faux OK

- l'ensemble des tables du modèle sémantique a été parcouru pour identifier toute table jouant un rôle de notification, sans se limiter à une correspondance de nom exacte ;
- la table de contenu identifiée dispose bien d'une colonne assimilable à un message ;
- l'ensemble des pages et des visuels du rapport a été parcouru pour rechercher une référence à cette table, y compris dans les textes dynamiques de textbox et pas seulement dans les projections de requête classiques ;
- au moins un visuel référençant effectivement la table de notification a été identifié ;
- aucune référence à une table de notification inexistante n'a été détectée côté rapport.

L'agent ne doit jamais conclure `OK` sur la seule présence de la table côté modèle, ni sur la seule présence d'un visuel qui « ressemble » à un bandeau sans confirmer sa référence technique à la table de contenu.

---

## 12. Résumé de la règle

```text
RÈGLE BP-44

RECHERCHER dans le modèle sémantique toute table évoquant un mécanisme de
notification (nom + colonnes Message/Status/Type/Color/Icon/PageNb)

SI aucune table trouvée
    RECHERCHER dans le rapport un visuel évoquant un bandeau
    SI trouvé -> règle = KO (visuel sans configuration modèle)
    SINON -> règle = NA (mécanisme absent du projet, hors périmètre)

SINON
    IDENTIFIER la table de contenu (colonne Message)
    SI colonne Message absente -> règle = NA (structure incomplète)

    SINON
        POUR chaque page, chaque visuel du rapport
            RECHERCHER une référence à la table de notification
        FIN POUR

        SI au moins un visuel référence la table
            règle = OK
        SINON
            règle = KO (configuré mais jamais affiché)
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-44 — Bandeau de notification aux utilisateurs          │
└────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────────────┐
     │ RECHERCHER dans tables\*.tmdl toute table           │
     │ évoquant un mécanisme de notification               │
     │ (nom contient "notif" OU >= 2 colonnes parmi          │
     │ Message/Status/Type/Color/Icon/PageNb)                │
     └──────────────┬─────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ┌───────────────────┐  ╔═══════════════════╗
   │ Aucune table       │  ║ Table(s) trouvée(s) ║
   │ trouvée             │  ╚══════════╤═════════╝
   └──────────┬───────────┘             ▼
              ▼                ┌──────────────────────────────┐
   ┌───────────────────────┐   │ IDENTIFIER la table de         │
   │ RECHERCHER dans le      │   │ contenu (colonne Message)      │
   │ rapport un visuel        │   └──────────────┬────────────────────┘
   │ évoquant un bandeau      │                  ▼
   └──────────┬───────────────┘         ┌────────┴─────────┐
      ┌───────┴───────┐                 ▼                   ▼
      ▼               ▼          ╔═════════════╗    ┌─────────────────┐
╔═══════════╗  ┌─────────────┐   ║ Colonne      ║    │ Colonne Message  │
║ Visuel     ║  │ Aucun        │   ║ Message      ║    │ absente          │
║ trouvé     ║  │ visuel       │   ║ présente     ║    │ -> NA (structure │
║ -> KO      ║  │ -> NA (hors  │   ╚══════╤═══════╝    │ incomplète)      │
║ (config.   ║  │ périmètre)   │          ▼             └─────────────────┘
║ manquante) ║  └─────────────┘  ┌──────────────────────────────┐
╚═══════════╝                    │ POUR chaque page, chaque      │
                                  │ visuel du rapport               │
                                  │ RECHERCHER une référence à la  │
                                  │ table de notification           │
                                  │ (projections + textes           │
                                  │ dynamiques de textbox)          │
                                  └──────────────┬────────────────────┘
                                                 ▼
                                        ┌────────┴─────────┐
                                        ▼                   ▼
                                 ╔═════════════╗    ┌─────────────────┐
                                 ║ 1+ visuel    ║    │ Aucun visuel     │
                                 ║ référence la ║    │ ne référence     │
                                 ║ table -> OK  ║    │ la table -> KO   │
                                 ╚═════════════╝    │ (configuré mais  │
                                                      │ jamais affiché) │
                                                      └─────────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL                  │
     │ Priorité : NA (structure/absence) > KO > OK│
     │ (NA prime dès que la structure ne permet   │
     │  pas de conclure)                          │
     └──────────────┬─────────────────────────────┘
                     │
    ┌────────────────┼─────────────────┬───────────────┐
    ▼                ▼                 ▼                ▼
╔═════════╗   ┌─────────────┐   ┌─────────────┐  ┌─────────────┐
║ Table     ║   │ Structure    │   │ Visuel/table │  │ Table +      │
║ présente, ║   │ incomplète   │   │ manquant(e)  │  │ visuel       │
║ jamais    ║   │ OU mécanisme │   │ -> KO        │  │ cohérents    │
║ affichée  ║   │ absent -> NA │   │              │  │ -> OK        │
║ -> KO     ║   └─────────────┘   └─────────────┘  └─────────────┘
╚═════════╝
                     │
                     ▼
        RETOUR rule_status (OK/KO/NA)
```
