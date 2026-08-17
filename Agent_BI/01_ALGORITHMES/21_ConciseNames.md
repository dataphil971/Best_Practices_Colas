# BP-21 — Noms d'objets concis, cohérents et conformes à la convention du modèle

## 1. Objectif de la bonne pratique

Les noms des objets d'un modèle sémantique (tables, colonnes, mesures, dossiers d'affichage) constituent la première interface entre le modèle et les utilisateurs métier qui construisent des rapports (volet des champs, info-bulles, recherche). Un nommage incohérent — espaces superflus, caractères ambigus, préfixes non respectés, casse variable — nuit à la lisibilité, complique la maintenance et peut provoquer des erreurs silencieuses (deux noms visuellement identiques mais techniquement différents à cause d'un espace final, par exemple).

L'objectif de cette règle est de vérifier que les noms des objets du modèle respectent une convention stable et déjà en place dans ce projet :

- les **tables** utilisent un préfixe fonctionnel : `D_` pour les dimensions, `F_` pour les faits, `T_` pour les tables techniques, `P_` pour les tables de paramétrage de présentation (légendes, ordres d'affichage), à l'exception de la table dédiée aux mesures (`MEASURE`), conventionnellement exemptée de préfixe ;
- les **colonnes** et **mesures** suivent une casse cohérente, sans espace superflu, sans caractère spécial ambigu ;
- les **dossiers d'affichage** (`displayFolder`) suivent la même exigence de propreté de nommage.

Cette règle doit être **générique et fondée sur la convention réellement observée dans le modèle audité**, pas sur une liste de préfixes universelle : si un projet différent utilisait par exemple `DIM_`/`FACT_` au lieu de `D_`/`F_`, la règle devrait s'adapter à la convention dominante détectée dans ce modèle plutôt que d'imposer un référentiel externe. Pour ce projet, la convention `D_`/`F_`/`P_`/`T_` est déjà majoritairement respectée et sert de référence à la validation.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de tables, colonnes et mesures ;
- de l'ordre des propriétés dans les fichiers TMDL ;
- de la langue utilisée dans les noms (français, anglais, mixte).

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl          (noms de tables, colonnes, mesures, displayFolder)
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl      (noms de colonnes référencés dans fromColumn/toColumn)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_CAMPAIGNS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\P_EVOLUTION_LEGEND_TOP.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\relationships.tmdl
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1 Inventaire des préfixes déjà en place dans ce projet

| Préfixe | Rôle | Exemples réels du projet |
|---|---|---|
| `D_` | Dimension | `D_CAMPAIGNS`, `D_USERS`, `D_CHOICE`, `D_USAGE_FREQUENCY_LEVELS` |
| `F_` | Fait | `F_ADOPTION_QUESTION`, `F_RESPONSES` |
| `T_` | Technique | `T_CHOICE_COUNTRY_JOB`, `T_NOTIFICATION`, `T_NOTIFICATION_TEXT`, `T_PAGE_NUMBER` |
| `P_` | Paramétrage de présentation | `P_EVOLUTION_LEGEND_TOP`, `P_EVOLUTION_LEGEND_BOTTOM`, `P_EVOLUTION_VALUE_TOP`, `P_EVOLUTION_VALUE_BOTTOM` |
| *(aucun)* | Table dédiée aux mesures — exemption conventionnelle | `MEASURE` |

### 3.2 Anomalies réelles détectées dans ce projet (`relationships.tmdl`)

```tmdl
relationship 12ca7fb2-4dee-f9cf-d271-dbdcbb0d26c7
	fromColumn: P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'
	toColumn: D_CHOICE.'ID '
```

Deux anomalies de nommage bien réelles apparaissent dans cet extrait, mises en évidence par l'obligation de les encadrer de guillemets simples en TMDL (signe systématique qu'un nom contient un caractère non standard, en particulier un espace) :

- `D_CHOICE.'ID '` : la colonne s'appelle littéralement `ID ` avec un **espace final** — violation directe de la convention « pas d'espace superflu » ;
- `P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'` : le nom `P_LEGEND Order` contient un **espace interne**, rompant la convention `UPPER_SNAKE_CASE` avec séparateur `_` respectée par la quasi-totalité des autres colonnes du modèle (`CAMPAIGN_ID`, `USER_JOB`, `USAGE_FREQUENCY_LEVELS`...).

### 3.3 Regex de validation

```python
import re

TABLE_NAME_PATTERN = re.compile(r"^(D_|F_|T_|P_)[A-Z0-9]+(_[A-Z0-9]+)*$")
TABLE_NAME_EXEMPTIONS = {"MEASURE"}   # convention établie de ce projet

COLUMN_NAME_PATTERN = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")   # UPPER_SNAKE_CASE sans espace

# Les mesures suivent une convention distincte mais elle-même cohérente dans ce projet
# (préfixe indiquant le type de résultat : pct_ pour un pourcentage, Nb_ pour un comptage) ;
# on exige seulement l'absence d'espace et de caractère spécial, pas une casse unique imposée.
MEASURE_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

LEADING_OR_TRAILING_WHITESPACE = re.compile(r"^\s|\s$")
INTERNAL_WHITESPACE = re.compile(r"\s")
```

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Nom de table conforme au motif préfixe + `UPPER_SNAKE_CASE`, ou nom `MEASURE` (exemption connue) | `OK` | Convention respectée. |
| Nom de table sans préfixe reconnu (`D_`/`F_`/`T_`/`P_`) et différent de `MEASURE` | `KO` | Rupture de la convention de préfixage du projet. |
| Nom d'objet (table, colonne, mesure ou `displayFolder`) avec espace en début ou fin de chaîne | `KO` | Espace superflu, source d'erreurs de correspondance silencieuses. |
| Nom de colonne avec espace interne (rompt la convention `UPPER_SNAKE_CASE` par ailleurs respectée) | `KO` | Incohérence avec le reste du modèle. |
| Nom de mesure avec espace interne | `KO` | Toléré techniquement en DAX, mais rompt la convention sans espace observée sur la majorité des autres mesures du projet. |
| Nom contenant un caractère spécial ambigu (accents, `#`, `%`, `/`, `\`, saut de ligne, guillemets internes non échappés) | `KO` | Risque de confusion ou d'erreur d'échappement dans les outils avals (DAX Studio, Tabular Editor, export). |
| Nom de `displayFolder` avec casse incohérente par rapport aux autres dossiers du même niveau (ex. `usage` vs `USAGE` vs `Usage` mélangés dans la même table) | `KO` | Incohérence de présentation par rapport à la convention observée dans le reste du modèle. |

Exemple issu du modèle audité :

| Objet | Type | Nom détecté | Anomalie | Statut |
|---|---|---|---|---|
| `D_CAMPAIGNS` | table | `D_CAMPAIGNS` | aucune | `OK` |
| `MEASURE` | table | `MEASURE` | aucune (exemption) | `OK` |
| `D_CHOICE.'ID '` | colonne | `ID ` | espace final | `KO` |
| `P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'` | colonne | `P_LEGEND Order` | espace interne | `KO` |
| `pct_RespondentsPerUsage` | mesure | `pct_RespondentsPerUsage` | aucune | `OK` |
| `Nb_Responses` | mesure | `Nb_Responses` | aucune | `OK` |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Charger `relationships.tmdl` pour récupérer les noms de colonnes qui y sont référencés (utile en complément de la lecture directe des fichiers de table, notamment pour les noms nécessitant un échappement).
3. Si aucun fichier de table n'est trouvé, retourner `NA` (information indisponible pour conclure).

### Étape 2 — Contrôler chaque nom de table
Pour chaque fichier `tables\<NOM>.tmdl`, extraire le nom réel de la table (déclaration `table <NOM>`) et appliquer `TABLE_NAME_PATTERN` (avec l'exemption `MEASURE`).

### Étape 3 — Contrôler chaque colonne et chaque mesure
Pour chaque bloc `column` et `measure` de chaque table : extraire le nom exact (y compris les espaces et caractères éventuellement présents, sans les « nettoyer » avant contrôle) ; appliquer les motifs de la section 3.3 ; détecter séparément les espaces en début/fin et les espaces internes.

### Étape 4 — Contrôler chaque `displayFolder`
Pour chaque mesure ou colonne portant un `displayFolder`, extraire sa valeur et vérifier l'absence d'espace superflu ainsi que la cohérence de casse par rapport aux autres `displayFolder` du même niveau hiérarchique dans la même table.

### Étape 5 — Ne pas s'arrêter à la première anomalie
L'agent doit parcourir l'intégralité des tables, colonnes, mesures et dossiers d'affichage, en recensant toutes les violations, pas seulement la première.

### Étape 6 — Terminer l'analyse
Produire le nombre total d'objets analysés par catégorie, la répartition `OK`/`KO`/`NA`, et le détail complet des objets `KO` avec le type d'anomalie précis.

---

## 6. Détection robuste / normalisation

- Un nom contenant un espace, un caractère spécial ou commençant par un chiffre est automatiquement encadré de guillemets simples par TMDL (`'ID '`, `'P_LEGEND Order'`, `'REPORT NAME'`) : la présence de ces guillemets est en elle-même un **signal fort** qu'une anomalie de nommage est probable, mais l'agent doit tout de même appliquer les motifs de validation sur le nom réel (guillemets retirés), car certains noms légitimement entre guillemets peuvent malgré tout être conformes selon la convention retenue (ex. un nom commençant par un chiffre dans un cas métier valide).
- L'agent ne doit **jamais** appliquer `strip()` avant de détecter un espace en début/fin de nom : c'est précisément la présence de cet espace dans le nom réel qui constitue l'anomalie à signaler (contrairement à d'autres règles du référentiel où la normalisation des espaces sert à la comparaison, ici l'espace fait partie de la donnée à évaluer).
- La casse doit être analysée sans normalisation forcée : la règle ne doit pas convertir automatiquement en majuscules avant de comparer, sous peine de masquer une incohérence de casse réelle (ex. `Usage` vs `USAGE`).
- Les noms de mesures suivant des préfixes de convention (`pct_`, `Nb_`) ne doivent pas être signalés comme non conformes du seul fait de mélanger majuscules et minuscules : cette règle valide uniquement l'absence d'espace/caractère ambigu pour les mesures, pas une casse unique imposée, car la convention observée dans ce projet mélange déjà plusieurs styles de façon volontaire et cohérente (indicateur de type de résultat en préfixe).
- Le préfixe de table doit être recherché en tête de chaîne uniquement (`^(D_|F_|T_|P_)`), jamais n'importe où dans le nom, pour éviter un faux positif sur une table dont le nom contiendrait incidemment la séquence `D_` ailleurs que comme préfixe.
- Les identifiants de relation (GUID ou `AutoDetected_<GUID>`) ne sont pas soumis à cette règle : ce sont des identifiants techniques internes, non des noms d'objets métier.

---

## 7. Pseudo-code détaillé

```python
import re

TABLE_NAME_PATTERN = re.compile(r"^(D_|F_|T_|P_)[A-Z0-9]+(_[A-Z0-9]+)*$")
TABLE_NAME_EXEMPTIONS = {"MEASURE"}
COLUMN_NAME_PATTERN = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")
MEASURE_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
LEADING_OR_TRAILING_WHITESPACE = re.compile(r"^\s|\s$")
INTERNAL_WHITESPACE = re.compile(r"\s")
SPECIAL_CHAR_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)   # hors lettres/chiffres/_/espace

def check_table_name(name):
    if name in TABLE_NAME_EXEMPTIONS:
        return {"status": "OK"}
    if LEADING_OR_TRAILING_WHITESPACE.search(name):
        return {"status": "KO", "reason": "Espace en début ou fin de nom de table"}
    if not TABLE_NAME_PATTERN.match(name):
        return {"status": "KO", "reason": "Préfixe de table non reconnu (attendu D_/F_/T_/P_)"}
    return {"status": "OK"}

def check_column_name(name):
    if LEADING_OR_TRAILING_WHITESPACE.search(name):
        return {"status": "KO", "reason": "Espace en début ou fin de nom de colonne"}
    if SPECIAL_CHAR_PATTERN.search(name.replace("_", "")):
        return {"status": "KO", "reason": "Caractère spécial ambigu dans le nom de colonne"}
    if INTERNAL_WHITESPACE.search(name):
        return {"status": "KO", "reason": "Espace interne dans le nom de colonne (attendu UPPER_SNAKE_CASE)"}
    if not COLUMN_NAME_PATTERN.match(name):
        return {"status": "KO", "reason": "Casse ou format non conforme à la convention UPPER_SNAKE_CASE"}
    return {"status": "OK"}

def check_measure_name(name):
    if LEADING_OR_TRAILING_WHITESPACE.search(name):
        return {"status": "KO", "reason": "Espace en début ou fin de nom de mesure"}
    if INTERNAL_WHITESPACE.search(name):
        return {"status": "KO", "reason": "Espace interne toléré en DAX mais incohérent avec la convention du modèle"}
    if not MEASURE_NAME_PATTERN.match(name):
        return {"status": "KO", "reason": "Caractère spécial ambigu dans le nom de mesure"}
    return {"status": "OK"}


ok_results, ko_results = [], []

table_files = find_all_tmdl_files("<SEMANTIC_MODEL_PATH>/definition/tables/")
if not table_files:
    return {"execution_status": "ERROR", "rule_status": "NA",
            "reason": "Aucun fichier de table TMDL trouvé"}

for table_file in table_files:
    table = parse_tmdl_table(table_file, preserve_raw_names=True)  # ne pas strip() les noms

    result = check_table_name(table.name)
    entry = {"object_type": "table", "object_name": repr(table.name), **result}
    (ok_results if result["status"] == "OK" else ko_results).append(entry)

    for column in table.columns:
        result = check_column_name(column.name)
        entry = {"object_type": "column", "object_name": f"{table.name}.{repr(column.name)}", **result}
        (ok_results if result["status"] == "OK" else ko_results).append(entry)

    for measure in table.measures:
        result = check_measure_name(measure.name)
        entry = {"object_type": "measure", "object_name": f"{table.name}.{repr(measure.name)}", **result}
        (ok_results if result["status"] == "OK" else ko_results).append(entry)
```

---

## 8. Calcul du statut global

```python
if not table_files:
    rule_status = "NA"
elif ko_results:
    rule_status = "KO"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Tous les noms d'objets respectent la convention | `OK` |
| Au moins une violation (espace en tête/fin/interne, préfixe manquant, caractère spécial, casse de `displayFolder` incohérente) | `KO` |
| Aucun fichier de table TMDL trouvé | `NA` |

---

## 9. Structure du résultat

Exemple `OK` (hypothèse d'un modèle entièrement nettoyé) :

```json
{
  "rule_id": "BP-21",
  "rule_name": "Noms d'objets concis, cohérents et conformes à la convention du modèle",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_tables": 15,
  "total_columns": 69,
  "total_measures": 42,
  "ok_objects": 126,
  "ko_objects": 0,
  "ko_details": []
}
```

Exemple `KO` (état réel constaté dans ce projet) :

```json
{
  "rule_id": "BP-21",
  "rule_name": "Noms d'objets concis, cohérents et conformes à la convention du modèle",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_tables": 15,
  "total_columns": 69,
  "total_measures": 42,
  "ok_objects": 124,
  "ko_objects": 2,
  "ko_details": [
    {"object_type": "column", "object_name": "D_CHOICE.'ID '",
     "reason": "Espace en début ou fin de nom de colonne"},
    {"object_type": "column", "object_name": "P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'",
     "reason": "Espace interne dans le nom de colonne (attendu UPPER_SNAKE_CASE)"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-21 — Convention de nommage des objets : OK

126 objets analysés (15 tables, 69 colonnes, 42 mesures). Tous respectent
la convention de préfixage D_/F_/T_/P_ pour les tables et l'absence
d'espace/caractère ambigu pour les colonnes et mesures.
```

### Exemple `KO`

```text
BP-21 — Convention de nommage des objets : KO

124 objets conformes sur 126 analysés.

Objets non conformes :
- D_CHOICE."ID " : la colonne comporte un espace final dans son nom
  technique, visible dans relationships.tmdl (toColumn: D_CHOICE.'ID ').
- P_EVOLUTION_LEGEND_TOP."P_LEGEND Order" : le nom contient un espace
  interne, rompant la convention UPPER_SNAKE_CASE respectée par les autres
  colonnes du modèle (ex. CAMPAIGN_ID, USAGE_FREQUENCY_LEVELS).

Correction attendue :
renommer la colonne D_CHOICE.'ID ' en D_CHOICE.ID (sans espace final) et
P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order' en
P_EVOLUTION_LEGEND_TOP.P_LEGEND_ORDER, en mettant à jour en parallèle les
relations qui les référencent dans relationships.tmdl.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- tous les fichiers de tables ont été lus, ainsi que `relationships.tmdl` en complément ;
- les noms d'objets ont été extraits **sans** être nettoyés (`strip()`) avant contrôle, afin de ne pas masquer un espace superflu ;
- chaque table, chaque colonne et chaque mesure a été analysée individuellement ;
- le préfixe de chaque table a été vérifié en tête de chaîne, avec la seule exemption `MEASURE` documentée ;
- chaque `displayFolder` a été contrôlé pour l'absence d'espace superflu et la cohérence de casse au sein d'une même table ;
- aucune anomalie détectée dans `relationships.tmdl` (noms de colonnes entre guillemets simples) n'a été omise du croisement avec les fichiers de tables.

L'agent ne doit jamais produire `OK` si un seul nom d'objet présente un espace en début/fin de chaîne, un caractère spécial ambigu, ou un préfixe de table non reconnu.

---

## 12. Résumé de la règle

```text
RÈGLE BP-21

SI aucun fichier de table TMDL trouvé
    règle = NA
    FIN

POUR chaque fichier de table TMDL
    EXTRAIRE le nom de la table SANS le nettoyer (préserver espaces éventuels)

    SI nom de table != "MEASURE"
        SI espace en tête/fin OU préfixe non conforme (D_/F_/T_/P_)
            table = KO
        SINON
            table = OK

    POUR chaque colonne
        SI espace en tête/fin OU caractère spécial ambigu OU espace interne
           OU casse non UPPER_SNAKE_CASE
            colonne = KO
        SINON
            colonne = OK

    POUR chaque mesure
        SI espace en tête/fin OU caractère spécial ambigu OU espace interne
            mesure = KO
        SINON
            mesure = OK

    POUR chaque displayFolder
        SI espace en tête/fin OU casse incohérente avec les autres dossiers du niveau
            displayFolder = KO

    ENREGISTRER chaque résultat avec le nom exact (guillemets/espaces préservés dans la preuve)
FIN POUR

SI au moins un objet KO
    règle = KO
SINON
    règle = OK

AFFICHER tous les objets KO avec le renommage recommandé
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-21 — Noms d'objets concis et conformes à la convention    │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ Lister tables/*.tmdl                       │
          │ Charger relationships.tmdl (noms entre        │
          │ guillemets simples)                            │
          └────────────────┬───────────────────────────────┘
               ┌───────────┴───────────┐
               ▼                       ▼
         ╔═════════════╗       ┌──────────────────┐
         ║ Trouvés ✅  ║       │ Aucun fichier ❌      │
         ╚══════╤══════╝       └─────────┬──────────┘
                │                        ▼
                │                ┌────────────────┐
                │                │ Retour :          │
                │                │ NA                │
                │                └────────────────┘
                ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque table TMDL (boucle)               │
     │ EXTRAIRE le nom SANS le nettoyer (strip)       │
     └────────────────┬───────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ Nom = "MEASURE" (exemption) ?    │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ╔═══════════╗ ┌───────────────────────┐
       ║ OUI = OK  ║ │ NON : espace tête/fin      │
       ╚═══════════╝ │ OU préfixe non conforme     │
                      │ (D_/F_/T_/P_) ?             │
                      └──────────┬─────────────────┘
                           ┌──────┴──────┐
                           ▼             ▼
                     ╔═══════════╗ ┌──────────┐
                     ║ OUI = KO  ║ │ NON = OK   │
                     ╚═══════════╝ └──────────┘
                           │             │
                           └──────┬──────┘
                                 ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque colonne de la table (boucle)      │
     └────────────────┬───────────────────────────────┘
                      ▼
        ┌────────────────────────────────┐
        │ Espace tête/fin OU caractère       │
        │ spécial ambigu OU espace interne    │
        │ OU casse non UPPER_SNAKE_CASE ?     │
        └──────────┬───────────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ╔═══════════╗ ┌──────────┐
       ║ OUI = KO  ║ │ NON = OK   │
       ╚═══════════╝ └──────────┘
             │             │
             └──────┬──────┘
                    ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque mesure de la table (boucle)       │
     └────────────────┬───────────────────────────────┘
                      ▼
        ┌────────────────────────────────┐
        │ Espace tête/fin OU caractère       │
        │ spécial ambigu OU espace interne    │
        └──────────┬───────────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ╔═══════════╗ ┌──────────┐
       ║ OUI = KO  ║ │ NON = OK   │
       ╚═══════════╝ └──────────┘
             │             │
             └──────┬──────┘
                    ▼
   FIN DE BOUCLE (table/colonne/mesure suivante)
                                 │
                                 ▼
    ┌────────────────────────────────────────────┐
    │ CALCUL DU RÉSULTAT FINAL                        │
    │ KO présent ?              → règle = KO             │
    │ Sinon                      → règle = OK            │
    │ (NA si aucun fichier de table TMDL trouvé)          │
    └────────────────────┬───────────────────────────────┘
                         ▼
             RETOUR rule_status (OK/KO/NA)
```
