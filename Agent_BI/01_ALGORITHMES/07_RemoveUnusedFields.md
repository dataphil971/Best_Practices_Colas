# BP-07 — Éliminer les colonnes visibles et inutilisées du modèle

## 1. Objectif de la bonne pratique

Chaque colonne chargée dans un modèle sémantique consomme de la mémoire (dictionnaire de valeurs VertiPaq, index de colonnes), allonge le temps de rafraîchissement, et — lorsqu'elle est **visible** dans le volet des champs — ajoute du bruit pour les utilisateurs qui explorent le modèle en libre-service (Analyse dans Excel, création de rapports personnels). Une colonne visible qui n'est référencée ni par une mesure DAX, ni par un visuel du rapport, ni par une relation, ni par un tri (`sortByColumn`), n'apporte aucune valeur au rapport actuel et devrait être **masquée** (si elle reste potentiellement utile en libre-service) ou **supprimée** (si elle est réellement superflue).

L'objectif de cette règle est d'identifier, pour chaque table du modèle, les colonnes qui cumulent deux caractéristiques : elles sont **visibles** (absence de la propriété `isHidden`) et elles ne sont **référencées nulle part** dans le périmètre analysé (mesures DAX du modèle, visuels et filtres du rapport, relations, tri par colonne). Une colonne masquée mais inutilisée n'est pas un problème de gouvernance de même nature (elle n'encombre pas l'expérience utilisateur) et n'est donc que secondairement signalée.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables et de colonnes ;
- du nom des tables et des colonnes ;
- de l'ordre des propriétés dans les fichiers TMDL ;
- du type de données de la colonne.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl
<REPORT_PATH>\definition\pages\*\visuals\*\visual.json
<REPORT_PATH>\definition\filters.json
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_CAMPAIGNS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\relationships.tmdl
AI_BAROMETER_BI-CDS.Report\definition\pages\*\visuals\*\visual.json
```

L'agent doit charger :

1. tous les fichiers `tables/*.tmdl`, pour lister colonnes et mesures ;
2. `relationships.tmdl`, pour identifier les colonnes utilisées comme clé de relation ;
3. tous les fichiers `visual.json` du rapport (un par visuel, dans chaque sous-dossier de page), pour extraire les champs réellement projetés, filtrés ou triés ;
4. les filtres de niveau page/rapport, généralement décrits dans le même schéma de visuel ou dans un fichier de filtres dédié selon la version du format PBIR.

---

## 3. Élément(s) / propriété(s) à contrôler

Visibilité d'une colonne, contrôlée par l'absence ou la présence de `isHidden` :

```tmdl
column CAMPAIGN_ID
	dataType: string
	isHidden
	lineageTag: b30938a6-aa65-4080-bd83-dd84d12c599d
	summarizeBy: none
	sourceColumn: CAMPAIGN_ID
```

`CAMPAIGN_ID` est **masquée** (`isHidden` présent) : même si elle n'est utilisée que comme clé de relation, elle est hors du périmètre prioritaire de cette règle. À l'inverse :

```tmdl
column CAMPAIGN_LABEL
	dataType: string
	lineageTag: 379b4036-dca5-4e99-a377-15d50ec4ce7c
	summarizeBy: none
	sourceColumn: CAMPAIGN_LABEL
```

`CAMPAIGN_LABEL` n'a pas de propriété `isHidden` : elle est **visible**, et doit donc être recherchée dans les mesures, les visuels et les relations avant de conclure à son utilité.

Référencement recherché :

- dans les mesures DAX : toute occurrence de `Table[Colonne]` dans le corps d'une mesure (`measure ... = ...`) ;
- dans les visuels : les champs déclarés dans les structures `queryRef`/`Column` d'un `visual.json` (axes, légendes, valeurs, info-bulles, tris) ;
- dans les relations : `fromColumn`/`toColumn` de `relationships.tmdl` ;
- dans les propriétés `sortByColumn` d'une autre colonne, qui référence la colonne courante comme colonne de tri.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `D_CAMPAIGNS[CAMPAIGN_LABEL]`, visible, utilisée comme champ de légende dans un visuel de la page 1 | `OK` | Colonne visible et effectivement exploitée par le rapport. |
| `F_RESPONSES[INTEREST_LEVEL]`, visible, référencée par `sortByColumn` d'une autre colonne et utilisée dans un visuel | `OK` | Colonne visible, utilisée à la fois pour le tri et l'affichage. |
| `D_CAMPAIGNS[CAMPAIGN_ID]`, `isHidden` présent, utilisée uniquement comme clé de relation | `NA` | Hors périmètre prioritaire : colonne déjà masquée, gouvernance déjà correcte. |
| Colonne hypothétique `D_USERS[LEGACY_COMMENT_FIELD]`, visible, absente de toute mesure, tout visuel et toute relation | `KO` | Colonne visible mais totalement inutilisée : à masquer ou supprimer. |
| Colonne hypothétique `F_RESPONSES[DEBUG_FLAG]`, visible, utilisée uniquement dans un filtre de page non documenté | `OK` (avec remarque) | Techniquement référencée ; utilité à confirmer manuellement mais la règle automatique ne peut pas conclure à l'inutilité. |
| Colonne dont le référencement n'a pas pu être vérifié (visuel illisible, `visual.json` corrompu) | `NA` | Analyse incomplète sur cette colonne, ne pas conclure. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Charger tous les fichiers `tables/*.tmdl`, `relationships.tmdl`.
2. Lister tous les fichiers `visual.json` sous `<REPORT_PATH>\definition\pages\*\visuals\*\`.
3. Si le dossier `tables/` est introuvable, retourner `NON_EVALUE`.

### Étape 2 — Construire l'inventaire des colonnes visibles
Pour chaque table, pour chaque colonne : déterminer sa visibilité (`isHidden` absent = visible) ; ignorer les colonnes déjà masquées pour la suite du calcul du statut (elles restent inventoriées mais classées `NA`).

### Étape 3 — Construire l'index de référencement
1. Parcourir toutes les mesures DAX de toutes les tables et extraire les références `Table[Colonne]`.
2. Parcourir `relationships.tmdl` et extraire toutes les colonnes utilisées en `fromColumn`/`toColumn`.
3. Parcourir chaque `visual.json` et extraire tous les champs référencés (axes, valeurs, légendes, info-bulles, tris, filtres de niveau visuel).
4. Parcourir les colonnes elles-mêmes pour repérer les propriétés `sortByColumn` qui référencent une autre colonne.

### Étape 4 — Croiser l'inventaire et l'index
Pour chaque colonne visible : vérifier sa présence dans l'index construit à l'étape 3. Marquer `OK` si trouvée au moins une fois, `KO` sinon.

### Étape 5 — Ne pas s'arrêter à la première colonne inutilisée
L'agent analyse l'intégralité des colonnes visibles de toutes les tables, sans interrompre l'analyse après la première anomalie.

### Étape 6 — Terminer l'analyse
Produire : le nombre total de colonnes visibles analysées ; le nombre de colonnes `OK`/`KO`/`NA` ; la liste des colonnes `KO` avec la table d'appartenance ; un résumé du gain de mémoire estimé si les colonnes `KO` étaient masquées ou supprimées (optionnel, si l'agent dispose de statistiques de cardinalité).

---

## 6. Détection robuste / normalisation

**Repérage des références de colonnes dans les mesures DAX** — les colonnes sont référencées sous la forme `NomTable[NomColonne]` ou, dans le contexte de la table elle-même, simplement `[NomColonne]`. L'agent doit résoudre cette forme courte en s'appuyant sur le contexte de la mesure (table hôte) et sur les colonnes réellement disponibles dans les tables filtrées par le contexte DAX environnant, avec une tolérance : en cas de doute, considérer la référence courte comme valide pour toute colonne homonyme du modèle plutôt que de risquer un faux `KO`.

```python
def extract_column_references(dax_body, all_tables):
    qualified = re.findall(r"([A-Za-z_][\w]*)\[([^\]]+)\]", dax_body)  # Table[Colonne]
    refs = {(normalize(t), normalize(c)) for t, c in qualified}
    return refs
```

**Repérage des références dans les visuels** — le format PBIR (`visual.json`) exprime les champs sous forme de structures imbriquées (`prototypeQuery.Select`, `Column.Property`, `Entity`). L'agent doit parcourir récursivement le JSON et collecter toutes les paires `(Entity, Property)` rencontrées, sans dépendre d'un chemin fixe dans l'arborescence JSON (la structure exacte varie selon le type de visuel).

```python
def extract_fields_from_visual(visual_json):
    refs = set()
    def walk(node):
        if isinstance(node, dict):
            if "Entity" in node and "Property" in node:
                refs.add((normalize(node["Entity"]), normalize(node["Property"])))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(visual_json)
    return refs
```

**Normalisation des noms** : comparaison insensible à la casse, suppression des espaces superflus, dépouillement des guillemets simples autour des noms composés (`D_CHOICE.'ID '`).

**Colonnes de tri (`sortByColumn`)** : une colonne visible peut n'être référencée par aucune mesure ni aucun visuel mais rester utile car elle sert de colonne de tri à une autre colonne visible et utilisée (cas de `INTEREST_LEGEND_ORDER`, masquée, qui trie `INTEREST_LEVEL`, visible et utilisée) — dans ce sens, une colonne visible qui **est elle-même** une colonne de tri utilisée doit être considérée comme référencée.

**Filtres de rapport/page** : les filtres définis au niveau rapport ou page (et pas seulement au niveau visuel) doivent être inclus dans l'index de référencement — une colonne uniquement utilisée comme filtre de page reste une colonne utile.

---

## 7. Pseudo-code détaillé

```python
def build_reference_index(tables, relationships, visual_jsons):
    index = set()

    for table in tables:
        for m in table.measures:
            index |= extract_column_references(remove_comments(m.expression), tables)

    for rel in relationships:
        index.add((normalize(rel.from_table), normalize(rel.from_column)))
        index.add((normalize(rel.to_table), normalize(rel.to_column)))

    for table in tables:
        for column in table.columns:
            sort_ref = column.get_property("sortByColumn")
            if sort_ref:
                index.add((normalize(table.name), normalize(sort_ref)))

    for visual_json in visual_jsons:
        index |= extract_fields_from_visual(visual_json)

    return index


def evaluate_column(table, column, reference_index):
    if column.has_property("isHidden"):
        return {"table": table.name, "column": column.name, "status": "NA",
                "reason": "Colonne déjà masquée, hors périmètre prioritaire"}

    key = (normalize(table.name), normalize(column.name))
    if key in reference_index:
        return {"table": table.name, "column": column.name, "status": "OK"}

    return {"table": table.name, "column": column.name, "status": "KO",
            "reason": "Colonne visible non référencée par une mesure, un visuel, une relation ou un tri"}


tables = parse_all_tables(table_files)
relationships = parse_relationships(relationships_file)
visual_jsons = load_all_visual_json(report_path)

if not visual_jsons:
    execution_status = "PARTIAL"   # analyse du modèle possible, analyse du rapport incomplète

reference_index = build_reference_index(tables, relationships, visual_jsons)

results = [
    evaluate_column(table, column, reference_index)
    for table in tables
    for column in table.columns
]
```

---

## 8. Calcul du statut global

```python
if any(r["status"] == "KO" for r in results):
    rule_status = "KO"
elif any(r["status"] == "NA" for r in results and no visual_jsons found):
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK`. Les colonnes déjà masquées, classées `NA` par choix de conception (hors périmètre prioritaire), ne font **pas** basculer le statut global en `NA` : seule l'incapacité à analyser le rapport (aucun `visual.json` accessible) doit produire un statut global `NA`, car dans ce cas les colonnes visibles ne peuvent être validées qu'à moitié (mesures et relations, mais pas usage visuel).

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les colonnes visibles sont référencées quelque part | `OK` |
| Au moins une colonne visible n'est référencée nulle part | `KO` |
| Modèle analysable mais aucun visuel de rapport accessible pour confirmer l'usage | `NA` |
| Colonnes `KO` détectées malgré une analyse partielle du rapport | `KO`, avec analyse partielle signalée |

---

## 9. Structure du résultat

Exemple lorsque toutes les colonnes visibles sont utilisées :

```json
{
  "rule_id": "BP-07",
  "rule_name": "Éliminer les colonnes visibles et inutilisées du modèle",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_columns": 69,
  "hidden_columns": 24,
  "visible_columns": 45,
  "ok_columns": 45,
  "ko_columns": 0,
  "ko_details": []
}
```

Exemple avec colonnes inutilisées :

```json
{
  "rule_id": "BP-07",
  "rule_name": "Éliminer les colonnes visibles et inutilisées du modèle",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_columns": 71,
  "hidden_columns": 24,
  "visible_columns": 47,
  "ok_columns": 45,
  "ko_columns": 2,
  "ko_details": [
    {"table": "D_USERS", "column": "LEGACY_COMMENT_FIELD", "reason": "Non référencée par une mesure, un visuel, une relation ou un tri"},
    {"table": "D_CAMPAIGNS", "column": "CAMPAIGN_INTERNAL_NOTE", "reason": "Non référencée par une mesure, un visuel, une relation ou un tri"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-07 — Colonnes visibles inutilisées : OK

45 colonnes visibles analysées sur 69 colonnes au total (24 déjà
masquées). Toutes les colonnes visibles sont référencées par au
moins une mesure DAX, un visuel du rapport, une relation ou un tri.
```

### Exemple `KO`

```text
BP-07 — Colonnes visibles inutilisées : KO

45 colonnes utilisées sur 47 colonnes visibles analysées.

Colonnes non conformes :
- D_USERS[LEGACY_COMMENT_FIELD] : visible, absente de toute mesure,
  tout visuel et toute relation.
- D_CAMPAIGNS[CAMPAIGN_INTERNAL_NOTE] : visible, absente de toute
  mesure, tout visuel et toute relation.

Correction attendue :
masquer ces colonnes (isHidden) si elles peuvent rester utiles en
libre-service, ou les supprimer du modèle et de la requête Power
Query source si elles sont définitivement obsolètes, afin de réduire
la taille du modèle et la charge cognitive du volet des champs.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- tous les fichiers `tables/*.tmdl` ont été chargés et toutes les colonnes inventoriées avec leur statut de visibilité ;
- `relationships.tmdl` a été chargé pour couvrir le référencement par relation ;
- l'ensemble des fichiers `visual.json` du rapport a été localisé et parsé (si le rapport est indisponible ou partiellement lu, le statut global doit refléter cette limite en `NA`, pas en `OK`) ;
- l'index de référencement croise mesures, relations, tris et visuels avant de conclure sur chaque colonne visible ;
- aucune colonne visible n'a été omise de l'analyse ;
- une colonne visible référencée uniquement par un filtre de page/rapport (et non par un visuel classique) a bien été prise en compte.

L'agent ne doit jamais produire `OK` si l'accès aux fichiers `visual.json` du rapport a échoué ou a été partiel : dans ce cas, l'usage réel des colonnes visibles ne peut être confirmé que partiellement, et le statut global doit être `NA`.

---

## 12. Résumé de la règle

```text
RÈGLE BP-07

CONSTRUIRE l'inventaire de toutes les colonnes de toutes les tables
CONSTRUIRE l'index de référencement :
    POUR chaque mesure DAX -> extraire Table[Colonne]
    POUR chaque relation -> ajouter fromColumn / toColumn
    POUR chaque colonne avec sortByColumn -> ajouter la colonne de tri référencée
    POUR chaque visual.json du rapport -> extraire tous les champs (Entity, Property)

POUR chaque colonne
    SI isHidden présent
        colonne = NA (hors périmètre prioritaire)
    SINON SI colonne présente dans l'index de référencement
        colonne = OK
    SINON
        colonne = KO

    ENREGISTRER le résultat avec preuve
FIN POUR

SI au moins une colonne visible est KO
    règle = KO
SINON SI le rapport n'a pas pu être analysé intégralement
    règle = NA
SINON
    règle = OK

AFFICHER toutes les colonnes KO avec recommandation (masquer ou supprimer)
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-07 — Colonnes visibles et inutilisées du modèle      │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────────┐
          │ Charger tables/*.tmdl              │
          │ Charger relationships.tmdl          │
          │ Lister tous les visual.json du      │
          │ rapport (pages/*/visuals/*)          │
          └──────────────┬────────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ tables/      ║    │ Dossier tables/        │
         ║ trouvé ✅    ║    │ introuvable ❌         │
         ╚════╤════════╝    └──────────┬────────────┘
              │                        ▼
              │                ┌───────────────────┐
              │                │ Retour : NON_EVALUE│
              │                └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ CONSTRUIRE l'index de référencement :       │
   │  - mesures DAX → Table[Colonne]             │
   │  - relations → fromColumn/toColumn          │
   │  - sortByColumn → colonne de tri référencée │
   │  - visual.json → (Entity, Property)          │
   └──────────────────┬──────────────────────────┘
                       ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque colonne de chaque table         │
   │ (boucle, aucune colonne visible omise)      │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ isHidden présent ?                    │
        └───────┬──────────────────┬───────────┘
              oui│                  │non (visible)
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────────┐
         ║ colonne = NA  ║  │ Colonne présente dans        │
         ║ (hors périmètre║  │ l'index de référencement ?   │
         ║  prioritaire)  ║  └───────┬──────────────┬────────┘
         ╚═══════════════╝       oui│                │non
                                     ▼                ▼
                          ╔═══════════════╗  ╔═══════════════╗
                          ║ colonne = OK  ║  ║ colonne = KO  ║
                          ╚═══════════════╝  ╚═══════════════╝
                       │
                       ▼ (ENREGISTRER avec preuve, boucle suivante)
   ┌──────────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL                                │
   │ SI au moins une colonne visible KO    → règle = KO     │
   │ SINON SI aucun visual.json accessible → règle = NA     │
   │        (analyse du rapport incomplète)                 │
   │ SINON                                  → règle = OK    │
   │ (les colonnes déjà masquées, classées NA, ne font       │
   │  JAMAIS basculer le statut global en NA à elles seules) │
   └───────────────────────┬────────────────────────────────┘
                            ▼
                RETOUR rule_status (OK / KO / NA)
```
