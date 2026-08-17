# BP-31 — Détection des patrons DAX à risque de performance

## 1. Objectif de la bonne pratique

L'objectif de cette règle est d'identifier, dans le code DAX des mesures du modèle sémantique, la présence de patrons connus pour dégrader les performances de calcul à l'échelle : `FILTER` appliqué sur une table entière plutôt que sur une seule colonne (empêchant l'optimisation du moteur de stockage), imbrications multiples de `CALCULATE`, usage de `EARLIER` (fonction historique, généralement remplaçable par une `VAR` plus lisible et souvent plus performante), itérateurs de ligne (`SUMX`, `AVERAGEX`, `FILTER`) appliqués à des tables volumineuses sans réduction préalable du contexte. Cette règle ne remplace pas un profilage réel : elle produit une liste de mesures **candidates** à un examen approfondi avec DAX Studio (analyse du plan de requête et des Server Timings), afin de prioriser l'effort d'optimisation sur les mesures les plus susceptibles de poser problème en production, en particulier sur de gros volumes ou des visuels à fort niveau de détail.

Cette règle est de nature heuristique et non garantie : un patron détecté n'est pas nécessairement problématique en pratique (cela dépend du volume de données, de la cardinalité des colonnes, du contexte de filtre réel), c'est pourquoi elle produit des recommandations (`WARN`) plutôt que des non-conformités bloquantes (`KO`), sauf pour les patrons les plus systématiquement problématiques.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre total de mesures ;
- de la table et des colonnes référencées ;
- du format d'écriture de l'expression DAX (ligne unique ou triple backticks).

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
```

---

## 3. Élément(s) / propriété(s) à contrôler

Patrons recherchés dans le corps DAX de chaque mesure :

**`FILTER` sur une table entière plutôt qu'une colonne** — pattern à risque :

```dax
CALCULATE ( [Nb_Responses], FILTER ( F_RESPONSES, F_RESPONSES[WORRY_LEVEL] = "High" ) )
```

Pattern préférable (filtre sur colonne, exploitable par le moteur de stockage sans matérialiser la table) :

```dax
CALCULATE ( [Nb_Responses], F_RESPONSES[WORRY_LEVEL] = "High" )
```

**`CALCULATE` imbriqués multiples**, observés dans une variante hypothétique à risque :

```dax
CALCULATE (
    CALCULATE ( [Nb_Responses], F_RESPONSES[WORRY_LEVEL] = "High" ),
    ALL ( F_RESPONSES[WORRY_LEGEND] )
)
```

**Usage de `EARLIER`** — fonction à contexte de ligne implicite, source d'erreurs et généralement remplaçable :

```dax
= SUMX ( F_RESPONSES, CALCULATE ( COUNTROWS ( F_RESPONSES ), F_RESPONSES[WORRY_LEVEL] = EARLIER ( F_RESPONSES[WORRY_LEVEL] ) ) )
```

**Itérateur sur une table volumineuse sans réduction préalable du contexte**, exemple réel du modèle audité (`Respondents_number`) :

```tmdl
measure Respondents_number = ```
        CALCULATE (
            DISTINCTCOUNT ( F_ADOPTION_QUESTION[CAMPAIGN_USER_LOGIN] ),
            CROSSFILTER ( D_USERS[CAMPAIGN_USER_LOGIN], F_RESPONSES[CAMPAIGN_USER_LOGIN], BOTH )
        )
        ```
```

Ici, `CROSSFILTER ( ..., BOTH )` force une propagation de filtre bidirectionnelle sur une relation ; ce n'est pas un itérateur au sens strict, mais un pattern à signaler car `BOTH` peut dégrader les performances et créer des comportements de filtrage ambigus sur un modèle en étoile — à documenter comme un choix assumé plutôt qu'à interdire systématiquement.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Aucun patron à risque détecté dans l'expression DAX de la mesure | `OK` | Rien à signaler pour cette mesure. |
| `FILTER` appliqué directement sur une table entière (`FILTER ( NomTable, ... )`) alors qu'un filtre de colonne équivalent est possible (comparaison simple) | `WARN` | Pattern remplaçable par un filtre booléen direct dans `CALCULATE`, plus performant. |
| `CALCULATE` imbriqué à l'intérieur d'un autre `CALCULATE` (hors imbrication au sein d'une mesure référencée) | `WARN` | Complexité de contexte de filtre difficile à raisonner et à optimiser. |
| Présence de `EARLIER` | `WARN` | Fonction historique, remplaçable par `VAR` dans la quasi-totalité des cas modernes, souvent source de confusion. |
| Itérateur (`SUMX`, `AVERAGEX`, `FILTER`, `MAXX`, `MINX`) appliqué directement à une table de faits volumineuse sans aucun filtre de réduction préalable dans les arguments de l'itérateur | `WARN` | Risque de balayage ligne à ligne coûteux sur un grand volume. |
| `CROSSFILTER` avec direction `BOTH` sur une relation dimension-fait | `WARN` | Propagation bidirectionnelle potentiellement coûteuse et ambiguë, à documenter comme choix assumé. |
| Combinaison de 3 patrons à risque ou plus dans une même mesure | `KO` | Cumul de complexité justifiant un passage prioritaire et obligatoire par un profilage DAX Studio avant mise en production. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Extraire le corps DAX de chaque mesure.

### Étape 2 — Rechercher chaque patron à risque
Pour chaque mesure, appliquer indépendamment chacune des détections de la section 4, sans s'arrêter à la première trouvée : une mesure peut cumuler plusieurs patrons.

### Étape 3 — Distinguer les faux positifs évidents
Écarter les appels à `FILTER` portant en réalité sur une table virtuelle déjà réduite (résultat de `VALUES`, `SUMMARIZE`, `ALLSELECTED` avec colonnes), qui ne posent pas le même risque qu'un `FILTER` sur la table physique complète.

### Étape 4 — Agréger les patrons détectés par mesure
Compter, par mesure, le nombre de patrons distincts détectés.

### Étape 5 — Terminer l'analyse
Parcourir la totalité des mesures avant de conclure. Produire la liste complète des mesures avec au moins un patron détecté, triée par nombre de patrns cumulés décroissant, pour prioriser le profilage DAX Studio.

---

## 6. Détection robuste / normalisation

- La détection de `FILTER` sur table entière doit distinguer `FILTER ( F_RESPONSES, ... )` (table physique, à risque) de `FILTER ( VALUES ( F_RESPONSES[WORRY_LEVEL] ), ... )` ou `FILTER ( SUMMARIZE(...), ... )` (table virtuelle déjà réduite en cardinalité, risque bien moindre).
- La détection de `CALCULATE` imbriqué doit ignorer les appels à `CALCULATE` qui apparaissent dans le corps d'une **autre mesure référencée** par `[NomMesure]` : seule l'imbrication directe et littérale dans la même expression compte.
- `EARLIER` doit être recherché comme mot-clé DAX complet (`\bEARLIER\b`), en évitant de confondre avec des noms de variables ou de colonnes contenant la sous-chaîne.
- Les commentaires DAX doivent être neutralisés avant la recherche de patrons, pour ne pas détecter un `FILTER` mentionné uniquement dans un commentaire.
- La liste des tables de faits volumineuses est déterminée par la convention de préfixe (`F_`) déjà utilisée dans les autres règles de ce corpus (cf. [BP-27](27_ModelDiagramLayout.md)), avec vérification croisée par la structure des relations si le préfixe n'est pas discriminant.

```python
FACT_TABLE_PREFIX = "F_"
ITERATOR_FUNCTIONS = {"SUMX", "AVERAGEX", "FILTER", "MAXX", "MINX", "COUNTX", "RANKX"}

def is_table_level_filter(filter_call, known_fact_tables):
    first_arg = filter_call.first_argument.strip()
    return first_arg in known_fact_tables  # table physique nue, pas VALUES(...)/SUMMARIZE(...)

def has_nested_calculate(dax_code):
    calls = find_function_calls(dax_code, "CALCULATE")
    return any(
        any(is_inside(inner.span, outer.span) for inner in calls if inner is not outer)
        for outer in calls
    )
```

---

## 7. Pseudo-code détaillé

```python
def analyze_dax_performance_patterns(table_files):
    findings = []

    fact_tables = {parse_tmdl_table(f).name for f in table_files
                    if parse_tmdl_table(f).name.startswith(FACT_TABLE_PREFIX)}

    for table_file in table_files:
        table = parse_tmdl_table(table_file)

        for measure in table.measures:
            dax = strip_dax_comments(measure.dax_expression)
            patterns_found = []

            for filter_call in find_function_calls(dax, "FILTER"):
                if is_table_level_filter(filter_call, fact_tables):
                    patterns_found.append("FILTER_ON_FULL_TABLE")

            if has_nested_calculate(dax):
                patterns_found.append("NESTED_CALCULATE")

            if re.search(r"\bEARLIER\s*\(", dax, re.IGNORECASE):
                patterns_found.append("EARLIER_USAGE")

            for iterator_call in find_function_calls_any(dax, ITERATOR_FUNCTIONS):
                if targets_full_fact_table(iterator_call, fact_tables) \
                        and not has_reducing_filter_argument(iterator_call):
                    patterns_found.append("ITERATOR_ON_FULL_FACT_TABLE")
                    break  # une occurrence suffit à qualifier la mesure

            if re.search(r"CROSSFILTER\s*\([^)]*,\s*BOTH\s*\)", dax, re.IGNORECASE):
                patterns_found.append("CROSSFILTER_BOTH")

            if patterns_found:
                status = "KO" if len(set(patterns_found)) >= 3 else "WARN"
                findings.append({
                    "table": table.name, "name": measure.name,
                    "patterns": sorted(set(patterns_found)), "status": status,
                })

    findings.sort(key=lambda f: len(f["patterns"]), reverse=True)
    return findings
```

---

## 8. Calcul du statut global

```python
if any(f["status"] == "KO" for f in findings):
    rule_status = "KO"
elif findings:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > OK`. Cette règle ne produit jamais `NA` : l'absence de mesure dans le modèle correspond simplement à l'absence de patron détecté, donc `OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Aucun patron à risque détecté sur l'ensemble des mesures | `OK` |
| Au moins une mesure cumule 3 patrons à risque ou plus | `KO` |
| Aucun cumul critique, mais au moins un patron isolé détecté | `WARN` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-31",
  "rule_name": "Détection des patrons DAX à risque de performance",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_measures_analyzed": 34,
  "findings": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-31",
  "rule_name": "Détection des patrons DAX à risque de performance",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_measures_analyzed": 34,
  "findings": [
    {
      "table": "MEASURE",
      "name": "Total_Worry_Weighted_Score",
      "patterns": ["FILTER_ON_FULL_TABLE", "ITERATOR_ON_FULL_FACT_TABLE", "NESTED_CALCULATE"],
      "status": "KO"
    },
    {
      "table": "MEASURE",
      "name": "Respondents_number",
      "patterns": ["CROSSFILTER_BOTH"],
      "status": "WARN"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-31 — Détection des patrons DAX à risque de performance : OK

34 mesures analysées, aucun patron connu à risque (FILTER sur table entière,
CALCULATE imbriqués, EARLIER, itérateur non réduit, CROSSFILTER BOTH) détecté.
```

### Exemple `KO`

```text
BP-31 — Détection des patrons DAX à risque de performance : KO

Mesure cumulant plusieurs patrons à risque :
- MEASURE[Total_Worry_Weighted_Score] : FILTER appliqué sur la table entière
  F_RESPONSES, itérateur SUMX sur la même table sans filtre réducteur, et
  CALCULATE imbriqué. Cumul de 3 patrons à risque.

Recommandation (non bloquante) :
- MEASURE[Respondents_number] utilise CROSSFILTER(..., BOTH), à documenter
  comme choix assumé si la propagation bidirectionnelle est nécessaire.

Correction attendue :
profiler MEASURE[Total_Worry_Weighted_Score] avec DAX Studio (Server Timings
et Query Plan) pour confirmer l'impact réel, puis remplacer le FILTER sur
table entière par un filtre de colonne direct dans CALCULATE et réduire le
contexte de l'itérateur SUMX avant son exécution.
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus et le corps DAX de chaque mesure a été extrait, quel que soit son format d'écriture ;
- chaque patron de la section 4 a été recherché indépendamment sur chaque mesure, sans s'arrêter à la première correspondance ;
- les faux positifs évidents (`FILTER` sur table virtuelle déjà réduite, `CALCULATE` imbriqué provenant en réalité d'une mesure référencée) ont été écartés avant de conclure ;
- les commentaires DAX ont été neutralisés avant la recherche de patrons ;
- aucune mesure n'a été omise de l'analyse ;
- le cumul de patrons par mesure a été calculé correctement avant d'appliquer le seuil de bascule en `KO`.

---

## 12. Résumé de la règle

```text
RÈGLE BP-31

POUR chaque table du modèle sémantique
    POUR chaque mesure
        EXTRAIRE le corps DAX, retirer les commentaires
        RECHERCHER FILTER sur table physique entière
        RECHERCHER CALCULATE imbriqué directement
        RECHERCHER EARLIER
        RECHERCHER itérateur sur table de faits sans filtre réducteur
        RECHERCHER CROSSFILTER(..., BOTH)

        SI 3 patrons distincts ou plus détectés
            mesure = KO
        SINON SI au moins 1 patron détecté
            mesure = WARN
        SINON
            mesure = OK (pas de finding)
        ENREGISTRER le résultat
    FIN POUR
FIN POUR

SI au moins une mesure KO -> règle = KO
SINON SI au moins une mesure WARN -> règle = WARN
SINON -> règle = OK

RECOMMANDER un profilage DAX Studio (Server Timings / Query Plan) pour
toutes les mesures WARN et KO, trié par nombre de patrons cumulés décroissant
```
