# BP-35 — Commentaires utiles dans le code complexe (DAX et Power Query M)

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que le code DAX des mesures et le code Power Query M des requêtes du modèle sémantique comportent des commentaires (`--` ou `//` en DAX, `//` ou `/* ... */` en M) qui expliquent la logique **non triviale** du calcul ou de la transformation, sans pour autant sur-commenter des étapes évidentes qui n'apportent aucune information supplémentaire par rapport au code lui-même. Un commentaire pertinent explique le **pourquoi** (intention métier, contournement d'un cas particulier, hypothèse de calcul) plutôt que de paraphraser le **quoi** (ce que le code fait déjà de façon lisible). L'absence totale de commentaire sur un calcul complexe oblige le lecteur à reconstruire mentalement l'intention ; à l'inverse, un commentaire sur chaque ligne triviale (`-- somme` au-dessus de `SUM(...)`) dilue l'attention et n'aide personne.

Cette règle mesure donc un **ratio commentaires / complexité**, pas un simple ratio commentaires / lignes de code : une mesure courte et triviale peut légitimement n'avoir aucun commentaire, tandis qu'une mesure longue avec plusieurs branches conditionnelles ou plusieurs `VAR` imbriqués doit comporter au moins un commentaire expliquant l'intention générale ou les points de complexité identifiés (cf. [BP-31](31_DAXPerformance.md) pour les patrons à risque, [BP-33](33_DAXVariables.md) pour l'usage de `VAR`).

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre total de mesures et de requêtes M ;
- du langage concerné (DAX ou Power Query M) ;
- du format d'écriture en TMDL (ligne unique ou triple backticks).

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl          (mesures DAX, dans les blocs measure)
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl           (code M des partitions, dans les blocs partition ... = m)
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl        (code M des requêtes partagées)
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\expressions.tmdl
```

---

## 3. Élément(s) / propriété(s) à contrôler

Exemple de mesure **avec commentaire utile**, expliquant une intention non déductible du code seul, observé dans le modèle réel :

```tmdl
measure pct_RespondentsPerUsage = ```
        VAR TotalRespondents =
            CALCULATE ( [Respondents_number], REMOVEFILTERS ( F_ADOPTION_QUESTION[USAGE LABEL]) )-- to have the totality  of respondents
        RETURN
            DIVIDE ( [Respondents_number], TotalRespondents )
        ```
```

Le commentaire `-- to have the totality of respondents` explique pourquoi `REMOVEFILTERS` est utilisé à cet endroit précis (lever tous les filtres actifs sur `USAGE LABEL` pour obtenir un dénominateur global), ce qui n'est pas évident à la seule lecture de l'appel de fonction.

Autre exemple de commentaire utile expliquant le rôle d'une jointure de contexte, également réel :

```tmdl
measure Respondents_number = ```
        CALCULATE (
            DISTINCTCOUNT ( F_ADOPTION_QUESTION[CAMPAIGN_USER_LOGIN] ),
            CROSSFILTER ( D_USERS[CAMPAIGN_USER_LOGIN], F_RESPONSES[CAMPAIGN_USER_LOGIN], BOTH )// To count only users who answered the survey.
        )
        ```
```

Exemple de mesure **complexe sans aucun commentaire** (cas à détecter), observé tel quel dans le modèle réel :

```tmdl
measure pct_Usage_Level_On_ALL =
        VAR Nb_Responses_Usage =
            CALCULATE(
                [Nb_Responses],
                ALL(
                    F_RESPONSES[USAGE_LEVEL],
                    F_RESPONSES[USAGE_LEGEND_ORDER]
                )
            )
        RETURN
            DIVIDE(
                [Nb_Responses],
                Nb_Responses_Usage
            )
```

Cette mesure suit exactement le même patron que `pct_RespondentsPerUsage`, mais sans le commentaire équivalent expliquant pourquoi `ALL` porte sur ces deux colonnes précises — incohérence de documentation au sein d'une même famille de mesures (cf. [BP-34](34_CalculationGroups.md)).

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Code simple (sous le seuil de complexité) sans commentaire | `OK` | Un code trivial n'a pas besoin d'être commenté. |
| Code complexe (au-dessus du seuil) avec au moins un commentaire non trivial | `OK` | Ratio commentaires/complexité jugé suffisant. |
| Code complexe sans aucun commentaire | `KO` | La logique non triviale n'est pas expliquée. |
| Code (simple ou complexe) truffé de commentaires triviaux redondants avec le code (ex. `-- somme` au-dessus de `SUM(...)`, un commentaire par ligne sans information ajoutée) | `WARN` | Sur-commentation qui dilue l'attention sans réel gain de lisibilité. |
| Code dont l'expression n'a pas pu être extraite de façon fiable | `NA` | Le ratio commentaires/complexité ne peut pas être évalué. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl` (mesures DAX et code M des partitions).
2. Charger `expressions.tmdl` s'il existe (code M des requêtes partagées).

### Étape 2 — Calculer la complexité de chaque élément
Pour chaque mesure DAX : utiliser les mêmes métriques que [BP-33](33_DAXVariables.md) (longueur, profondeur d'imbrication, nombre de `CALCULATE`/`FILTER`, présence de `VAR`, présence de branches conditionnelles `IF`/`SWITCH`). Pour chaque requête M : nombre d'étapes, présence d'étapes de type jointure/pivot/filtre complexe (cf. [BP-04](04_PushTransformUpstream.md) pour la classification des fonctions M lourdes).

### Étape 3 — Extraire et qualifier les commentaires
Pour chaque élément : extraire tous les commentaires (`--`, `//`, `/* ... */`) présents dans le corps du code ; pour chacun, évaluer s'il est trivial (reformulation directe du nom de la fonction/variable adjacente, longueur très courte, mots génériques comme « calcul », « total », « ici ») ou non trivial (explique une intention, un cas particulier, une hypothèse métier).

### Étape 4 — Calculer le ratio commentaires utiles / complexité
Rapprocher le nombre de commentaires non triviaux du niveau de complexité mesuré à l'étape 2.

### Étape 5 — Classer chaque élément
Appliquer la logique de la section 4. Ne pas s'arrêter au premier élément non conforme : parcourir la totalité des mesures et des requêtes M.

### Étape 6 — Terminer l'analyse
Produire la liste des éléments `KO` (complexes et non commentés), la liste des éléments `WARN` (sur-commentés), et les métriques globales.

---

## 6. Détection robuste / normalisation

- Le seuil de complexité DAX est identique à celui défini dans [BP-33](33_DAXVariables.md) pour garantir la cohérence entre les deux règles : longueur normalisée > 120 caractères, OU profondeur d'imbrication ≥ 3, OU au moins 2 appels `CALCULATE`/`FILTER`, OU présence d'au moins une branche `IF`/`SWITCH`.
- Le seuil de complexité M reprend la classification des fonctions « lourdes » de [BP-04](04_PushTransformUpstream.md) : une requête contenant au moins une étape lourde (jointure, pivot, agrégation) est considérée comme complexe pour cette règle.
- Un commentaire DAX de fin de ligne (`-- texte` ou `// texte`) doit être capturé même lorsqu'il suit immédiatement une expression sans espace (`REMOVEFILTERS(...)-- to have...`), en s'assurant de ne pas capturer par erreur un `--` ou `//` apparaissant à l'intérieur d'une chaîne de caractères littérale.
- Les commentaires de bloc (`/* ... */`) en DAX doivent être neutralisés séparément des commentaires de fin de ligne pour éviter les doubles comptages.
- La détection de trivialité d'un commentaire doit comparer le contenu normalisé du commentaire (minuscule, sans ponctuation) à une liste de formulations génériques (`total`, `somme`, `calcul`, `résultat`, `here`, `sum`, `total`) ET vérifier que le commentaire ne fait qu'un mot ou deux, sans expliquer de condition ni de justification métier.
- En Power Query M, les commentaires `//` de fin de ligne et les blocs `/* ... */` doivent être extraits en tenant compte du fait qu'une étape peut être nommée avec des espaces (`#"Nom avec espaces"`), ce qui ne doit jamais être confondu avec un commentaire.

```python
TRIVIAL_COMMENT_TOKENS = {"total", "somme", "sum", "calcul", "resultat", "résultat", "here", "ici", "ok"}

def is_trivial_comment(comment_text):
    normalized = re.sub(r"[^\w\s]", "", comment_text).strip().lower()
    words = normalized.split()
    return len(words) <= 2 and all(w in TRIVIAL_COMMENT_TOKENS for w in words)

def extract_dax_comments(dax_code):
    line_comments = re.findall(r"(?:--|//)\s*(.+)", dax_code)
    block_comments = re.findall(r"/\*(.*?)\*/", dax_code, re.DOTALL)
    return line_comments + block_comments
```

---

## 7. Pseudo-code détaillé

```python
def analyze_code_comments(table_files, expressions_file):
    ok_items, ko_items, warn_items, na_items = [], [], [], []

    for table_file in table_files:
        table = parse_tmdl_table(table_file)

        for measure in table.measures:
            raw_dax = measure.raw_dax_expression
            if raw_dax is None:
                na_items.append({"element": f"{table.name}[{measure.name}]", "kind": "measure", "status": "NA"})
                continue

            metrics = compute_complexity_score(raw_dax)  # réutilise BP-33
            has_conditional = bool(re.search(r"\b(IF|SWITCH)\s*\(", raw_dax, re.IGNORECASE))
            is_complex = is_complex_measure(metrics) or has_conditional

            comments = extract_dax_comments(strip_string_literals(raw_dax))
            non_trivial_comments = [c for c in comments if not is_trivial_comment(c)]
            trivial_comment_ratio = (len(comments) - len(non_trivial_comments)) / len(comments) if comments else 0

            element_id = {"table": table.name, "name": measure.name, "kind": "measure"}

            if is_complex and not non_trivial_comments:
                ko_items.append({**element_id, "status": "KO",
                                  "reason": "Code complexe sans commentaire explicatif"})
            elif trivial_comment_ratio > 0.7 and len(comments) >= 3:
                warn_items.append({**element_id, "status": "WARN",
                                    "reason": "Sur-commentation : commentaires majoritairement triviaux"})
            else:
                ok_items.append({**element_id, "status": "OK"})

        if table.has_m_partition():
            m_code = table.partition.source_expression
            steps = parse_steps(m_code)
            heavy_steps = [s for s in steps if classify_step(s) == "HEAVY"]  # réutilise BP-04
            comments = extract_m_comments(m_code)
            non_trivial_comments = [c for c in comments if not is_trivial_comment(c)]

            element_id = {"table": table.name, "name": "partition", "kind": "m_query"}
            if heavy_steps and not non_trivial_comments:
                ko_items.append({**element_id, "status": "KO",
                                  "reason": "Requête M avec étapes lourdes non commentées"})
            else:
                ok_items.append({**element_id, "status": "OK"})

    if expressions_file_exists(expressions_file):
        for expr in parse_tmdl_expressions(expressions_file):
            if expr.is_data_query():
                steps = parse_steps(expr.body)
                heavy_steps = [s for s in steps if classify_step(s) == "HEAVY"]
                comments = extract_m_comments(expr.body)
                non_trivial_comments = [c for c in comments if not is_trivial_comment(c)]

                element_id = {"table": "expressions.tmdl", "name": expr.name, "kind": "m_query"}
                if heavy_steps and not non_trivial_comments:
                    ko_items.append({**element_id, "status": "KO",
                                      "reason": "Requête M partagée avec étapes lourdes non commentées"})
                else:
                    ok_items.append({**element_id, "status": "OK"})

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
| Tout le code complexe (DAX et M) comporte au moins un commentaire non trivial | `OK` |
| Au moins un élément complexe (mesure ou requête M) sans aucun commentaire explicatif | `KO` |
| Aucun `KO`, mais au moins un élément sur-commenté (commentaires majoritairement triviaux) | `WARN` |
| Aucun élément n'a pu être analysé | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-35",
  "rule_name": "Commentaires utiles dans le code complexe (DAX et M)",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_elements_analyzed": 58,
  "complex_elements": 24,
  "ko_details": [],
  "warn_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-35",
  "rule_name": "Commentaires utiles dans le code complexe (DAX et M)",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_elements_analyzed": 58,
  "complex_elements": 24,
  "ko_details": [
    {
      "table": "MEASURE",
      "name": "pct_Usage_Level_On_ALL",
      "kind": "measure",
      "reason": "Code complexe sans commentaire explicatif"
    }
  ],
  "warn_details": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-35 — Commentaires utiles dans le code complexe (DAX et M) : OK

58 éléments analysés (mesures DAX et requêtes M), dont 24 jugés complexes.
Tous comportent au moins un commentaire non trivial expliquant l'intention
du calcul ou de la transformation.
```

### Exemple `KO`

```text
BP-35 — Commentaires utiles dans le code complexe (DAX et M) : KO

Mesure complexe non commentée détectée :
- MEASURE[pct_Usage_Level_On_ALL] : le patron CALCULATE([Nb_Responses],
  ALL(F_RESPONSES[USAGE_LEVEL], F_RESPONSES[USAGE_LEGEND_ORDER])) n'est pas
  commenté, alors que la mesure structurellement identique
  pct_RespondentsPerUsage explique, elle, pourquoi le filtre est levé
  ("to have the totality of respondents").

Correction attendue :
ajouter un commentaire en fin de ligne sur la clause ALL de
pct_Usage_Level_On_ALL, expliquant pourquoi ces deux colonnes précises sont
levées du contexte de filtre (ex. : "-- to retrieve the total across all
usage levels"), en cohérence avec les autres mesures de la même famille.
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` et `expressions.tmdl` (s'il existe) ont été lus ;
- la complexité de chaque mesure DAX et de chaque requête M a été calculée avant de juger de la nécessité d'un commentaire ;
- les commentaires ont été extraits en tenant compte des deux syntaxes DAX (`--`, `//`, `/* */`) et des deux syntaxes M (`//`, `/* */`), sans confondre un commentaire avec du contenu situé à l'intérieur d'une chaîne littérale ou d'un nom d'étape entre guillemets ;
- la trivialité de chaque commentaire a été évaluée avant de le compter comme « utile » ;
- aucun élément complexe n'a été omis de l'analyse, que ce soit une mesure DAX ou une requête M ;
- le seuil de complexité utilisé est resté cohérent avec celui de BP-33 (DAX) et de BP-04 (M).

---

## 12. Résumé de la règle

```text
RÈGLE BP-35

POUR chaque mesure DAX du modèle
    CALCULER la complexité (longueur, profondeur, CALCULATE/FILTER, IF/SWITCH)
    EXTRAIRE les commentaires (--, //, /* */)
    FILTRER les commentaires non triviaux

    SI complexe ET aucun commentaire non trivial
        mesure = KO
    SINON SI commentaires majoritairement triviaux et nombreux
        mesure = WARN
    SINON
        mesure = OK
FIN POUR

POUR chaque requête M (tables + expressions partagées)
    CLASSER les étapes (HEAVY / LIGHT, cf. BP-04)
    EXTRAIRE les commentaires M
    SI étapes HEAVY présentes ET aucun commentaire non trivial
        requête = KO
    SINON
        requête = OK
FIN POUR

SI au moins un élément KO -> règle = KO
SINON SI au moins un élément WARN -> règle = WARN
SINON -> règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-35 — Commentaires utiles dans le code complexe         │
│         (DAX et Power Query M)                                    │
└────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
     ┌─────────────────────────────────────────────────┐
     │ Localiser tables\*.tmdl (mesures + partitions M)  │
     │ et expressions.tmdl (requêtes M partagées)        │
     └──────────────┬──────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ╔═════════════╗       ┌───────────────┐
   ║ Fichiers ✅ ║       │ Introuvable ❌ │
   ╚══════╤══════╝       └───────┬────────┘
          │                      ▼
          │              ┌───────────────┐
          │              │ Élément = NA  │
          │              └───────────────┘
          ▼
 ┌────────────────────────────────────────┐
 │ POUR chaque mesure DAX                  │
 │  CALCULER complexité (longueur,         │
 │  profondeur, CALCULATE/FILTER, IF/SWITCH)│
 │  EXTRAIRE commentaires (--, //, /* */)   │
 │  FILTRER commentaires triviaux           │
 └──────────────┬───────────────────────────┘
                ▼
       ┌────────┴─────────┐
       ▼                   ▼
╔═════════════════╗  ┌─────────────────────────┐
║ Complexe ET      ║  │ Non complexe             │
║ 0 commentaire    ║  │ OU commentaire présent   │
║ non trivial      ║  └──────────┬────────────────┘
╚════════╤═════════╝             │
         ▼                        ▼
   ┌─────────────┐        ┌───────────────────────────┐
   │ Mesure = KO │        │ Ratio triviaux > 0.7        │
   └─────────────┘        │ ET >= 3 commentaires ?       │
                           └──────────┬────────────────────┘
                              ┌────────┴────────┐
                              ▼                 ▼
                       ╔═════════════╗   ┌─────────────┐
                       ║ OUI -> WARN ║   │ NON -> OK    │
                       ╚═════════════╝   └─────────────┘
                                          (mesure conforme)
                ▼
 ┌────────────────────────────────────────┐
 │ POUR chaque requête M (partitions +     │
 │ expressions.tmdl)                       │
 │  CLASSER les étapes (HEAVY / LIGHT)     │
 │  EXTRAIRE commentaires M (//, /* */)    │
 └──────────────┬───────────────────────────┘
                ▼
       ┌────────┴─────────┐
       ▼                   ▼
╔═════════════════╗  ┌───────────────┐
║ Étapes HEAVY ET  ║  │ Pas de HEAVY   │
║ 0 commentaire    ║  │ non commenté   │
╚════════╤═════════╝  └───────┬────────┘
         ▼                    ▼
   ┌─────────────┐      ┌─────────────┐
   │ Requête = KO│      │ Requête = OK │
   └─────────────┘      └─────────────┘
                ▼
     ┌──────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL              │
     │ Priorité : KO > WARN > NA > OK        │
     └──────────────┬─────────────────────────┘
                     │
       ┌─────────────┼─────────────────┐
       ▼              ▼                 ▼
╔═════════════╗ ┌─────────────┐  ┌──────────────────┐
║ 1+ KO -> KO ║ │ 0 KO, 1+    │  │ 0 KO, 0 WARN,     │
║             ║ │ WARN -> WARN│  │ rien d'analysable │
╚═════════════╝ └─────────────┘  │ -> NA             │
                                  └──────────────────┘
                                        │
       └─────────────┬────────────────┘
                      ▼
        RETOUR rule_status (OK / KO / WARN / NA)
```
