# BP-39 — Configuration et test systématique des filtres (page, visuel, rapport)

## 1. Objectif de la bonne pratique

Power BI permet de définir des filtres à trois niveaux emboîtés : au niveau du rapport entier (`report.json`), au niveau d'une page (`page.json` → `filterConfig`) et au niveau d'un visuel individuel (`visual.json` → `filterConfig`). Ces filtres référencent des colonnes ou des mesures du modèle sémantique par leur nom technique (`Entity`/`Property`). Un filtre mal configuré — colonne renommée ou supprimée côté modèle, mesure déplacée, condition de filtre incohérente — ne provoque pas toujours une erreur visible immédiatement : le visuel peut simplement s'afficher vide ou incohérent, ce que l'utilisateur final interprète à tort comme une absence de données plutôt que comme un défaut de configuration.

L'objectif de cette règle est de vérifier, de façon croisée entre le rapport et le modèle sémantique, que :

- chaque filtre (page, visuel, rapport) référence une colonne ou une mesure qui **existe réellement** dans le modèle sémantique ;
- aucun visuel ne cumule, sur un même champ, des filtres aux niveaux page/visuel/rapport qui s'excluent mutuellement (ex. un filtre de page qui n'autorise que la valeur `"2024"` et un filtre de visuel qui exclut explicitement `"2024"`), ce qui viderait silencieusement le visuel de toute donnée.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages, de visuels et de filtres ;
- des identifiants techniques hexadécimaux des pages, visuels et filtres ;
- du type de filtre (catégoriel, avancé, top N, relatif à une date...).

---

## 2. Emplacement des fichiers concernés

```text
<REPORT_PATH>\definition\report.json                                      (filtres de niveau rapport)
<REPORT_PATH>\definition\pages\<pageId>\page.json                          (filtres de niveau page — filterConfig)
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json     (filtres de niveau visuel — filterConfig)
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl                             (référentiel des colonnes/mesures existantes)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.Report\definition\report.json
AI_BAROMETER_BI-CDS.Report\definition\pages\13e9e9fd2ae0e0e76591\page.json          (filtre de page sur T_PAGE_NUMBER)
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\T_PAGE_NUMBER.tmdl
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1. Filtre de page — `page.json.filterConfig`

Extrait réel du projet (page « About »), filtre catégoriel sur `T_PAGE_NUMBER[PAGE_NUMBER]` :

```json
{
  "filterConfig": {
    "filters": [
      {
        "name": "7f8927468d4db8ab6516",
        "field": {
          "Column": {
            "Expression": { "SourceRef": { "Entity": "T_PAGE_NUMBER" } },
            "Property": "PAGE_NUMBER"
          }
        },
        "type": "Categorical",
        "filter": {
          "Version": 2,
          "From": [{ "Name": "t", "Entity": "T_PAGE_NUMBER", "Type": 0 }],
          "Where": [{
            "Condition": {
              "In": {
                "Expressions": [{ "Column": { "Expression": { "SourceRef": { "Source": "t" } }, "Property": "PAGE_NUMBER" } }],
                "Values": [[{ "Literal": { "Value": "0L" } }]]
              }
            }
          }]
        },
        "howCreated": "User"
      }
    ]
  }
}
```

Propriétés décisionnelles :
- `filters[].field.Column.Expression.SourceRef.Entity` + `filters[].field.Column.Property` (ou l'équivalent `Measure` pour un filtre sur une mesure) : couple `(Table, Champ)` à valider contre le modèle.
- `filters[].filter.Where[].Condition` : structure logique de la condition (`In`, `Not`, `Comparison`...), utilisée pour la détection de contradiction inter-niveaux (section 4).

### 3.2. Filtre de visuel — `visual.json.filterConfig`

Structure identique à celle de la page, imbriquée dans le bloc `visual` du fichier `visual.json` :

```jsonpath
$.visual.filterConfig.filters[]
```

### 3.3. Filtre de rapport — `report.json`

```jsonpath
$.filterConfig.filters[]
```

Propriété à confirmer selon la version du schéma : la clé racine exacte portant les filtres globaux du rapport dans `report.json` peut varier (`filterConfig` au même niveau que celui des pages, ou une clé dédiée) ; l'agent doit rechercher, de façon tolérante, toute occurrence de `filterConfig.filters[]` à la racine de `report.json`.

### 3.4. Référentiel du modèle sémantique

Pour valider l'existence d'un champ référencé, l'agent doit disposer de l'inventaire des colonnes et mesures du modèle (cf. méthode de parcours des tables TMDL décrite dans [BP-22](22_DisableSummarization.md)) :

```text
<SEMANTIC_MODEL_PATH>\definition\tables\<NomTable>.tmdl   → colonnes (column <Nom>) et mesures (measure <Nom>)
```

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Filtre (page/visuel/rapport) dont le couple `(Entity, Property)` correspond à une colonne ou une mesure existante du modèle | `OK` | Filtre valide et exploitable. |
| Filtre référençant une table ou une colonne/mesure absente du modèle sémantique | `KO` | Filtre cassé : le champ n'existe plus (renommage, suppression) — le visuel affichera un comportement imprévisible ou vide. |
| Filtre de visuel et filtre de page portant sur le même champ avec des conditions mutuellement exclusives (ex. page = `In {"2024"}`, visuel = `NotIn {"2024"}`) | `KO` | Le visuel ne retournera jamais aucune donnée : contradiction de filtrage entre niveaux. |
| Filtre présent mais dont la structure `filter.Where` est vide ou absente alors que `filters[]` contient une entrée | `NA` | Filtre déclaré mais condition non interprétable depuis la structure lue. |
| Champ filtré identique entre deux niveaux avec des conditions compatibles (ex. page = `In {"2024","2025"}`, visuel = `In {"2024"}`, sous-ensemble cohérent) | `OK` | Restriction progressive normale, aucune contradiction. |
| Aucun filtre défini nulle part dans le rapport | `NA` | Rien à évaluer — la règle ne peut pas conclure à une conformité positive en l'absence de filtre à tester. |

---

## 5. Parcours complet du rapport

### Étape 1 — Construire le référentiel du modèle
1. Parcourir `<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl`.
2. Construire un dictionnaire `{ "Table.Colonne": type, "Table.Mesure": type }` couvrant toutes les colonnes et mesures visibles et masquées.

### Étape 2 — Localiser tous les filtres du rapport
1. Lire `report.json` → extraire les filtres de niveau rapport.
2. Lire `pages.json` puis chaque `page.json` → extraire les filtres de niveau page.
3. Pour chaque page, lister tous les `visual.json` → extraire les filtres de niveau visuel.

### Étape 3 — Valider l'existence de chaque champ filtré
Pour chaque filtre trouvé (tous niveaux confondus) : extraire `(Entity, Property)` ; vérifier sa présence dans le référentiel du modèle ; classer `OK` ou `KO`.

### Étape 4 — Détecter les contradictions inter-niveaux, visuel par visuel
Pour chaque visuel : rassembler la pile de filtres qui s'appliquent effectivement à lui (filtre de rapport + filtre(s) de la page qui le contient + son propre filtre de visuel) ; regrouper ces filtres par champ filtré ; pour chaque champ filtré à plusieurs niveaux, comparer les ensembles de valeurs/conditions résolues ; si l'intersection est vide, marquer une contradiction `KO`.

### Étape 5 — Terminer l'analyse
Parcourir la totalité des pages et des visuels avant de conclure — ne jamais s'arrêter au premier filtre invalide trouvé. Produire : le nombre total de filtres analysés par niveau, la liste des filtres `KO` (champ inexistant), la liste des contradictions `KO` détectées avec le visuel concerné, la liste des filtres `NA`.

---

## 6. Détection robuste / normalisation

- Le nom technique du filtre (`filters[].name`, identifiant hexadécimal) n'a pas de valeur métier : seul le couple `(Entity, Property)` compte pour la validation.
- La structure de condition (`filter.Where[].Condition`) peut prendre plusieurs formes syntaxiques (`In`, `Not { In }`, `Comparison`, `Between`...) : l'agent doit normaliser chaque condition en un ensemble de valeurs autorisées/exclues avant de comparer deux filtres portant sur le même champ, plutôt que de comparer les structures JSON brutes terme à terme.
- Un filtre avec `"howCreated": "Drill"` ou `"howCreated": "Advanced"` doit être traité de la même façon qu'un filtre `"howCreated": "User"` pour la validation d'existence du champ ; cette propriété sert uniquement de contexte informatif dans les messages, jamais de critère de décision.
- Les mesures référencées via `field.Measure` doivent être résolues différemment des colonnes (`field.Column`) : les deux formes doivent être supportées par l'extraction du couple `(Entity, Property)`.
- Les filtres implicites générés par une hiérarchie de drill-down ou par une interaction de visuel (cf. [BP-38](38_EliminateVisualInteractions.md)) ne font pas partie du périmètre de cette règle : seuls les filtres explicitement déclarés dans `filterConfig` sont concernés.
- Les pages masquées (`HiddenInViewMode`) restent intégralement analysées : un filtre cassé sur une page technique reste un défaut de configuration à corriger.

---

## 7. Pseudo-code détaillé

```python
def build_model_reference(semantic_model_path):
    fields = {}
    for table_file in find_all_tmdl_files(f"{semantic_model_path}/definition/tables/"):
        table = parse_tmdl_table(table_file)
        for column in table.columns:
            fields[f"{table.name}.{column.name}"] = "column"
        for measure in table.measures:
            fields[f"{table.name}.{measure.name}"] = "measure"
    return fields


def extract_field_ref(filter_entry):
    field = filter_entry.get("field", {})
    if "Column" in field:
        entity = field["Column"]["Expression"]["SourceRef"]["Entity"]
        return f"{entity}.{field['Column']['Property']}"
    if "Measure" in field:
        entity = field["Measure"]["Expression"]["SourceRef"]["Entity"]
        return f"{entity}.{field['Measure']['Property']}"
    return None


def normalize_condition(filter_entry):
    where = filter_entry.get("filter", {}).get("Where", [])
    if not where:
        return None
    return resolve_allowed_and_excluded_values(where)   # -> {"allowed": {...} | None, "excluded": {...}}


def analyze_filters(report_path, semantic_model_path):
    model_fields = build_model_reference(semantic_model_path)

    all_filters = []
    all_filters += extract_filters(read_json(f"{report_path}/definition/report.json"), level="report")

    pages = list_pages(report_path)
    for page in pages:
        page_json = read_json(f"{report_path}/definition/pages/{page.id}/page.json")
        page_filters = extract_filters(page_json, level="page", page=page)
        all_filters += page_filters

        for vfile in list_visual_json_files(report_path, page.id):
            visual = read_json(vfile)
            visual_filters = extract_filters(visual.get("visual", {}), level="visual",
                                              page=page, visual_id=visual["name"])
            all_filters += visual_filters

    ko_missing_field, na_filters = [], []
    for f in all_filters:
        field_ref = extract_field_ref(f)
        if field_ref is None:
            na_filters.append({"filter": f["name"], "reason": "Champ filtré non résolvable"})
            continue
        if field_ref not in model_fields:
            ko_missing_field.append({"filter": f["name"], "field": field_ref, "level": f["level"],
                                      "page": f.get("page"), "visual": f.get("visual_id")})

    ko_contradictions = detect_cross_level_contradictions(pages, all_filters)

    return {
        "total_filters": len(all_filters),
        "ko_missing_field": ko_missing_field,
        "ko_contradictions": ko_contradictions,
        "na_filters": na_filters,
    }


def detect_cross_level_contradictions(pages, all_filters):
    contradictions = []
    for page in pages:
        for visual_id in visuals_of(page):
            applicable = [f for f in all_filters
                          if f["level"] == "report"
                          or (f["level"] == "page" and f.get("page") == page.id)
                          or (f["level"] == "visual" and f.get("visual_id") == visual_id)]

            by_field = group_by(applicable, key=extract_field_ref)
            for field_ref, filters_on_field in by_field.items():
                if len(filters_on_field) < 2:
                    continue
                conditions = [normalize_condition(f) for f in filters_on_field]
                if conditions_are_mutually_exclusive(conditions):
                    contradictions.append({
                        "page": page.display_name, "visual": visual_id, "field": field_ref,
                        "reason": "Conditions de filtre mutuellement exclusives entre niveaux",
                    })
    return contradictions
```

---

## 8. Calcul du statut global

```python
if ko_missing_field or ko_contradictions:
    rule_status = "KO"
elif na_filters:
    rule_status = "NA"
elif total_filters == 0:
    rule_status = "NA"
else:
    rule_status = "OK"
```

| Résultat de l'analyse | Statut global |
|---|---|
| Tous les filtres référencent un champ existant, aucune contradiction inter-niveaux | `OK` |
| Au moins un filtre référence un champ inexistant dans le modèle | `KO` |
| Au moins une contradiction de filtres inter-niveaux détectée sur un visuel | `KO` |
| Aucun `KO`, mais au moins un filtre non interprétable | `NA` |
| Aucun filtre défini dans tout le rapport | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-39",
  "rule_name": "Configuration et test des filtres (page/visuel/rapport)",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_filters": 17,
  "ko_missing_field": [],
  "ko_contradictions": [],
  "na_filters": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-39",
  "rule_name": "Configuration et test des filtres (page/visuel/rapport)",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_filters": 17,
  "ko_missing_field": [
    {"filter": "9c2a1f...", "field": "F_RESPONSES.OLD_COLUMN", "level": "visual",
     "page": "Adoption", "visual": "4f36c5d7ccc129a12ccd"}
  ],
  "ko_contradictions": [
    {"page": "Training", "visual": "c099a124db161c5cda5b", "field": "T_PAGE_NUMBER.PAGE_NUMBER",
     "reason": "Conditions de filtre mutuellement exclusives entre niveaux"}
  ],
  "na_filters": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-39 — Configuration et test des filtres : OK

17 filtres analysés (rapport, pages, visuels). Chaque filtre référence un
champ existant dans le modèle sémantique, aucune contradiction de filtrage
entre les niveaux rapport/page/visuel n'a été détectée.
```

### Exemple `KO`

```text
BP-39 — Configuration et test des filtres : KO

Champ filtré inexistant :
- Visuel "4f36c5d7ccc129a12ccd" (page "Adoption") : filtre sur
  F_RESPONSES.OLD_COLUMN, colonne absente du modèle sémantique actuel.

Contradiction de filtrage :
- Visuel "c099a124db161c5cda5b" (page "Training") : le filtre de page et le
  filtre de visuel portent tous deux sur T_PAGE_NUMBER.PAGE_NUMBER avec des
  conditions qui s'excluent mutuellement — ce visuel ne retournera jamais
  aucune donnée tant que la contradiction n'est pas levée.

Correction attendue :
1. Mettre à jour ou supprimer le filtre référençant F_RESPONSES.OLD_COLUMN.
2. Revoir la condition du filtre de visuel ou du filtre de page sur
   T_PAGE_NUMBER.PAGE_NUMBER pour rendre les deux niveaux compatibles.
```

---

## 11. Conditions empêchant un faux OK

- le référentiel complet des colonnes et mesures du modèle sémantique a été construit avant toute validation de filtre ;
- tous les filtres de niveau rapport, toutes les pages et tous les visuels de toutes les pages ont été parcourus, sans exception ;
- chaque filtre trouvé a été résolu vers un couple `(Entity, Property)` explicite ;
- pour chaque visuel, la pile complète des filtres qui s'appliquent réellement à lui (rapport + page + visuel) a été reconstituée avant de rechercher une contradiction ;
- aucune contradiction de filtrage n'a été détectée sur aucun visuel ;
- aucun filtre ne référence un champ absent du modèle sémantique.

---

## 12. Résumé de la règle

```text
RÈGLE BP-39

CONSTRUIRE le référentiel des colonnes/mesures du modèle sémantique

COLLECTER tous les filtres :
    - niveau rapport (report.json)
    - niveau page (chaque page.json)
    - niveau visuel (chaque visual.json)

POUR chaque filtre
    RÉSOUDRE (Entity, Property)
    SI champ absent du référentiel du modèle
        filtre = KO
    SINON
        filtre = OK

POUR chaque visuel
    RASSEMBLER la pile de filtres applicables (rapport + page + visuel)
    REGROUPER par champ filtré
    SI conditions mutuellement exclusives sur un même champ
        visuel = KO (contradiction)

SI au moins un filtre KO ou une contradiction détectée
    règle = KO
SINON SI au moins un filtre non interprétable
    règle = NA
SINON SI aucun filtre défini dans le rapport
    règle = NA
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-39 — Configuration et test des filtres                 │
│         (page, visuel, rapport)                                   │
└────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
          ┌────────────────────────────────────┐
          │ CONSTRUIRE le référentiel du modèle  │
          │ (tables\*.tmdl -> colonnes/mesures)  │
          └──────────────┬───────────────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────────────┐
     │ COLLECTER tous les filtres                         │
     │  - niveau rapport (report.json)                    │
     │  - niveau page (chaque page.json)                  │
     │  - niveau visuel (chaque visual.json)               │
     └──────────────┬─────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ╔═════════════╗       ┌───────────────┐
   ║ 1+ filtre   ║       │ Aucun filtre   │
   ║ trouvé      ║       │ nulle part     │
   ╚══════╤══════╝       └───────┬────────┘
          │                      ▼
          │              ┌──────────────┐
          │              │ Retour : NA  │
          │              └──────────────┘
          ▼
 ┌────────────────────────────────────────┐
 │ POUR chaque filtre                      │
 │  RÉSOUDRE (Entity, Property)            │
 └──────────────┬───────────────────────────┘
                ▼
       ┌────────┴─────────┐
       ▼                   ▼
╔═════════════════╗  ┌─────────────────────┐
║ Champ non        ║  │ Champ résolu         │
║ résolvable       ║  │                      │
║ -> NA            ║  └──────────┬────────────┘
╚═════════════════╝              ▼
                          ┌────────┴─────────┐
                          ▼                   ▼
                   ╔═════════════╗    ┌───────────────┐
                   ║ Absent du   ║    │ Présent dans   │
                   ║ modèle ->KO ║    │ le modèle -> OK│
                   ╚═════════════╝    └───────────────┘
                          │
                          ▼
 ┌──────────────────────────────────────────┐
 │ POUR chaque visuel                        │
 │  RASSEMBLER la pile de filtres applicables│
 │  (rapport + page + visuel)                │
 │  REGROUPER par champ filtré               │
 └──────────────┬─────────────────────────────┘
                ▼
       ┌────────┴─────────┐
       ▼                   ▼
╔═════════════════╗  ┌─────────────────────┐
║ Conditions       ║  │ Conditions           │
║ mutuellement     ║  │ compatibles           │
║ exclusives sur    ║  │ (sous-ensemble)       │
║ un même champ    ║  └─────────────────────┘
║ -> KO            ║
╚═════════════════╝
                          │
                          ▼
     ┌──────────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL                  │
     │ Priorité : KO > NA > OK                   │
     └──────────────┬─────────────────────────────┘
                     │
    ┌────────────────┼─────────────────┬───────────────┐
    ▼                ▼                 ▼                ▼
╔═════════╗   ┌─────────────┐   ┌─────────────┐  ┌─────────────┐
║ Champ    ║   │ Filtre non   │   │ Aucun filtre │  │ Tous les     │
║ absent   ║   │ interprétable│   │ dans tout le │  │ filtres OK,  │
║ OU       ║   │ -> NA        │   │ rapport      │  │ aucune       │
║ contradic║   └─────────────┘   │ -> NA        │  │ contradiction│
║ tion     ║                     └─────────────┘  │ -> OK        │
║ -> KO    ║                                       └─────────────┘
╚═════════╝
                     │
                     ▼
        RETOUR rule_status (OK/KO/NA)
```
