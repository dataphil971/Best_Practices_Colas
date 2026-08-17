# BP-33 — Utilisation de variables DAX (VAR/RETURN) dans les mesures complexes

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que les mesures DAX suffisamment complexes utilisent des variables (`VAR ... RETURN`) plutôt que de répéter la même sous-expression à plusieurs endroits ou d'imbriquer directement des appels de fonctions sans étape intermédiaire nommée. L'usage de `VAR` apporte trois bénéfices cumulés : la **lisibilité** (chaque variable porte un nom métier explicite, ce qui rend le calcul auto-documenté), la **maintenabilité** (une sous-expression modifiée n'a besoin d'être changée qu'à un seul endroit) et la **performance** (le moteur DAX évalue une variable une seule fois, même si elle est référencée plusieurs fois dans le `RETURN`, alors qu'une sous-expression répétée littéralement peut être réévaluée à chaque occurrence).

Cette règle définit un seuil de complexité (longueur de l'expression, profondeur d'imbrication de fonctions, répétition d'une même sous-expression) au-delà duquel l'absence de `VAR` devient une non-conformité. Une mesure triviale (`SUM(Table[Colonne])`) n'a évidemment pas besoin de variable ; une mesure combinant plusieurs `CALCULATE` avec des filtres complexes et des références répétées à une même sous-expression justifie pleinement l'introduction de variables.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre total de mesures ;
- de la table dans laquelle se trouve chaque mesure ;
- du format d'écriture en TMDL (ligne unique ou triple backticks).

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

Exemple de mesure **conforme**, utilisant `VAR`/`RETURN` pour nommer explicitement une étape intermédiaire, observée dans le modèle réel :

```tmdl
measure pct_RespondentsPerUsage = ```
        VAR TotalRespondents =
            CALCULATE ( [Respondents_number], REMOVEFILTERS ( F_ADOPTION_QUESTION[USAGE LABEL]) )
        RETURN
            DIVIDE ( [Respondents_number], TotalRespondents )
        ```
```

Exemple de mesure **complexe sans `VAR`** (cas hypothétique de répétition de sous-expression, à détecter comme non conforme) :

```dax
measure Score_Gap =
    DIVIDE(
        CALCULATE([Nb_Responses], F_RESPONSES[TESTED_KNOWLEDGE_LEVEL] = "High")
            - CALCULATE([Nb_Responses], F_RESPONSES[TESTED_KNOWLEDGE_LEVEL] = "Low"),
        CALCULATE([Nb_Responses], F_RESPONSES[TESTED_KNOWLEDGE_LEVEL] = "High")
            + CALCULATE([Nb_Responses], F_RESPONSES[TESTED_KNOWLEDGE_LEVEL] = "Low")
    )
```

Ici, `CALCULATE([Nb_Responses], F_RESPONSES[TESTED_KNOWLEDGE_LEVEL] = "High")` et sa variante `"Low"` sont chacune répétées deux fois littéralement : une simple réécriture avec `VAR HighCount = ...` et `VAR LowCount = ...` suivie d'un `RETURN DIVIDE(HighCount - LowCount, HighCount + LowCount)` éliminerait la duplication et rendrait l'intention (calcul d'un écart normalisé) immédiatement lisible.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Mesure simple (sous le seuil de complexité) sans `VAR` | `OK` | L'absence de variable est acceptable pour une expression triviale. |
| Mesure complexe (au-dessus du seuil) utilisant au moins un bloc `VAR ... RETURN` | `OK` | Bonne pratique respectée. |
| Mesure complexe sans aucun `VAR`, avec au moins une sous-expression répétée littéralement 2 fois ou plus | `KO` | Duplication évitable, lisibilité et performance dégradées. |
| Mesure complexe sans `VAR`, sans répétition détectée, mais avec un niveau d'imbrication de fonctions élevé (≥ 4 niveaux) | `WARN` | Pas de duplication stricte, mais la lisibilité bénéficierait d'une décomposition en étapes nommées. |
| Mesure dont le corps DAX n'a pas pu être extrait de façon fiable | `NA` | La complexité ne peut pas être évaluée. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Extraire le corps DAX de chaque mesure.

### Étape 2 — Calculer les métriques de complexité
Pour chaque mesure : longueur de l'expression normalisée (hors commentaires et espaces superflus) ; profondeur maximale d'imbrication des parenthèses de fonctions ; nombre de fonctions DAX distinctes appelées.

### Étape 3 — Détecter la présence de `VAR`
Rechercher le mot-clé `VAR` suivi d'un `RETURN` dans le corps de la mesure.

### Étape 4 — Détecter les sous-expressions répétées
Si aucun `VAR` n'est présent et que la mesure dépasse le seuil de complexité, rechercher des sous-expressions structurellement identiques (après normalisation) apparaissant au moins deux fois dans le corps de la mesure.

### Étape 5 — Classer chaque mesure
Appliquer la logique de la section 4. Ne pas s'arrêter à la première mesure non conforme : parcourir la totalité des mesures du modèle.

### Étape 6 — Terminer l'analyse
Produire la liste des mesures `KO` avec la sous-expression répétée identifiée, la liste des mesures `WARN`, et les métriques de complexité globales du modèle.

---

## 6. Détection robuste / normalisation

- Le seuil de complexité ne doit jamais être une valeur arbitraire unique appliquée aveuglément : il combine plusieurs signaux (longueur de l'expression normalisée > 120 caractères, OU profondeur d'imbrication ≥ 3, OU au moins 2 appels à `CALCULATE`/`FILTER`) — une mesure ne franchissant aucun de ces seuils est considérée comme simple et exemptée.
- La détection de répétition doit comparer des sous-expressions normalisées (espaces, casse) de longueur significative (> 20 caractères après normalisation) pour éviter de signaler des répétitions triviales comme `F_RESPONSES[CAMPAIGN_USER_LOGIN]` apparaissant plusieurs fois par nécessité syntaxique.
- Une mesure peut être écrite sur une seule ligne ou encadrée de triples backticks : la recherche de `VAR`/`RETURN` et le calcul de complexité ne dépendent pas du format de stockage TMDL.
- Le mot-clé `VAR` doit être recherché comme token DAX complet (`\bVAR\b`), en évitant de confondre avec un identifiant de colonne ou de variable contenant la sous-chaîne `var`.
- Les commentaires DAX doivent être neutralisés avant le calcul de longueur et la détection de répétition.

```python
def compute_complexity_score(dax_code):
    cleaned = strip_dax_comments(dax_code)
    normalized = re.sub(r"\s+", " ", cleaned).strip()
    depth = max_parenthesis_depth(normalized)
    calculate_filter_calls = len(re.findall(r"\b(CALCULATE|FILTER)\s*\(", normalized, re.IGNORECASE))
    return {
        "length": len(normalized),
        "max_depth": depth,
        "calculate_filter_calls": calculate_filter_calls,
    }

def is_complex_measure(metrics):
    return metrics["length"] > 120 or metrics["max_depth"] >= 3 or metrics["calculate_filter_calls"] >= 2

def has_var_return(dax_code):
    return bool(re.search(r"\bVAR\b", dax_code, re.IGNORECASE)) and \
           bool(re.search(r"\bRETURN\b", dax_code, re.IGNORECASE))

def find_repeated_subexpressions(dax_code, min_length=20):
    normalized = re.sub(r"\s+", " ", strip_dax_comments(dax_code)).strip().lower()
    candidates = extract_function_call_subexpressions(normalized)  # ex: calculate(...) complets
    repeated = [expr for expr in set(candidates)
                if len(expr) >= min_length and normalized.count(expr) >= 2]
    return repeated
```

---

## 7. Pseudo-code détaillé

```python
def analyze_dax_variable_usage(table_files):
    ok_items, ko_items, warn_items, na_items = [], [], [], []

    for table_file in table_files:
        table = parse_tmdl_table(table_file)

        for measure in table.measures:
            raw_dax = measure.raw_dax_expression
            if raw_dax is None:
                na_items.append({"table": table.name, "name": measure.name, "status": "NA",
                                  "reason": "Expression DAX non extraite"})
                continue

            metrics = compute_complexity_score(raw_dax)

            if not is_complex_measure(metrics):
                ok_items.append({"table": table.name, "name": measure.name, "status": "OK",
                                  "reason": "Mesure simple, VAR non requis"})
                continue

            if has_var_return(raw_dax):
                ok_items.append({"table": table.name, "name": measure.name, "status": "OK",
                                  "metrics": metrics})
                continue

            repeated = find_repeated_subexpressions(raw_dax)
            if repeated:
                ko_items.append({
                    "table": table.name, "name": measure.name, "status": "KO",
                    "metrics": metrics, "repeated_subexpressions": repeated,
                    "reason": "Sous-expression répétée sans VAR",
                })
            elif metrics["max_depth"] >= 4:
                warn_items.append({
                    "table": table.name, "name": measure.name, "status": "WARN",
                    "metrics": metrics,
                    "reason": "Imbrication profonde sans étape nommée (VAR recommandé)",
                })
            else:
                ko_items.append({
                    "table": table.name, "name": measure.name, "status": "KO",
                    "metrics": metrics,
                    "reason": "Mesure complexe sans VAR (seuil de complexité dépassé)",
                })

    return ok_items, ko_items, warn_items, na_items
```

---

## 8. Calcul du statut global

```python
if ko_items:
    rule_status = "KO"
elif warn_items:
    rule_status = "WARN"
elif na_items and not ok_items:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les mesures complexes utilisent VAR/RETURN | `OK` |
| Au moins une mesure complexe sans VAR (avec ou sans répétition détectée) | `KO` |
| Aucun `KO`, mais au moins une mesure profondément imbriquée sans VAR ni répétition stricte | `WARN` |
| Aucune mesure n'a pu être analysée | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-33",
  "rule_name": "Utilisation de variables DAX dans les mesures complexes",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_measures_analyzed": 34,
  "complex_measures": 21,
  "ko_details": [],
  "warn_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-33",
  "rule_name": "Utilisation de variables DAX dans les mesures complexes",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_measures_analyzed": 34,
  "complex_measures": 22,
  "ko_details": [
    {
      "table": "MEASURE",
      "name": "Score_Gap",
      "repeated_subexpressions": ["calculate([nb_responses], f_responses[tested_knowledge_level] = \"high\")"],
      "reason": "Sous-expression répétée sans VAR"
    }
  ],
  "warn_details": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-33 — Utilisation de variables DAX dans les mesures complexes : OK

34 mesures analysées, dont 21 jugées complexes. Toutes utilisent VAR/RETURN
pour nommer leurs étapes intermédiaires.
```

### Exemple `KO`

```text
BP-33 — Utilisation de variables DAX dans les mesures complexes : KO

Mesure complexe sans VAR détectée :
- MEASURE[Score_Gap] : l'expression
  CALCULATE([Nb_Responses], F_RESPONSES[TESTED_KNOWLEDGE_LEVEL] = "High")
  est répétée deux fois littéralement dans la formule.

Correction attendue :
réécrire Score_Gap avec VAR HighCount = CALCULATE([Nb_Responses],
F_RESPONSES[TESTED_KNOWLEDGE_LEVEL] = "High") et VAR LowCount = CALCULATE(
[Nb_Responses], F_RESPONSES[TESTED_KNOWLEDGE_LEVEL] = "Low"), puis RETURN
DIVIDE(HighCount - LowCount, HighCount + LowCount).
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus et le corps DAX de chaque mesure a été extrait ;
- les métriques de complexité (longueur, profondeur, nombre de CALCULATE/FILTER) ont été calculées pour chaque mesure avant de juger de la nécessité d'un VAR ;
- la détection de VAR/RETURN a couvert les deux formats d'écriture TMDL (ligne unique, triple backticks) ;
- la détection de répétition a porté sur des sous-expressions normalisées de longueur significative, pour éviter les faux positifs sur de simples références de colonnes ;
- aucune mesure complexe n'a été omise de l'analyse ;
- une mesure simple n'a jamais été signalée à tort pour absence de VAR.

---

## 12. Résumé de la règle

```text
RÈGLE BP-33

POUR chaque table du modèle sémantique
    POUR chaque mesure
        EXTRAIRE le corps DAX
        CALCULER longueur, profondeur d'imbrication, nb CALCULATE/FILTER

        SI mesure simple (sous tous les seuils)
            mesure = OK
        SINON SI VAR...RETURN présent
            mesure = OK
        SINON
            RECHERCHER sous-expressions répétées significatives
            SI répétition détectée OU seuil de complexité nettement dépassé
                mesure = KO
            SINON SI imbrication profonde (>= 4)
                mesure = WARN
            SINON
                mesure = KO
        ENREGISTRER le résultat
    FIN POUR
FIN POUR

SI au moins une mesure KO -> règle = KO
SINON SI au moins une mesure WARN -> règle = WARN
SINON -> règle = OK
```
