# BP-19 — Descriptions fonctionnelles renseignées pour les modèles réutilisables (« build datasets »)

## 1. Objectif de la bonne pratique

Un modèle sémantique destiné à être réutilisé comme source par d'autres rapports — parfois appelé « build dataset » ou modèle partagé/certifié dans l'écosystème Power BI — doit documenter ses objets pour que les auteurs de rapports tiers puissent comprendre le contenu d'une table ou le calcul exact d'une mesure **sans avoir à consulter le code M ou DAX sous-jacent**. En TMDL, cette documentation prend la forme de la propriété `description`, matérialisée par une ligne de commentaire `///` placée juste au-dessus de la déclaration de l'objet (`table`, `measure`, `column`).

L'objectif de cette règle est de vérifier que, pour les tables et les mesures d'un modèle marqué comme réutilisable, chaque objet dispose d'une description **non vide** et **suffisamment informative** (au-delà d'un simple seuil de longueur minimal, pour écarter les descriptions creuses du type reprise du nom technique de l'objet).

Un point de méthode important : la notion de « build dataset » (modèle certifié, promu, ou marqué comme source partagée) est un statut de **certification/promotion géré côté service Power BI** (workspace, métadonnées de l'élément dans le portail), et non une propriété stockée dans les fichiers TMDL locaux d'un projet PBIP. Cette règle ne peut donc pas déduire seule, à partir des fichiers du projet, si le modèle audité a vocation à être un « build dataset » : cette information doit être fournie explicitement en entrée d'audit (indicateur `is_build_dataset` du contexte de la demande). Sans cette indication, la règle ne doit pas supposer un statut par défaut.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport ou du modèle sémantique ;
- du nombre de tables et de mesures ;
- de la présence ou non d'une table dédiée aux mesures (convention `MEASURE` observée dans ce projet) ;
- de l'ordre des propriétés dans les fichiers TMDL.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl        (description de chaque table et de chaque mesure)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
```

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1 Syntaxe TMDL de la description

En TMDL, une ligne commençant par `///` immédiatement avant la déclaration d'un objet (`table <NOM>`, `measure <NOM> = ...`, `column <NOM>`) est compilée comme la propriété `description` de cet objet. L'absence de cette ligne équivaut à une description vide.

Extrait réel du projet audité (`MEASURE.tmdl`) illustrant les deux cas :

```tmdl
table MEASURE
	lineageTag: b57b7d33-f0e2-4901-960e-dd3acbdd73cf

	/// Percentage of adoption's respondent par usage
	measure pct_RespondentsPerUsage = ```
			VAR TotalRespondents = ...
			RETURN DIVIDE ( [Respondents_number], TotalRespondents )
			```
		formatString: 0%;-0%;0%
		displayFolder: USAGE
		lineageTag: 320df796-1696-477b-9805-04d792997a70

	measure Nb_Responses = COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN])
		formatString: 0
		displayFolder: CAMPAIGNS STATS
		lineageTag: 41157889-d0e7-4d7b-92ff-d870f629f75f
```

Dans cet extrait réel :
- la mesure `pct_RespondentsPerUsage` **possède** une description (`/// Percentage of adoption's respondent par usage`) → conforme ;
- la mesure `Nb_Responses` **n'a aucune ligne `///`** au-dessus de sa déclaration → non conforme ;
- la table `MEASURE` elle-même n'a pas de ligne `///` au-dessus de `table MEASURE` → non conforme au niveau table.

### 3.2 Seuil de longueur minimal

Une description de 3-4 caractères ou reprenant strictement le nom technique de l'objet (`"Nb_Responses"` comme description de la mesure `Nb_Responses`) n'apporte aucune information utile. L'agent applique un contrôle en deux temps :

```python
MIN_DESCRIPTION_LENGTH = 15   # paramètre configurable

def is_meaningful_description(description, object_name):
    if description is None:
        return False
    cleaned = description.strip()
    if len(cleaned) < MIN_DESCRIPTION_LENGTH:
        return False
    if cleaned.lower().replace("_", " ") == object_name.lower().replace("_", " "):
        return False   # description = simple reprise du nom technique
    return True
```

---

## 4. Règle(s) d'évaluation

*(applicable uniquement si le contexte d'audit indique `is_build_dataset = true`)*

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Table ou mesure avec description non vide, longueur suffisante, informative | `OK` | Documentation fonctionnelle exploitable par un réutilisateur externe. |
| Table ou mesure sans ligne `///` (description absente) | `KO` | Aucune documentation disponible pour cet objet. |
| Table ou mesure avec description présente mais trop courte ou reprenant simplement le nom technique | `KO` | Description non informative en pratique. |
| `is_build_dataset` non fourni ou `false` dans le contexte d'audit | `NA` (rule globale) | Hors périmètre : le modèle n'est pas identifié comme un dataset à vocation de réutilisation. |
| Colonnes du modèle (hors tables et mesures) | Hors périmètre de cette règle | Le brief cible explicitement les tables et les mesures ; la documentation des colonnes relève d'une bonne pratique distincte, non couverte ici. |

Exemple issu du modèle audité (en supposant `is_build_dataset = true`) :

| Objet | Type | Description détectée | Statut |
|---|---|---|---|
| `MEASURE` | table | absente | `KO` |
| `pct_RespondentsPerUsage` | mesure | « Percentage of adoption's respondent par usage » (47 caractères) | `OK` |
| `Nb_Responses` | mesure | absente | `KO` |
| `pct_Worry_Level_On_ALL` | mesure | « Ratio of responses at the current worry level against the total number of responses across all worry levels » | `OK` |
| `D_USERS` | table | absente | `KO` |

---

## 5. Parcours complet du modèle

### Étape 1 — Vérifier l'applicabilité de la règle
1. Lire l'indicateur `is_build_dataset` fourni dans le contexte d'audit.
2. Si absent ou `false`, retourner immédiatement `rule_status = NA` avec la raison « modèle non identifié comme build dataset réutilisable », sans analyser les fichiers.

### Étape 2 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Si aucun fichier n'est trouvé, retourner `NON_EVALUE`.

### Étape 3 — Analyser chaque table
Pour chaque fichier TMDL : extraire la description de la table elle-même (ligne `///` précédant `table <NOM>`) ; appliquer le contrôle de qualité de la section 3.2 ; enregistrer le résultat.

### Étape 4 — Analyser chaque mesure
Pour chaque bloc `measure` rencontré dans le fichier (y compris dans une table dédiée comme `MEASURE`, mais aussi dans toute table portant des mesures) : extraire la description (ligne `///` précédant `measure <NOM> = ...`) ; appliquer le contrôle de qualité ; enregistrer le résultat.

### Étape 5 — Ne pas s'arrêter à la première anomalie
L'agent doit parcourir l'intégralité des tables et de leurs mesures, même après un premier `KO`.

### Étape 6 — Terminer l'analyse
Produire le nombre total de tables et de mesures analysées, le nombre conforme, le détail des objets `KO` avec leur type et la raison précise (absence vs. trop courte/non informative).

---

## 6. Détection robuste / normalisation

- La ligne `///` doit être recherchée **immédiatement** au-dessus de la ligne de déclaration de l'objet, en ignorant les lignes vides éventuelles entre les deux, mais **pas** au-delà d'un bloc d'objet précédent (une description ne doit jamais être « empruntée » à l'objet précédent par erreur de parsing).
- Plusieurs lignes `///` consécutives doivent être concaténées en une seule description multi-lignes (cas d'une description longue répartie sur plusieurs lignes de commentaire).
- La comparaison entre la description et le nom technique de l'objet (pour détecter une reprise triviale du nom) doit être insensible à la casse et normaliser les séparateurs (`_`, espace) avant comparaison.
- Le seuil `MIN_DESCRIPTION_LENGTH` doit rester un paramètre configurable, jamais une constante figée arbitrairement sans possibilité d'ajustement par l'équipe d'audit.
- Les mesures peuvent être définies avec une expression DAX simple sur une seule ligne (`measure Nb_Responses = COUNT(...)`) ou une expression multi-lignes encadrée par des triples backticks (`measure pct_RespondentsPerUsage = ``` ... ``` `) : la détection de la description ne doit pas être perturbée par cette différence de syntaxe, la ligne `///` se trouvant toujours avant le mot-clé `measure` dans les deux cas.
- Une table peut ne contenir aucune mesure (table de dimension pure) : dans ce cas, seule sa propre description de table est évaluée, l'absence de mesures n'est pas une anomalie.

---

## 7. Pseudo-code détaillé

```python
MIN_DESCRIPTION_LENGTH = 15

def is_meaningful_description(description, object_name):
    if description is None:
        return False
    cleaned = " ".join(description.strip().split())
    if len(cleaned) < MIN_DESCRIPTION_LENGTH:
        return False
    normalized_desc = cleaned.lower().replace("_", " ")
    normalized_name = object_name.lower().replace("_", " ")
    if normalized_desc == normalized_name:
        return False
    return True

def extract_preceding_description(tmdl_lines, declaration_line_index):
    # Remonte les lignes juste au-dessus de la déclaration, tant qu'elles commencent par ///
    # (en tolérant des lignes vides intermédiaires), et les concatène.
    lines = []
    i = declaration_line_index - 1
    while i >= 0:
        stripped = tmdl_lines[i].strip()
        if stripped.startswith("///"):
            lines.insert(0, stripped.removeprefix("///").strip())
            i -= 1
        elif stripped == "":
            i -= 1
        else:
            break
    return " ".join(lines) if lines else None


def evaluate_documented_object(object_type, object_name, description):
    if not is_meaningful_description(description, object_name):
        reason = ("Description absente" if not description
                   else "Description trop courte ou reprenant simplement le nom technique")
        return {"object_type": object_type, "object_name": object_name,
                "status": "KO", "description": description, "reason": reason}
    return {"object_type": object_type, "object_name": object_name,
            "status": "OK", "description": description}


is_build_dataset = get_audit_context_flag("is_build_dataset")
if not is_build_dataset:
    return {"execution_status": "SUCCESS", "rule_status": "NA",
            "reason": "Modèle non identifié comme build dataset réutilisable (indicateur non fourni ou false)"}

table_files = find_all_tmdl_files("<SEMANTIC_MODEL_PATH>/definition/tables/")
if not table_files:
    return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
            "reason": "Aucun fichier de table TMDL trouvé"}

ok_results, ko_results = [], []

for table_file in table_files:
    tmdl_lines = read_file_lines(table_file)
    table_name, table_decl_index = find_table_declaration(tmdl_lines)
    table_description = extract_preceding_description(tmdl_lines, table_decl_index)

    result = evaluate_documented_object("table", table_name, table_description)
    (ok_results if result["status"] == "OK" else ko_results).append(result)

    for measure_name, measure_decl_index in find_all_measure_declarations(tmdl_lines):
        measure_description = extract_preceding_description(tmdl_lines, measure_decl_index)
        result = evaluate_documented_object("measure", measure_name, measure_description)
        (ok_results if result["status"] == "OK" else ko_results).append(result)
```

---

## 8. Calcul du statut global

```python
if not is_build_dataset:
    rule_status = "NA"
elif ko_results:
    rule_status = "KO"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK` (le `NA` global lié à `is_build_dataset = false` prime sur tout le reste, car l'analyse n'est alors pas exécutée).

| Résultat de l'analyse | Statut global |
|---|---|
| Modèle marqué build dataset, toutes les tables et mesures documentées | `OK` |
| Modèle marqué build dataset, au moins une table ou mesure sans description exploitable | `KO` |
| Modèle non marqué comme build dataset | `NA` |

---

## 9. Structure du résultat

Exemple `KO` (état actuel du projet audité, en supposant `is_build_dataset = true`) :

```json
{
  "rule_id": "BP-19",
  "rule_name": "Descriptions fonctionnelles renseignées pour les modèles réutilisables",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "is_build_dataset": true,
  "min_description_length": 15,
  "total_tables": 15,
  "total_measures": 42,
  "ok_objects": 31,
  "ko_objects": 26,
  "ko_details": [
    {"object_type": "table", "object_name": "MEASURE", "description": null, "reason": "Description absente"},
    {"object_type": "table", "object_name": "D_USERS", "description": null, "reason": "Description absente"},
    {"object_type": "measure", "object_name": "Nb_Responses", "description": null, "reason": "Description absente"}
  ]
}
```

Exemple `NA` :

```json
{
  "rule_id": "BP-19",
  "rule_name": "Descriptions fonctionnelles renseignées pour les modèles réutilisables",
  "execution_status": "SUCCESS",
  "rule_status": "NA",
  "reason": "Modèle non identifié comme build dataset réutilisable (indicateur non fourni ou false)"
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `NA`

```text
BP-19 — Descriptions pour modèle réutilisable : NON APPLICABLE

Le modèle audité n'a pas été signalé comme "build dataset" destiné à être
réutilisé comme source par d'autres rapports (indicateur is_build_dataset
non fourni). Cette règle n'a donc pas été évaluée.
```

### Exemple `KO`

```text
BP-19 — Descriptions pour modèle réutilisable : KO

31 objets documentés sur 57 (15 tables + 42 mesures) analysés.

Exemples d'objets sans description exploitable :
- Table MEASURE : aucune description.
- Table D_USERS : aucune description.
- Mesure Nb_Responses : aucune description (contrairement à
  pct_RespondentsPerUsage, correctement documentée : "Percentage of
  adoption's respondent par usage").

Correction attendue :
ajouter une ligne de commentaire /// au-dessus de chaque table et de
chaque mesure concernée, décrivant en une phrase son contenu fonctionnel
ou son mode de calcul (ex. "/// Nombre total de réponses enregistrées,
tous types de questionnaires confondus").
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- l'indicateur `is_build_dataset` a été explicitement fourni et vaut `true` (sinon le statut correct est `NA`, jamais `OK`) ;
- tous les fichiers de tables ont été lus ;
- chaque table a été évaluée pour sa propre description, indépendamment de ses mesures ;
- chaque mesure de chaque table a été évaluée individuellement, y compris dans les tables ne portant pas le nom `MEASURE` ;
- le contrôle de longueur minimale et de non-trivialité a été appliqué à chaque description trouvée, pas seulement sa présence ;
- aucune table ni mesure n'a été omise de l'analyse.

L'agent ne doit jamais produire `OK` si l'indicateur `is_build_dataset` est absent, si une seule description manque, ou si une description présente se limite à répéter le nom technique de l'objet.

---

## 12. Résumé de la règle

```text
RÈGLE BP-19

SI is_build_dataset != true
    règle = NA
    ARRÊTER

POUR chaque fichier de table TMDL
    EXTRAIRE la description de la table (ligne /// précédente)
    ÉVALUER cette description (présence + longueur + non-trivialité)

    POUR chaque mesure de la table
        EXTRAIRE la description de la mesure (ligne /// précédente)
        ÉVALUER cette description (présence + longueur + non-trivialité)
    FIN POUR
FIN POUR

SI au moins un objet (table ou mesure) sans description exploitable
    règle = KO
SINON
    règle = OK

AFFICHER tous les objets KO avec leur type et la raison (absente / trop
courte / reprise du nom technique)
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-19 — Descriptions pour modèles réutilisables              │
│ ("build dataset")                                                     │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ LIRE l'indicateur is_build_dataset        │
          │ du contexte d'audit                       │
          └────────────────┬───────────────────────────┘
               ┌───────────┴───────────┐
               ▼                       ▼
         ╔═════════════╗       ┌──────────────────┐
         ║ = true ✅   ║       │ absent / false ❌    │
         ╚══════╤══════╝       └─────────┬──────────┘
                │                        ▼
                │                ┌────────────────┐
                │                │ Retour global : │
                │                │ règle = NA       │
                │                │ (ARRÊTER)        │
                │                └────────────────┘
                ▼
     ┌────────────────────────────────────┐
     │ Lister tables/*.tmdl                  │
     └────────────────┬─────────────────────────┘
          ┌───────────┴───────────┐
          ▼                       ▼
    ╔═════════════╗       ┌──────────────────┐
    ║ Trouvés ✅  ║       │ Aucun fichier ❌     │
    ╚══════╤══════╝       └─────────┬──────────┘
           │                        ▼
           │                ┌────────────────┐
           │                │ Retour :        │
           │                │ NON_EVALUE      │
           │                └────────────────┘
           ▼
 ┌──────────────────────────────────────────┐
 │ POUR chaque fichier de table (boucle)       │
 │  EXTRAIRE la description de la TABLE        │
 │  (ligne /// précédente)                     │
 └────────────────┬───────────────────────────────┘
                  ▼
     ┌───────────────────────────────┐
     │ Description présente, longueur   │
     │ >= 15 ET != nom technique ?      │
     └──────────┬──────────────────────┘
          ┌──────┴──────┐
          ▼             ▼
    ╔═══════════╗ ┌──────────┐
    ║ OUI = OK  ║ │ NON = KO   │
    ╚═══════════╝ └──────────┘
          │             │
          └──────┬──────┘
                 ▼
 ┌──────────────────────────────────────────┐
 │ POUR chaque mesure de la table (boucle)     │
 │  EXTRAIRE la description de la MESURE       │
 │  (même contrôle présence/longueur/non-      │
 │  trivialité)                                 │
 └────────────────┬───────────────────────────────┘
                  ▼
          (mêmes branches OK / KO que ci-dessus)
                  │
                  ▼
   FIN DE BOUCLE (table/mesure suivante)
                  │
                  ▼
    ┌────────────────────────────────────────────┐
    │ CALCUL DU RÉSULTAT FINAL                      │
    │ is_build_dataset != true → règle = NA          │
    │ Sinon, au moins un objet KO → règle = KO       │
    │ Sinon                       → règle = OK       │
    └────────────────────┬───────────────────────────┘
                         ▼
             RETOUR rule_status (OK/KO/NA)
```
