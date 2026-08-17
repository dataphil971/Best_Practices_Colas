# BP-09 — Désactiver l'option globale « Auto Date/Time »

## 1. Objectif de la bonne pratique

Lorsque l'option Power BI Desktop « Auto Date/Time » (aussi appelée time intelligence automatique) est activée, le moteur crée **silencieusement une table de dates cachée par colonne de type date/heure** présente dans le modèle, afin de permettre l'usage direct des fonctions de hiérarchie temporelle (Année/Trimestre/Mois/Jour) dans le volet des champs. Chacune de ces tables cachées consomme de la mémoire supplémentaire dans le moteur VertiPaq et allonge le temps de rafraîchissement, sans que l'utilisateur du modèle n'en ait conscience — le coût est proportionnel au nombre de colonnes de type date/heure du modèle, pas à un seul coût fixe. Cette fonctionnalité fait, de plus, double emploi avec une **table de dates dédiée** correctement conçue et marquée ([BP-02](02_DateTable.md)), qui doit être la source unique de vérité pour toute time intelligence dans un modèle bien gouverné.

L'objectif de cette règle est de vérifier que l'option « Auto Date/Time » est **désactivée** au niveau du modèle. Dans un projet Power BI au format PBIP/TMDL, ce réglage se matérialise par l'annotation `__PBI_TimeIntelligenceEnabled` au niveau du fichier `model.tmdl` : la valeur `0` signifie que l'option est désactivée (aucune table de dates cachée n'est générée), la valeur `1` (ou l'absence de l'annotation, qui correspond au comportement par défaut historique de Power BI Desktop) signifie qu'elle est active.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de colonnes de type date/heure présentes dans le modèle ;
- de la présence ou non d'une table de dates dédiée déjà en place ;
- de l'ordre des propriétés et annotations dans `model.tmdl`.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\model.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\model.tmdl
```

L'agent doit charger l'intégralité de ce fichier unique — contrairement à la plupart des autres règles du référentiel, cette bonne pratique ne dépend pas des fichiers de tables individuelles mais d'un réglage global déclaré une seule fois au niveau du modèle.

---

## 3. Élément(s) / propriété(s) à contrôler

La propriété décisionnelle est l'annotation suivante, déclarée directement sous le bloc `model` de `model.tmdl` :

```tmdl
model Model
	culture: fr-FR
	defaultPowerBIDataSourceVersion: powerBI_V3
	sourceQueryCulture: en-US
	dataAccessOptions
		legacyRedirects
		returnErrorValuesAsNull

...

annotation __PBI_TimeIntelligenceEnabled = 0
```

Dans ce projet, la valeur observée est `0` : l'option « Auto Date/Time » est **désactivée** au niveau du modèle. L'agent doit lire exclusivement cette annotation ; les autres annotations globales du fichier (`PBI_QueryOrder`, `PBI_ProTooling`, les blocs `queryGroup`) ne participent jamais au verdict de cette règle.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `annotation __PBI_TimeIntelligenceEnabled = 0` | `OK` | Auto Date/Time désactivée : aucune table de dates cachée générée. |
| `annotation __PBI_TimeIntelligenceEnabled = 1` | `KO` | Auto Date/Time activée : une table de dates cachée est générée pour chaque colonne date/heure du modèle. |
| Annotation `__PBI_TimeIntelligenceEnabled` absente du fichier `model.tmdl` | `KO` | Absence d'annotation explicite : Power BI applique le comportement par défaut historique, qui est activé, sauf configuration contraire au niveau de l'installation — à traiter comme non conforme tant que le réglage n'est pas explicitement désactivé. |
| Valeur de l'annotation illisible ou non numérique (`__PBI_TimeIntelligenceEnabled = <valeur inattendue>`) | `NA` | Impossible d'interpréter le réglage de façon fiable. |
| `model.tmdl` introuvable ou illisible | `NA` (au niveau technique `NON_EVALUE`) | Impossible d'accéder au fichier source du réglage. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Accéder à `<SEMANTIC_MODEL_PATH>\definition\model.tmdl`.
2. Vérifier que le fichier existe et est accessible en lecture.
3. Si le fichier est introuvable, retourner `NON_EVALUE`.

### Étape 2 — Rechercher l'annotation
Parcourir l'intégralité du fichier (l'annotation peut être positionnée n'importe où dans le fichier, généralement après les déclarations de `queryGroup` et avant les références `ref table`) à la recherche de la ligne `annotation __PBI_TimeIntelligenceEnabled = <valeur>`.

### Étape 3 — Interpréter la valeur
Extraire la valeur brute, la normaliser, et la comparer aux valeurs attendues (`0` ou `1`).

### Étape 4 — Compléter l'analyse avec le contexte du modèle (optionnel mais recommandé)
Pour renforcer le diagnostic, l'agent peut recenser le nombre de colonnes de type `dateTime`/`date` présentes dans les fichiers `tables/*.tmdl` : si l'annotation est absente ou active (`KO`) et que plusieurs colonnes de ce type existent, le message utilisateur peut chiffrer l'impact potentiel (nombre de tables de dates cachées susceptibles d'être générées).

### Étape 5 — Terminer l'analyse
Produire : la valeur brute trouvée pour l'annotation ; le statut résultant ; en cas de `KO`, le nombre de colonnes date/heure recensées dans le modèle, à titre d'indicateur de l'impact.

---

## 6. Détection robuste / normalisation

**Recherche indépendante de la position** : l'annotation `__PBI_TimeIntelligenceEnabled` n'est pas nécessairement la première ligne après le bloc `model` — dans ce projet, elle apparaît après plusieurs blocs `queryGroup` et avant l'annotation `PBI_QueryOrder`. L'agent doit rechercher la ligne par son nom de propriété dans l'intégralité du fichier, sans dépendre d'un numéro de ligne fixe.

```python
def find_annotation(model_tmdl_text, annotation_name):
    pattern = re.compile(rf"^\s*annotation\s+{re.escape(annotation_name)}\s*=\s*(.+)$", re.MULTILINE)
    match = pattern.search(model_tmdl_text)
    return match.group(1).strip() if match else None
```

**Normalisation de la valeur** : suppression des espaces, comparaison sous forme de chaîne pour tolérer `0`, `"0"`, `0 ` :

```python
def normalize_flag(raw_value):
    if raw_value is None:
        return None
    return str(raw_value).strip().strip('"').strip("'")
```

**Distinction entre absence et désactivation explicite** : l'absence de l'annotation ne doit **jamais** être interprétée comme équivalente à `0` — Power BI Desktop active l'option par défaut à la création d'un nouveau modèle tant qu'elle n'a pas été désactivée explicitement dans les options de fichier (Options du fichier > Options de données > Time Intelligence), ce qui matérialise systématiquement l'annotation à `0` une fois désactivée. Une absence d'annotation dans un fichier `model.tmdl` généré par export TMDL doit donc être traitée avec la même sévérité qu'une valeur `1`.

**Recensement des colonnes date/heure pour le contexte** : réutilise la même détection que [BP-02](02_DateTable.md) (`dataType` égal à `dateTime` ou `date`), appliquée à toutes les colonnes de toutes les tables, sans se limiter à la table de dates candidate.

---

## 7. Pseudo-code détaillé

```python
def evaluate_auto_date_time(model_tmdl_path, table_files):
    if not file_exists(model_tmdl_path):
        return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
                "reason": "Fichier model.tmdl introuvable"}

    model_text = read_file(model_tmdl_path)
    raw_value = find_annotation(model_text, "__PBI_TimeIntelligenceEnabled")
    normalized = normalize_flag(raw_value)

    date_columns = []
    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        for column in table.columns:
            dtype = str(column.get_property("dataType") or "").strip().lower()
            if dtype in {"datetime", "date"}:
                date_columns.append({"table": table.name, "column": column.name})

    if normalized is None:
        return {
            "rule_status": "KO",
            "annotation_found": False,
            "reason": "Annotation __PBI_TimeIntelligenceEnabled absente : Auto Date/Time réputée active par défaut",
            "impacted_date_columns": date_columns,
        }

    if normalized == "0":
        return {"rule_status": "OK", "annotation_found": True, "raw_value": raw_value}

    if normalized == "1":
        return {
            "rule_status": "KO",
            "annotation_found": True,
            "raw_value": raw_value,
            "reason": "Auto Date/Time explicitement activée",
            "impacted_date_columns": date_columns,
        }

    return {"rule_status": "NA", "annotation_found": True, "raw_value": raw_value,
            "reason": "Valeur de l'annotation non interprétable"}
```

---

## 8. Calcul du statut global

```python
rule_status = result["rule_status"]   # déjà déterminé lors de l'évaluation unique (une seule annotation à contrôler)
```

Contrairement aux règles portant sur un ensemble de colonnes ou de requêtes, cette bonne pratique porte sur un **réglage unique** au niveau du modèle : il n'y a pas d'agrégation de plusieurs résultats élémentaires. La priorité `KO > NA > OK` reste néanmoins respectée dans la hiérarchie d'interprétation :

| Résultat de l'analyse | Statut global |
|---|---|
| `annotation __PBI_TimeIntelligenceEnabled = 0` | `OK` |
| `annotation __PBI_TimeIntelligenceEnabled = 1` | `KO` |
| Annotation absente du fichier | `KO` |
| Valeur illisible/non numérique | `NA` |
| Fichier `model.tmdl` introuvable | `NON_EVALUE` (technique, distinct du triplet `OK`/`KO`/`NA`) |

---

## 9. Structure du résultat

Exemple lorsque la bonne pratique est respectée (état actuel du projet audité) :

```json
{
  "rule_id": "BP-09",
  "rule_name": "Désactiver l'option globale Auto Date/Time",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "annotation_found": true,
  "raw_value": "0",
  "source_file": "AI_BAROMETER_BI-CDS.SemanticModel/definition/model.tmdl"
}
```

Exemple avec option activée ou annotation absente :

```json
{
  "rule_id": "BP-09",
  "rule_name": "Désactiver l'option globale Auto Date/Time",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "annotation_found": false,
  "reason": "Annotation __PBI_TimeIntelligenceEnabled absente : Auto Date/Time réputée active par défaut",
  "impacted_date_columns": [
    {"table": "D_DATES", "column": "DATE"},
    {"table": "T_NOTIFICATION", "column": "PUBLICATION_DATE"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK` (état actuel du projet audité)

```text
BP-09 — Option Auto Date/Time : OK

L'annotation __PBI_TimeIntelligenceEnabled du fichier
AI_BAROMETER_BI-CDS.SemanticModel/definition/model.tmdl est réglée
sur 0 : l'option Auto Date/Time est désactivée. Aucune table de dates
cachée n'est générée automatiquement par Power BI.
```

### Exemple `KO`

```text
BP-09 — Option Auto Date/Time : KO

L'annotation __PBI_TimeIntelligenceEnabled est absente (ou réglée sur
1) dans model.tmdl : l'option Auto Date/Time est active par défaut.

2 colonnes de type date/heure ont été recensées dans le modèle
(D_DATES[DATE], T_NOTIFICATION[PUBLICATION_DATE]) : chacune peut
générer une table de dates cachée distincte, redondante avec toute
table de dates dédiée déjà présente dans le modèle.

Correction attendue :
dans Power BI Desktop, ouvrir Fichier > Options et paramètres >
Options pour le fichier actif > Time Intelligence, décocher
"Activer Auto Date/Time", puis enregistrer le fichier pour que
l'annotation __PBI_TimeIntelligenceEnabled = 0 soit écrite dans
model.tmdl.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- `model.tmdl` a été localisé et intégralement lu ;
- l'annotation `__PBI_TimeIntelligenceEnabled` a été recherchée dans l'intégralité du fichier, indépendamment de sa position ;
- l'annotation est présente **et** sa valeur normalisée est strictement `0` ;
- aucune ambiguïté n'existe sur la valeur lue (pas de troncature, pas de valeur non numérique).

L'agent ne doit jamais produire `OK` en cas d'absence de l'annotation : ce cas doit systématiquement être traité comme `KO`, car il correspond au comportement par défaut activé de Power BI Desktop, jamais présumé désactivé par prudence.

---

## 12. Résumé de la règle

```text
RÈGLE BP-09

LOCALISER model.tmdl
SI fichier introuvable
    règle = NON_EVALUE

RECHERCHER annotation __PBI_TimeIntelligenceEnabled dans tout le fichier

SI annotation absente
    règle = KO (comportement par défaut activé, jamais présumé désactivé)
SINON
    NORMALISER la valeur brute
    SI valeur = 0
        règle = OK
    SINON SI valeur = 1
        règle = KO
    SINON
        règle = NA

SI règle = KO
    RECENSER les colonnes date/heure de toutes les tables (impact potentiel)

AFFICHER le statut avec la valeur brute lue et l'impact estimé si KO
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-09 — Désactiver l'option globale Auto Date/Time      │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │ Localiser                     │
          │ <SEMANTIC_MODEL_PATH>\         │
          │ definition\model.tmdl          │
          └──────────────┬────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ Trouvé ✅   ║    │ Fichier introuvable ❌ │
         ╚════╤════════╝    └──────────┬────────────┘
              │                        ▼
              │                ┌───────────────────┐
              │                │ Retour : NON_EVALUE│
              │                └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ RECHERCHER l'annotation                     │
   │ __PBI_TimeIntelligenceEnabled dans            │
   │ l'intégralité du fichier (position libre)     │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ Annotation présente ?                 │
        └───────┬──────────────────┬───────────┘
              non│                  │oui
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────────┐
         ║ règle = KO    ║  │ NORMALISER la valeur brute   │
         ║ (comportement ║  │ (espaces, guillemets)         │
         ║  par défaut   ║  └───────────────┬─────────────────┘
         ║  activé,      ║                  ▼
         ║  jamais       ║   ┌────────────────────────────────────┐
         ║  présumé      ║   │ Valeur = "0" ?  │ = "1" ?  │ autre ? │
         ║  désactivé)   ║   └──────┬────────────┬────────────┬─────┘
         ╚═══════════════╝       "0"│         "1"│      illisible│
                                     ▼             ▼               ▼
                          ╔═══════════════╗ ╔═══════════════╗ ╔═══════════════╗
                          ║ règle = OK    ║ ║ règle = KO    ║ ║ règle = NA    ║
                          ╚═══════════════╝ ╚═══════════════╝ ╚═══════════════╝
                       │
                       ▼ (chemin commun aux deux verdicts KO)
        ┌────────────────────────────────────────────┐
        │ SI règle = KO :                              │
        │ POUR chaque table de tables/*.tmdl (boucle    │
        │ secondaire, contexte seulement)               │
        │   RECENSER les colonnes dataType date/dateTime│
        │   (impact potentiel — n'influence pas le       │
        │    verdict, déjà déterminé ci-dessus)           │
        └──────────────────┬────────────────────────────┘
                           ▼
                RETOUR rule_status (OK / KO / NA)
                avec la valeur brute lue et, si KO,
                l'impact estimé (colonnes date/heure)
```
