# BP-26 — Description des champs dont le sens métier n'est pas évident

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que les colonnes et les mesures dont l'intitulé ne permet pas, à lui seul, de comprendre sans ambiguïté leur contenu ou leur mode de calcul, portent une description (`description` en TMDL, ou commentaire `///` immédiatement avant la définition). Un nom de champ techniquement correct n'est pas toujours suffisant : des intitulés abrégés, des codes couleur, des indicateurs calculés ou des champs à vocation purement technique d'affichage peuvent induire l'utilisateur en erreur s'ils ne sont pas explicités.

Cette règle se distingue de deux autres bonnes pratiques du même corpus :
- [BP-19](19_CertifiedDatasetDescriptions.md) porte spécifiquement sur les exigences de documentation des **datasets certifiés / de build**, un périmètre de gouvernance plus large et plus strict ;
- [BP-29](29_MeasurePurpose.md) exige une description **systématique sur 100 % des mesures**, quel que soit leur niveau d'ambiguïté apparent, car les mesures sont les objets les plus consommés par les utilisateurs.

BP-26 est une règle de bon sens plus ciblée : elle ne réclame pas une description exhaustive de tous les champs, mais seulement de ceux dont l'ambiguïté est raisonnablement détectable (acronymes non explicites, termes génériques non qualifiés, codes techniques d'affichage).

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables, de colonnes et de mesures ;
- du type d'élément (colonne ou mesure) ;
- de l'ordre des propriétés dans les fichiers TMDL.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\T_NOTIFICATION.tmdl
```

L'agent doit examiner tous les blocs `column` et `measure` visibles (les éléments masqués, cf. [BP-25](25_HideTechnicalFields.md), sont hors périmètre car ils ne sont jamais consultés par l'utilisateur final).

---

## 3. Élément(s) / propriété(s) à contrôler

Deux mécanismes TMDL portent la description d'un champ :

**Commentaire `///` immédiatement avant la définition** (converti en description lors du chargement du modèle) :

```tmdl
/// Percentage of adoption's respondent par usage
measure pct_RespondentsPerUsage = ```...```
```

**Propriété `description` explicite dans le bloc** (moins fréquente dans ce projet, mais valide) :

```tmdl
column USER_COUNTRY
    dataType: string
    description: Country of residence declared by the respondent at registration
    sourceColumn: USER_COUNTRY
```

Exemple de mesure **ambiguë sans description** (cas à détecter) :

```tmdl
measure Color_Worry = ```
        VAR CurrentLevel =
            SELECTEDVALUE(F_RESPONSES[WORRY_LEVEL])
        RETURN
            CALCULATE(
                MAX(F_RESPONSES[WORRY_COLOUR]),
                F_RESPONSES[WORRY_LEVEL] = CurrentLevel
            )
        ```
    displayFolder: FILTERS\COLOUR
    lineageTag: 235d368d-3ad8-4490-8ead-066f9f2ec6e2
```

Le nom `Color_Worry` ne précise ni la logique de résolution (couleur associée au niveau d'inquiétude actuellement sélectionné, utilisée pour la mise en forme conditionnelle des visuels) ni son usage attendu (elle n'est pas destinée à être affichée directement, mais consommée par les propriétés de mise en forme d'un visuel) : c'est un candidat typique à une description manquante.

À l'inverse, `Filters_Reminder_en` est un exemple explicite via son nom mais dont la logique de concaténation (rappel des filtres actifs) mériterait tout de même une description, faute de quoi un développeur reprenant le modèle devrait lire l'intégralité du code DAX pour comprendre l'objectif.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Champ visible identifié comme ambigu, avec description (`///` ou `description:`) non vide | `OK` | L'ambiguïté potentielle est levée par la documentation. |
| Champ visible identifié comme ambigu, sans description | `KO` | Le sens du champ n'est pas déductible de son seul intitulé, et rien ne vient l'expliciter. |
| Champ visible dont l'intitulé est suffisamment explicite par lui-même (ex. `CAMPAIGN_ID`, `USER_COUNTRY`, `Sample_Total_Size`) | `NA` | La règle ne s'applique pas : la description n'est pas requise par cette bonne pratique (mais peut rester recommandée par BP-29 si c'est une mesure). |
| Champ visible avec description présente mais trop générique pour lever l'ambiguïté (ex. `description: KPI`, `///  `) | `KO` | La documentation existe formellement mais n'apporte aucune information exploitable. |
| Champ masqué (`isHidden`) | `NA` | Hors périmètre, jamais présenté à l'utilisateur final. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Si aucun fichier n'est trouvé, retourner `NON_EVALUE`.

### Étape 2 — Recenser les champs visibles
Pour chaque table : identifier tous les blocs `column` et `measure` ; exclure ceux portant `isHidden`.

### Étape 3 — Qualifier l'ambiguïté de chaque champ visible
Pour chaque champ restant, appliquer une grille de détection d'ambiguïté (section 6) fondée sur des signaux objectifs (terme générique non qualifié, abréviation non standard, champ de type couleur/statut/technique d'affichage, référence à une logique conditionnelle non déductible du nom).

### Étape 4 — Vérifier la présence et la qualité de la description
Pour chaque champ jugé ambigu : rechercher un commentaire `///` immédiatement avant sa définition ou une propriété `description` dans son bloc ; vérifier que le texte trouvé n'est pas vide ni trivial (longueur minimale, absence de valeurs de type placeholder comme `TODO`, `N/A`, `.`).

### Étape 5 — Terminer l'analyse
Parcourir la totalité des champs visibles sans s'arrêter au premier cas non conforme. Produire le nombre de champs ambigus détectés, le nombre documentés (`OK`), le nombre non documentés (`KO`), et la liste des champs non ambigus (`NA`) à titre d'information.

---

## 6. Détection robuste / normalisation

**Signaux d'ambiguïté** (au moins un signal suffit à classer le champ comme candidat à documentation) :
- le nom du champ est un terme générique isolé ou peu qualifié : `Color_*`, `*_Flag`, `*_Status`, `*_Type`, `*_Code`, `Value`, `Result`, `Title`, `Message`, `Icon` ;
- le nom du champ contient une abréviation non explicitée par le contexte de la table (`NOTIF_*` en dehors d'une table `T_NOTIFICATION` explicite) ;
- l'expression DAX de la mesure contient une logique conditionnelle (`IF`, `SWITCH`) dont le résultat dépend d'un contexte non déductible du nom (ex. sélection dynamique d'une couleur, d'un texte ou d'une icône selon une valeur sélectionnée) ;
- le champ est destiné à un usage technique d'affichage (construction de SVG, titres dynamiques, bannières) plutôt qu'à une lecture directe par l'utilisateur.

**Signaux d'absence d'ambiguïté** (le champ est dispensé de cette règle) :
- le nom du champ est un identifiant, une date, ou une grandeur métier standard immédiatement compréhensible (`CAMPAIGN_ID`, `USER_COUNTRY`, `Nb_Responses`, `Sample_Total_Size`) ;
- le champ est une clé technique déjà masquée (hors périmètre, cf. section 4).

**Normalisation de la description trouvée** :
```python
def is_meaningful_description(text):
    if text is None:
        return False
    normalized = text.strip()
    if len(normalized) < 10:
        return False
    if normalized.lower() in {"todo", "n/a", "na", "tbd", "."}:
        return False
    return True
```

- Le commentaire `///` doit être recherché **immédiatement** au-dessus de la ligne `measure <nom> =` ou `column <nom>`, en ignorant les lignes vides éventuelles entre les deux ne provenant pas d'un autre élément.
- Une description peut être répartie sur plusieurs lignes `///` consécutives : l'agent doit les concaténer avant d'évaluer la longueur.
- La casse et les espaces superflus ne doivent pas influencer la détection de la présence du commentaire, seulement son contenu normalisé.

---

## 7. Pseudo-code détaillé

```python
GENERIC_TERMS = {"color", "flag", "status", "type", "code", "value", "result",
                  "title", "message", "icon"}

def is_ambiguous_field(element, table):
    name_lower = element.name.lower()

    if any(term in name_lower for term in GENERIC_TERMS):
        return True, "Terme générique non qualifié dans le nom"

    if element.block_type == "measure":
        dax_body = element.dax_expression
        if contains_conditional_logic(dax_body) and not is_self_explanatory_name(element.name):
            return True, "Logique conditionnelle non déductible du nom"

    if name_lower.startswith("notif_") and table.name != "T_NOTIFICATION":
        return True, "Abréviation de domaine non explicitée par le contexte"

    return False, None


def analyze_field_descriptions(table_files):
    ok_items, ko_items, na_items = [], [], []

    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        elements = list(table.measures) + list(table.columns)

        for element in elements:
            if element.has_flag("isHidden"):
                na_items.append({"table": table.name, "name": element.name, "status": "NA",
                                  "reason": "Champ masqué, hors périmètre utilisateur"})
                continue

            ambiguous, reason = is_ambiguous_field(element, table)
            if not ambiguous:
                na_items.append({"table": table.name, "name": element.name, "status": "NA",
                                  "reason": "Intitulé suffisamment explicite"})
                continue

            raw_description = element.get_triple_slash_comment() or element.get_property("description")
            if is_meaningful_description(raw_description):
                ok_items.append({"table": table.name, "name": element.name, "status": "OK"})
            else:
                ko_items.append({
                    "table": table.name, "name": element.name, "status": "KO",
                    "ambiguity_reason": reason,
                    "reason": "Champ ambigu sans description exploitable",
                })

    return ok_items, ko_items, na_items
```

---

## 8. Calcul du statut global

```python
if ko_items:
    rule_status = "KO"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > OK`. Les éléments `NA` (non ambigus ou masqués) ne participent jamais au calcul du statut global ; l'absence totale de champ ambigu dans le modèle conduit à `OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Tous les champs ambigus détectés sont documentés | `OK` |
| Au moins un champ ambigu n'est pas documenté (ou documenté de façon triviale) | `KO` |
| Aucun champ ambigu détecté dans le modèle | `OK`, avec message informatif |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-26",
  "rule_name": "Description des champs dont le sens métier n'est pas évident",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "ambiguous_fields_detected": 9,
  "documented": 9,
  "not_documented": 0,
  "ko_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-26",
  "rule_name": "Description des champs dont le sens métier n'est pas évident",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "ambiguous_fields_detected": 9,
  "documented": 6,
  "not_documented": 3,
  "ko_details": [
    {"table": "MEASURE", "name": "Color_Worry", "ambiguity_reason": "Terme générique non qualifié dans le nom"},
    {"table": "MEASURE", "name": "Color_Interest", "ambiguity_reason": "Terme générique non qualifié dans le nom"},
    {"table": "MEASURE", "name": "NOTIF_Icon", "ambiguity_reason": "Abréviation de domaine non explicitée par le contexte"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-26 — Description des champs dont le sens métier n'est pas évident : OK

9 champs identifiés comme potentiellement ambigus (couleurs dynamiques, icônes,
titres calculés). Tous disposent d'une description exploitable.
```

### Exemple `KO`

```text
BP-26 — Description des champs dont le sens métier n'est pas évident : KO

6 champs ambigus documentés sur 9 détectés.

Champs non documentés :
- MEASURE[Color_Worry] : mesure retournant un code couleur selon le niveau
  d'inquiétude sélectionné, sans description expliquant son usage
  (mise en forme conditionnelle).
- MEASURE[Color_Interest] : même problème pour le niveau d'intérêt.
- MEASURE[NOTIF_Icon] : renvoie un chemin d'icône selon le type de
  notification, sans description.

Correction attendue :
ajouter un commentaire /// juste avant chaque mesure listée, expliquant la
logique de résolution et l'usage attendu du champ (ex. : "/// Couleur
associée au niveau d'inquiétude actuellement sélectionné, utilisée pour la
mise en forme conditionnelle des visuels").
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus ;
- chaque champ visible (colonne et mesure) a été passé au crible de la grille d'ambiguïté ;
- les champs masqués ont bien été exclus du périmètre ;
- pour chaque champ jugé ambigu, la recherche de description a couvert à la fois le commentaire `///` et la propriété `description` ;
- une description triviale, vide ou de type placeholder n'a jamais été comptée comme conforme ;
- aucun champ ambigu n'a été omis de l'analyse par erreur de classification.

---

## 12. Résumé de la règle

```text
RÈGLE BP-26

POUR chaque table du modèle sémantique
    POUR chaque colonne et chaque mesure visible (isHidden absent)
        ÉVALUER l'ambiguïté du champ (terme générique, abréviation non
                 explicitée, logique conditionnelle non déductible du nom)

        SI champ non ambigu
            champ = NA
        SINON
            RECHERCHER description (/// ou description:)
            SI description présente et significative
                champ = OK
            SINON
                champ = KO
        ENREGISTRER le résultat
    FIN POUR
FIN POUR

SI au moins un champ ambigu non documenté
    règle = KO
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-26 — Description des champs dont le sens métier    │
│         n'est pas évident                                     │
└────────────────────────┬───────────────────────────────────────┘
                          ▼
           ┌───────────────────────────────┐
           │ Lister tables\*.tmdl            │
           └───────────────┬─────────────────┘
                ┌────────────┴────────────┐
                ▼                          ▼
          ╔═════════════╗          ┌───────────────┐
          ║ Fichiers    ║          │ Aucun fichier  │
          ║ trouvés ✅  ║          │ trouvé ❌       │
          ╚══════╤══════╝          └───────┬────────┘
                 │                          ▼
                 │                  ┌────────────────┐
                 │                  │ Retour :        │
                 │                  │ NON_EVALUE      │
                 │                  └────────────────┘
                 ▼
   ┌────────────────────────────────────────────┐
   │ POUR chaque table                            │
   │  POUR chaque colonne / mesure visible          │
   │  (isHidden exclu)                              │
   └───────────────────────┬─────────────────────────┘
                           ▼
              ┌──────────────────────────────┐
              │ Champ ambigu ? (terme          │
              │ générique, abréviation, IF/    │
              │ SWITCH non déductible du nom)  │
              └───────────────┬────────────────┘
              ┌─────────────────┴─────────────────┐
              ▼                                    ▼
        ╔═════════╗                          ┌────────────┐
        ║ NON     ║                          │ OUI        │
        ╚════╤════╝                          └─────┬──────┘
             ▼                                      ▼
      ┌─────────────┐                    ┌──────────────────────┐
      │ champ = NA   │                    │ RECHERCHER description│
      │ (non ambigu) │                    │ (/// ou description:) │
      └─────────────┘                    └───────────┬────────────┘
                                                       ▼
                                          ┌──────────────────────────┐
                                          │ Description présente ET   │
                                          │ significative ?           │
                                          └───────────────┬─────────────┘
                                        ┌───────────────────┴───────────────────┐
                                        ▼                                       ▼
                                  ╔═════════╗                             ┌────────────┐
                                  ║ OUI ✅  ║                             │ NON ❌     │
                                  ╚════╤════╝                             └─────┬──────┘
                                       ▼                                        ▼
                                ┌─────────────┐                       ┌─────────────┐
                                │ champ = OK   │                       │ champ = KO   │
                                └─────────────┘                       └─────────────┘
                 │ (répéter pour tous les champs visibles de toutes les tables)
                 ▼
     ┌──────────────────────────────────────┐
     │ CALCUL DU STATUT GLOBAL                │
     │ (les champs NA ne comptent jamais)     │
     │ Au moins un champ KO ? -> règle = KO   │
     │ Sinon                  -> règle = OK   │
     └────────────────────┬─────────────────────┘
                          ▼
                RETOUR rule_status
                (OK / KO)
```
