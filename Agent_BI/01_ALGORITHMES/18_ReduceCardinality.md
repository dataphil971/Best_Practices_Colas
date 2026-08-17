# BP-18 — Éviter les colonnes à haute cardinalité comme filtre visuel (slicer)

## 1. Objectif de la bonne pratique

La cardinalité d'une colonne est son nombre de valeurs distinctes. Une colonne à **très haute cardinalité** (identifiants uniques, textes libres, horodatages précis...) pose deux problèmes lorsqu'elle est utilisée comme filtre visuel (« slicer ») dans un rapport Power BI :

1. **Compression VertiPaq** : le moteur de stockage colonne de Power BI compresse d'autant moins bien une colonne que le nombre de valeurs distinctes est élevé (le dictionnaire d'encodage RLE/valeur devient volumineux, la taille du modèle en mémoire augmente).
2. **Expérience utilisateur** : un slicer affichant plusieurs centaines ou milliers de valeurs distinctes devient inutilisable pour un utilisateur métier (liste interminable, recherche peu pertinente, absence de hiérarchie de filtrage).

L'objectif de cette règle est d'identifier les colonnes à haute cardinalité **effectivement utilisées comme slicer** dans au moins un visuel du rapport, en croisant deux sources d'information : la structure du modèle sémantique (pour la cardinalité) et les définitions de visuels du rapport (pour l'usage en tant que filtre).

Point essentiel : **le nombre de valeurs distinctes d'une colonne n'est pas stocké dans les fichiers TMDL**, qui décrivent uniquement la structure du modèle (colonnes, types, relations), pas le contenu des données. Cette règle nécessite donc, comme [BP-16](16_IncrementalRefresh.md) et [BP-20](20_ReferentialIntegrity.md), un **extrait de cardinalité externe** (résultat d'une requête DAX de type `EVALUATE ROW("distinct", DISTINCTCOUNT(Table[Column]), "rows", COUNTROWS(Table))` exécutée via XMLA/ADOMD, ou export de profilage de données), fourni en complément des fichiers TMDL et du rapport.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de pages et de visuels du rapport ;
- du type de visuel utilisé comme filtre (`slicer`, mais aussi les filtres de page/rapport qui suivent une structure JSON analogue) ;
- des seuils de cardinalité retenus, qui doivent rester configurables.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl                          (liste des colonnes du modèle)
<REPORT_PATH>\definition\pages\<pageId>\visuals\<visualId>\visual.json   (détection des slicers et de leur champ)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
AI_BAROMETER_BI-CDS.Report\definition\pages\6d13bf2424ca09747390\visuals\b47dd7660409c14d2c95\visual.json
```

En complément, l'agent doit recevoir un extrait de cardinalité, par exemple :

```json
{
  "D_USERS.USER_JOB": {"distinct_count": 87, "row_count": 412},
  "D_USERS.USER_COUNTRY": {"distinct_count": 14, "row_count": 412},
  "F_RESPONSES.CAMPAIGN_USER_LOGIN": {"distinct_count": 4830, "row_count": 4830}
}
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1 Détection d'un slicer et de son champ dans `visual.json`

Extrait réel de ce projet (`.../visuals/b47dd7660409c14d2c95/visual.json`) :

```json
{
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

Le couple `(Entity, Property)` — ici `(D_USERS, USER_JOB)` — identifie sans ambiguïté la table et la colonne du modèle utilisées comme champ du slicer. Le champ `queryRef` (`"D_USERS.USER_JOB"`) fournit une forme condensée équivalente, utile pour une extraction rapide par expression régulière en complément de la lecture structurée du JSON.

### 3.2 Cardinalité d'une colonne (fournie en entrée d'audit)

```json
{"D_USERS.USER_JOB": {"distinct_count": 87, "row_count": 412}}
```

Deux métriques complémentaires sont nécessaires pour éviter les faux positifs sur les petites tables de dimension :

- **ratio relatif** : `distinct_count / row_count` — pertinent pour détecter une colonne quasi-identifiante (proche de 1, comme une clé primaire) ;
- **volume absolu** : `distinct_count` seul — pertinent pour détecter une liste trop longue pour un slicer, indépendamment du ratio (une colonne à 3 000 valeurs distinctes sur une table de 50 000 lignes a un ratio faible de 6 %, mais reste inutilisable comme slicer).

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Colonne utilisée comme slicer, `distinct_count` faible (sous le seuil absolu) et ratio faible (sous le seuil relatif) | `OK` | Cardinalité compatible avec un usage en filtre visuel. |
| Colonne utilisée comme slicer, `distinct_count` supérieur au seuil absolu **ou** ratio supérieur au seuil relatif | `KO` | Slicer à haute cardinalité : compression VertiPaq dégradée et liste de valeurs difficilement exploitable. |
| Colonne utilisée comme slicer, cardinalité non fournie dans l'extrait | `NA` | Impossible de conclure sans donnée de cardinalité. |
| Colonne non utilisée comme slicer dans le rapport (utilisée uniquement en axe de visuel, mesure, relation...) | `NA` | Hors périmètre : cette règle cible spécifiquement l'usage en filtre visuel. |
| Slicer configuré en mode « Entre » / plage numérique ou date (« Between », histogramme de plage) plutôt qu'en liste de valeurs | `NA` | Le mode plage ne matérialise pas la liste de valeurs distinctes à l'écran ; le problème d'UX ne s'applique pas de la même façon (à vérifier via la propriété `mode` du visuel, ex. `"mode": "Between"`). |

Exemple avec seuils configurés à `distinct_count > 50` **ou** `ratio > 0.2` :

| Colonne | Utilisée comme slicer ? | `distinct_count` | `row_count` | Ratio | Statut |
|---|---|---|---|---|---|
| `D_USERS.USER_JOB` | Oui (page `6d13bf...`) | 87 | 412 | 0.21 | `KO` (dépasse les deux seuils) |
| `D_USERS.USER_COUNTRY` | Oui (hypothèse) | 14 | 412 | 0.03 | `OK` |
| `F_RESPONSES.CAMPAIGN_USER_LOGIN` | Non (jamais utilisée en slicer dans ce rapport) | 4830 | 4830 | 1.0 | `NA` (hors périmètre) |
| `D_CAMPAIGNS.CAMPAIGN_LABEL` | Oui (hypothèse) | — (non fourni) | — | — | `NA` (cardinalité manquante) |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl` du modèle sémantique.
2. Lister récursivement tous les fichiers `visual.json` sous `<REPORT_PATH>\definition\pages\`.
3. Charger l'extrait de cardinalité externe fourni en entrée d'audit.
4. Si le rapport ou le modèle est introuvable, retourner `NON_EVALUE`.

### Étape 2 — Recenser tous les slicers du rapport
Pour chaque `visual.json`, vérifier `visual.visualType == "slicer"` ; si oui, extraire tous les champs projetés (`query.queryState.Values.projections[].field.Column`), c'est-à-dire le couple `(Entity, Property)` et le mode du slicer (`Basic`, `Between`, `List`, `Dropdown`...) le cas échéant.

### Étape 3 — Croiser avec la cardinalité
Pour chaque couple `(table, colonne)` identifié comme champ de slicer, rechercher son entrée dans l'extrait de cardinalité ; si absente, classer `NA` avec la raison explicite ; sinon calculer le ratio et comparer aux deux seuils.

### Étape 4 — Ne pas s'arrêter à la première anomalie
Un même couple `(table, colonne)` peut être utilisé comme slicer par plusieurs visuels sur plusieurs pages (cas fréquent des slicers synchronisés, comme `syncGroup` dans l'exemple réel de ce projet) : l'agent doit recenser **toutes** les occurrences, mais ne compter la colonne qu'une seule fois dans le verdict global tout en listant chaque page/visuel concerné comme preuve.

### Étape 5 — Terminer l'analyse
Produire le nombre total de slicers détectés, le nombre de couples `(table, colonne)` distincts utilisés comme slicer, la répartition `OK`/`KO`/`NA`, et le détail de chaque colonne `KO` avec la liste des visuels concernés.

---

## 6. Détection robuste / normalisation

- Le nom de la propriété du visuel est toujours `"visualType": "slicer"` ; l'agent ne doit pas se fier au seul nom du fichier ou à une éventuelle légende affichée (`title`), qui peut être libre et ne pas refléter le champ réellement utilisé.
- Un visuel `slicer` peut projeter plusieurs champs simultanément (hiérarchie de slicer) : l'agent doit itérer sur l'intégralité du tableau `projections`, pas seulement le premier élément.
- Le mode du slicer (`Basic`/liste vs `Between`/plage vs `Relative date`) se trouve dans `visual.objects.data[].properties.mode.expr.Literal.Value` (ex. `"'Basic'"`) : l'agent doit lire cette propriété pour exclure les slicers en mode plage numérique/date du périmètre, conformément à la section 4.
- Les identifiants de page (`81a74ceaa660678035ae`) et de visuel (`b47dd7660409c14d2c95`) sont des hachages opaques sans signification métier : ils ne doivent jamais être utilisés comme critère de décision, seulement comme référence technique dans les preuves.
- La correspondance entre le couple `(Entity, Property)` du visuel et une colonne réelle du modèle doit être vérifiée (la colonne doit exister dans les fichiers `tables\*.tmdl`) ; si `Entity` ne correspond à aucune table connue, classer `NA` avec la raison « référence de champ non résolvable dans le modèle » plutôt que d'échouer silencieusement.
- Les seuils (`CARDINALITY_ABSOLUTE_THRESHOLD`, `CARDINALITY_RATIO_THRESHOLD`) doivent rester des paramètres configurables de l'audit, jamais des constantes figées dans le pseudo-code.
- Un visuel dupliqué (bookmark, visuel masqué comme celui observé dans ce projet avec `"isHidden": true`) doit tout de même être analysé : un slicer masqué reste un slicer techniquement présent et potentiellement réactivé, il ne doit pas être exclu silencieusement du périmètre.

---

## 7. Pseudo-code détaillé

```python
CARDINALITY_ABSOLUTE_THRESHOLD = 50     # paramètre configurable
CARDINALITY_RATIO_THRESHOLD = 0.2       # paramètre configurable

def is_range_mode_slicer(visual_json):
    mode = get_property_literal(visual_json, "objects.data[0].properties.mode")
    return mode is not None and mode.strip("'").lower() in {"between", "relativedate", "relativerange"}

def extract_slicer_fields(visual_json):
    if visual_json.get("visual", {}).get("visualType") != "slicer":
        return []
    projections = deep_get(visual_json, "visual.query.queryState.Values.projections", default=[])
    fields = []
    for proj in projections:
        column = proj.get("field", {}).get("Column")
        if column is None:
            continue
        entity = deep_get(column, "Expression.SourceRef.Entity")
        prop = column.get("Property")
        if entity and prop:
            fields.append((entity, prop))
    return fields


slicer_usage = {}   # (table, column) -> [ {page, visual, is_range_mode}, ... ]

report_visual_files = find_all_visual_json_files("<REPORT_PATH>/definition/pages/")
for visual_file in report_visual_files:
    visual_json = load_json(visual_file)
    if is_range_mode_slicer(visual_json):
        continue   # hors périmètre : mode plage, pas de liste de valeurs affichée
    for entity, prop in extract_slicer_fields(visual_json):
        slicer_usage.setdefault((entity, prop), []).append({
            "page": extract_page_id(visual_file),
            "visual": extract_visual_id(visual_file),
        })

model_columns = collect_all_column_identifiers("<SEMANTIC_MODEL_PATH>/definition/tables/")
cardinality_extract = load_external_cardinality_extract()   # fourni par le contexte d'audit

ok_results, ko_results, na_results = [], [], []

for (table, column), usages in slicer_usage.items():
    key = f"{table}.{column}"

    if key not in model_columns:
        na_results.append({"column": key, "status": "NA",
                            "reason": "Référence de champ non résolvable dans le modèle"})
        continue

    stats = cardinality_extract.get(key) if cardinality_extract else None
    if stats is None:
        na_results.append({"column": key, "status": "NA", "usages": usages,
                            "reason": "Cardinalité non fournie pour cette colonne"})
        continue

    distinct_count = stats["distinct_count"]
    row_count = stats["row_count"]
    ratio = distinct_count / row_count if row_count else 0

    if distinct_count > CARDINALITY_ABSOLUTE_THRESHOLD or ratio > CARDINALITY_RATIO_THRESHOLD:
        ko_results.append({
            "column": key, "status": "KO", "distinct_count": distinct_count,
            "row_count": row_count, "ratio": round(ratio, 2), "usages": usages,
            "reason": "Cardinalité trop élevée pour un usage en slicer",
        })
    else:
        ok_results.append({
            "column": key, "status": "OK", "distinct_count": distinct_count,
            "row_count": row_count, "ratio": round(ratio, 2), "usages": usages,
        })
```

---

## 8. Calcul du statut global

```python
if ko_results:
    rule_status = "KO"
elif na_results and not ok_results:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Tous les slicers portent sur des colonnes à cardinalité maîtrisée | `OK` |
| Au moins un slicer porte sur une colonne à haute cardinalité | `KO` |
| Aucun slicer détecté dans le rapport, ou cardinalité non fournie pour tous les slicers | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-18",
  "rule_name": "Éviter les colonnes à haute cardinalité comme filtre visuel (slicer)",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "thresholds": {"absolute": 50, "ratio": 0.2},
  "total_slicers_detected": 6,
  "distinct_slicer_columns": 3,
  "ok_columns": 3,
  "ko_columns": 0,
  "na_columns": 0,
  "ok_details": [
    {"column": "D_USERS.USER_COUNTRY", "distinct_count": 14, "row_count": 412, "ratio": 0.03,
     "usages": [{"page": "6d13bf2424ca09747390", "visual": "7c671fa36d4026317ce2"}]}
  ]
}
```

Exemple `KO` (basé sur le slicer réel de ce projet) :

```json
{
  "rule_id": "BP-18",
  "rule_name": "Éviter les colonnes à haute cardinalité comme filtre visuel (slicer)",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "thresholds": {"absolute": 50, "ratio": 0.2},
  "total_slicers_detected": 6,
  "distinct_slicer_columns": 3,
  "ok_columns": 2,
  "ko_columns": 1,
  "na_columns": 0,
  "ko_details": [
    {
      "column": "D_USERS.USER_JOB",
      "distinct_count": 87,
      "row_count": 412,
      "ratio": 0.21,
      "usages": [{"page": "6d13bf2424ca09747390", "visual": "b47dd7660409c14d2c95"}],
      "reason": "Cardinalité trop élevée pour un usage en slicer"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-18 — Cardinalité des slicers : OK

3 colonnes distinctes utilisées comme slicer dans le rapport, toutes sous
les seuils retenus (50 valeurs distinctes / ratio 20 %). Aucune colonne à
haute cardinalité n'est proposée comme filtre visuel.
```

### Exemple `KO`

```text
BP-18 — Cardinalité des slicers : KO

2 colonnes conformes sur 3 colonnes utilisées comme slicer.

Colonne non conforme :
- D_USERS.USER_JOB : 87 valeurs distinctes sur 412 lignes (ratio 21 %),
  utilisée comme slicer sur la page 6d13bf2424ca09747390 (visuel
  b47dd7660409c14d2c95, titre "Job"). Liste de filtrage longue et
  compression VertiPaq dégradée pour cette colonne.

Correction attendue :
regrouper les intitulés de poste en catégories métier de plus haut niveau
(nouvelle colonne calculée à cardinalité réduite), ou remplacer le slicer
par un champ de recherche libre / une hiérarchie à deux niveaux, plutôt
que d'exposer directement la colonne USER_JOB en liste de filtrage.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- tous les fichiers `visual.json` du rapport ont été énumérés récursivement, y compris ceux des visuels masqués (`isHidden: true`) ;
- tous les visuels de type `slicer` ont été détectés, avec l'intégralité de leurs champs projetés (pas seulement le premier) ;
- les slicers en mode plage (`Between`, dates relatives) ont été correctement exclus du périmètre, mais leur exclusion a été tracée, pas silencieuse ;
- un extrait de cardinalité a été fourni et couvre toutes les colonnes utilisées comme slicer ;
- chaque colonne a été comparée aux deux seuils (absolu et relatif), pas un seul des deux ;
- aucune colonne slicer n'a été omise du croisement avec le modèle sémantique.

L'agent ne doit jamais produire `OK` en l'absence d'extrait de cardinalité, ni lorsqu'un couple `(Entity, Property)` d'un slicer ne peut pas être résolu vers une colonne réelle du modèle.

---

## 12. Résumé de la règle

```text
RÈGLE BP-18

RECENSER tous les visual.json du rapport
POUR chaque visuel de type "slicer"
    SI mode = plage (Between / Relative date)
        IGNORER (hors périmètre)
    EXTRAIRE tous les champs projetés (Entity, Property)
    ENREGISTRER l'usage (page, visuel) pour chaque champ

CHARGER l'extrait de cardinalité externe

POUR chaque colonne utilisée comme slicer
    SI colonne non résolvable dans le modèle
        colonne = NA
        CONTINUER
    SI cardinalité non fournie
        colonne = NA
        CONTINUER

    ratio = distinct_count / row_count

    SI distinct_count > seuil_absolu OU ratio > seuil_relatif
        colonne = KO
    SINON
        colonne = OK

    ENREGISTRER le résultat avec la liste des visuels utilisant cette colonne
FIN POUR

SI au moins une colonne KO
    règle = KO
SINON SI aucun slicer avec cardinalité connue
    règle = NA
SINON
    règle = OK

AFFICHER toutes les colonnes KO avec recommandation de regroupement/hiérarchie
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-18 — Cardinalité des colonnes utilisées comme slicer      │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ Lister tables/*.tmdl (colonnes modèle)    │
          │ Lister récursivement les visual.json      │
          │ CHARGER l'extrait de cardinalité externe   │
          └────────────────┬───────────────────────────┘
               ┌───────────┴───────────┐
               ▼                       ▼
         ╔═════════════╗       ┌──────────────────┐
         ║ Modèle et    ║       │ Modèle ou rapport  │
         ║ rapport      ║       │ introuvable ❌      │
         ║ trouvés ✅   ║       └─────────┬──────────┘
         ╚══════╤═══════╝                 ▼
                │                ┌────────────────┐
                │                │ Retour :        │
                │                │ NON_EVALUE      │
                │                └────────────────┘
                ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque visual.json (boucle)            │
     │  SI visualType = "slicer" ET mode != plage  │
     │    EXTRAIRE tous les champs (Entity,         │
     │    Property) projetés → slicer_usage         │
     └────────────────┬───────────────────────────────┘
                      ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque colonne (table,col) utilisée     │
     │ comme slicer (boucle)                         │
     └────────────────┬───────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ Colonne résolvable dans le       │
        │ modèle sémantique ?              │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ┌──────────┐   ╔═══════════╗
       │ NON = NA │   ║ OUI          ║
       └──────────┘   ╚═════╤════════╝
                            ▼
                 ┌───────────────────────┐
                 │ Cardinalité fournie      │
                 │ dans l'extrait ?         │
                 └──────────┬─────────────────┘
                      ┌──────┴──────┐
                      ▼             ▼
                ┌──────────┐  ╔═══════════╗
                │ NON = NA │  ║ OUI           ║
                └──────────┘  ╚═════╤═════════╝
                                    ▼
                     ┌────────────────────────────┐
                     │ ratio = distinct/row_count     │
                     │ distinct_count > seuil abs.     │
                     │ OU ratio > seuil relatif ?       │
                     └──────────────┬────────────────────┘
                              ┌──────┴──────┐
                              ▼             ▼
                        ╔═══════════╗ ┌──────────┐
                        ║ OUI = KO  ║ │ NON = OK   │
                        ╚═══════════╝ └──────────┘
                              │             │
                              └──────┬──────┘
                                    ▼
                    FIN DE BOUCLE (colonne suivante)
                                    │
                                    ▼
        ┌────────────────────────────────────────────┐
        │ CALCUL DU RÉSULTAT FINAL                      │
        │ KO présent ?              → règle = KO         │
        │ Sinon NA seul (aucun OK)  → règle = NA         │
        │ Sinon                      → règle = OK        │
        └────────────────────┬───────────────────────────┘
                             ▼
             RETOUR rule_status (OK/KO/NA)
```
