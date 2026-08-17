# BP-30 — Formatage standardisé du code DAX

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que le code DAX des mesures du modèle sémantique respecte des conventions de formatage communément admises dans l'écosystème Power BI (proches de celles produites par DAX Formatter / SQLBI) : une clause par ligne pour les fonctions structurantes (`CALCULATE`, `VAR`, `RETURN`, `SWITCH`, `FILTER`), une indentation cohérente et croissante avec la profondeur d'imbrication des parenthèses, des espaces homogènes autour des opérateurs, et l'absence de lignes excessivement longues regroupant plusieurs clauses logiques. Un code DAX mal formaté (tout sur une ligne, indentation incohérente, espaces erratiques) est fonctionnellement correct mais beaucoup plus difficile à relire, à faire évoluer et à revoir en pair-review, ce qui augmente le risque d'erreur lors des modifications futures.

Cette règle ne porte pas sur la correction fonctionnelle du calcul (qui est hors de portée d'une revue de formatage) mais uniquement sur la forme du code. Elle est complémentaire de [BP-33](33_DAXVariables.md) (usage de variables) et de [BP-35](35_CommentsInCode.md) (commentaires) : un code bien formaté, avec des variables et des commentaires pertinents, constitue ensemble une mesure DAX de qualité professionnelle.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre total de mesures ;
- de la complexité de chaque mesure ;
- du format d'écriture en TMDL (ligne unique ou triple backticks) — une mesure simple tenant naturellement sur une ligne n'est pas pénalisée pour autant.

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

Exemple de mesure **correctement formatée**, observée dans le modèle réel (une clause par ligne, indentation croissante avec la profondeur) :

```tmdl
measure pct_Worry_Level_On_ALL = ```
        VAR Total_Nb_Responses =
            CALCULATE(
                [Nb_Responses],
                ALL(
                    F_RESPONSES[WORRY_LEVEL],
                    F_RESPONSES[WORRY_LEGEND]
                )
            )
        RETURN
            DIVIDE(
                [Nb_Responses],
                Total_Nb_Responses
            )
        ```
```

Exemple de mesure **mal formatée** (tout sur une seule ligne dense), également rencontrée dans le modèle réel :

```tmdl
measure pct_Usage_Level_On_ALL =
        VAR Nb_Responses_Usage = CALCULATE([Nb_Responses], ALL(F_RESPONSES[USAGE_LEVEL], F_RESPONSES[USAGE_LEGEND_ORDER]))
        RETURN DIVIDE([Nb_Responses], Nb_Responses_Usage)
```

Ici, l'appel `CALCULATE(...)` avec son filtre `ALL(...)` imbriqué est compressé sur une seule ligne de plus de 100 caractères, alors que la mesure structurellement identique `pct_Worry_Level_On_ALL` répartit les mêmes clauses sur plusieurs lignes.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Mesure simple (une seule fonction, pas d'imbrication) tenant sur une ligne courte (< 80 caractères) | `OK` | Le format ligne unique est légitime pour une expression triviale. |
| Mesure complexe (≥ 2 niveaux d'imbrication de fonctions, ou présence de `VAR`/`RETURN`) avec une clause structurante par ligne et indentation croissante avec la profondeur | `OK` | Formatage conforme aux standards DAX Formatter. |
| Mesure complexe dont plusieurs clauses structurantes (`CALCULATE`, `FILTER`, `ALL`, virgules d'arguments) sont regroupées sur une même ligne dépassant la longueur raisonnable | `KO` | Lisibilité dégradée, code difficile à faire évoluer. |
| Mesure complexe avec indentation incohérente (les lignes de même profondeur de parenthèses n'ont pas la même indentation) | `KO` | Structure visuelle trompeuse par rapport à la structure logique réelle. |
| Mesure avec espacement erratique autour des opérateurs (`a=b` au lieu de `a = b`, virgules sans espace après) | `WARN` | Détail de style non bloquant mais recommandé. |
| Mesure dont le corps DAX n'a pas pu être extrait de façon fiable (erreur de parsing TMDL) | `NA` | Le formatage ne peut pas être évalué. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Extraire toutes les mesures avec leur corps DAX brut, en conservant les sauts de ligne et l'indentation d'origine.

### Étape 2 — Évaluer la complexité de chaque mesure
Compter le nombre de fonctions imbriquées, la présence de blocs `VAR`/`RETURN`, la longueur totale de l'expression. Une mesure sans imbrication et courte est exemptée de l'exigence « une clause par ligne ».

### Étape 3 — Vérifier la répartition en lignes
Pour chaque mesure complexe : mesurer la longueur de chaque ligne du corps DAX ; détecter les lignes contenant plusieurs clauses structurantes séparées par une virgule de haut niveau ou plusieurs mots-clés (`CALCULATE(`, `FILTER(`, `VAR`, `RETURN`) sur la même ligne.

### Étape 4 — Vérifier la cohérence de l'indentation
Calculer, pour chaque ligne, la profondeur de parenthésage à son début (nombre de parenthèses ouvertes non fermées avant cette ligne) et comparer l'indentation effective (nombre d'espaces en tête de ligne) à celle des autres lignes de même profondeur dans la même mesure.

### Étape 5 — Vérifier l'espacement
Contrôler la présence d'espaces autour des opérateurs de comparaison et d'affectation (`=`, `<`, `>`, `<=`, `>=`, `<>`) et après les virgules d'arguments.

### Étape 6 — Terminer l'analyse
Parcourir la totalité des mesures avant de conclure. Produire la liste des mesures `KO` avec le détail de l'anomalie de formatage, et la liste des mesures `WARN` pour les problèmes de style mineurs.

---

## 6. Détection robuste / normalisation

- Une mesure écrite sur une seule ligne en TMDL n'est pas automatiquement non conforme : le critère est la complexité de l'expression, pas le format de stockage TMDL (ligne unique vs triple backticks). Une expression simple comme `COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN])` reste conforme même sur une ligne.
- Le calcul de la profondeur de parenthésage doit ignorer les parenthèses et virgules situées à l'intérieur de chaînes de caractères littérales (`"texte, avec virgule"`), pour ne pas fausser la détection de clauses multiples sur une même ligne.
- Les commentaires (`--`, `//`, `/* */`) doivent être neutralisés avant l'analyse de longueur de ligne et de comptage de clauses, mais leur présence ne doit pas être confondue avec un défaut de formatage.
- L'indentation attendue n'est pas comparée à une valeur absolue fixe (2 espaces, 4 espaces...) mais à la cohérence interne de la mesure : toutes les lignes de même profondeur de parenthésage doivent partager la même indentation au sein d'une même mesure.
- Les noms de colonnes entre crochets (`F_RESPONSES[WORRY_LEVEL]`) contiennent parfois des espaces internes qui ne doivent pas être confondus avec des espaces de séparation de clauses.

```python
def strip_dax_comments_and_strings(dax_code):
    code = re.sub(r'"[^"]*"', '""', dax_code)          # neutralise le contenu des chaînes
    code = re.sub(r"--.*", "", code)
    code = re.sub(r"//.*", "", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return code

def parenthesis_depth_at_line_start(lines, line_index):
    text_before = "\n".join(lines[:line_index])
    return text_before.count("(") - text_before.count(")")

def count_top_level_clauses_on_line(line):
    """Compte les occurrences de mots-clés structurants et de virgules d'arguments hors chaînes."""
    keywords = len(re.findall(r"\b(CALCULATE|FILTER|VAR|RETURN|SWITCH)\b", line, re.IGNORECASE))
    commas = line.count(",")
    return keywords + (1 if commas > 0 else 0)
```

---

## 7. Pseudo-code détaillé

```python
def is_simple_measure(dax_code):
    depth = max_parenthesis_depth(dax_code)
    has_var = bool(re.search(r"\bVAR\b", dax_code, re.IGNORECASE))
    return depth <= 1 and not has_var and len(dax_code.strip()) < 80


def analyze_dax_formatting(table_files):
    ok_items, ko_items, warn_items, na_items = [], [], [], []

    for table_file in table_files:
        table = parse_tmdl_table(table_file)

        for measure in table.measures:
            raw_dax = measure.raw_dax_expression
            if raw_dax is None:
                na_items.append({"table": table.name, "name": measure.name, "status": "NA",
                                  "reason": "Expression DAX non extraite"})
                continue

            cleaned = strip_dax_comments_and_strings(raw_dax)

            if is_simple_measure(cleaned):
                ok_items.append({"table": table.name, "name": measure.name, "status": "OK",
                                  "reason": "Mesure simple, format ligne unique acceptable"})
                continue

            lines = cleaned.split("\n")
            dense_lines = [
                i for i, line in enumerate(lines)
                if len(line.strip()) > 100 and count_top_level_clauses_on_line(line) >= 2
            ]

            depth_indentation = {}
            inconsistent_indentation = False
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                depth = parenthesis_depth_at_line_start(lines, i)
                indent = len(line) - len(line.lstrip(" "))
                if depth in depth_indentation and depth_indentation[depth] != indent:
                    inconsistent_indentation = True
                depth_indentation.setdefault(depth, indent)

            spacing_issues = detect_spacing_issues(cleaned)

            if dense_lines or inconsistent_indentation:
                ko_items.append({
                    "table": table.name, "name": measure.name, "status": "KO",
                    "dense_lines": dense_lines,
                    "inconsistent_indentation": inconsistent_indentation,
                })
            elif spacing_issues:
                warn_items.append({
                    "table": table.name, "name": measure.name, "status": "WARN",
                    "spacing_issues": spacing_issues,
                })
            else:
                ok_items.append({"table": table.name, "name": measure.name, "status": "OK"})

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

Priorité des statuts : `KO > WARN > OK`, avec `NA` réservé au cas où aucune mesure n'a pu être analysée du tout.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les mesures complexes respectent la répartition en lignes et l'indentation cohérente | `OK` |
| Au moins une mesure complexe regroupe plusieurs clauses sur une ligne dense ou présente une indentation incohérente | `KO` |
| Aucun `KO`, mais des problèmes d'espacement mineurs détectés | `WARN` |
| Aucune mesure n'a pu être analysée (erreur de parsing généralisée) | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-30",
  "rule_name": "Formatage standardisé du code DAX",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_measures_analyzed": 34,
  "ko_details": [],
  "warn_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-30",
  "rule_name": "Formatage standardisé du code DAX",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_measures_analyzed": 34,
  "ko_details": [
    {
      "table": "MEASURE",
      "name": "pct_Usage_Level_On_ALL",
      "dense_lines": [1],
      "inconsistent_indentation": false,
      "reason": "CALCULATE et ALL imbriqués regroupés sur une seule ligne de plus de 100 caractères"
    }
  ],
  "warn_details": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-30 — Formatage standardisé du code DAX : OK

34 mesures analysées. Les mesures complexes (avec VAR/RETURN ou imbrication
de fonctions) respectent une clause structurante par ligne et une indentation
cohérente avec la profondeur d'imbrication. Les mesures simples tenant
naturellement sur une ligne ne sont pas pénalisées.
```

### Exemple `KO`

```text
BP-30 — Formatage standardisé du code DAX : KO

Mesure mal formatée détectée :
- MEASURE[pct_Usage_Level_On_ALL] : la clause CALCULATE([Nb_Responses],
  ALL(F_RESPONSES[USAGE_LEVEL], F_RESPONSES[USAGE_LEGEND_ORDER])) est
  compressée sur une seule ligne de plus de 100 caractères, alors que la
  mesure structurellement identique pct_Worry_Level_On_ALL répartit les
  mêmes clauses sur plusieurs lignes indentées.

Correction attendue :
reformater pct_Usage_Level_On_ALL en répartissant CALCULATE, ALL et leurs
arguments sur des lignes séparées avec une indentation croissante, à
l'identique du style déjà appliqué sur pct_Worry_Level_On_ALL et
pct_Interest_Level_On_ALL (idéalement en passant le code dans DAX Formatter).
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus et l'expression DAX brute de chaque mesure a été extraite avec ses sauts de ligne et son indentation d'origine ;
- la complexité de chaque mesure a été évaluée avant de juger de la nécessité d'un formatage multi-lignes ;
- les commentaires et le contenu des chaînes de caractères ont été neutralisés avant l'analyse de longueur de ligne et de comptage de clauses ;
- la cohérence d'indentation a été vérifiée en comparant les lignes de même profondeur de parenthésage au sein de chaque mesure, pas contre une valeur absolue arbitraire ;
- aucune mesure complexe n'a été omise de l'analyse ;
- une mesure simple correctement écrite sur une seule ligne n'a jamais été comptée à tort comme non conforme.

---

## 12. Résumé de la règle

```text
RÈGLE BP-30

POUR chaque table du modèle sémantique
    POUR chaque mesure
        EXTRAIRE le corps DAX brut (avec indentation d'origine)
        NEUTRALISER commentaires et chaînes de caractères

        SI mesure simple (peu de profondeur, pas de VAR, courte)
            mesure = OK
        SINON
            VÉRIFIER l'absence de lignes denses (plusieurs clauses sur une ligne)
            VÉRIFIER la cohérence de l'indentation par profondeur de parenthésage
            VÉRIFIER l'espacement autour des opérateurs et virgules

            SI ligne dense OU indentation incohérente
                mesure = KO
            SINON SI problème d'espacement mineur
                mesure = WARN
            SINON
                mesure = OK
        ENREGISTRER le résultat
    FIN POUR
FIN POUR

SI au moins une mesure KO -> règle = KO
SINON SI au moins une mesure WARN -> règle = WARN
SINON -> règle = OK
```
