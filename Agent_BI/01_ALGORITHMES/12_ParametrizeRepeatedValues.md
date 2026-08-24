# BP-12 — Paramétrer les valeurs littérales répétées dans Power Query

## 1. Objectif

Détecter les valeurs de configuration répétées dans plusieurs requêtes M et vérifier qu'elles sont centralisées dans un paramètre lorsque la politique du projet l'exige.

Exemples de valeurs typiquement paramétrables :

```text
URL de site
hostname
HTTP path
catalogue
workspace
chemin de fichier
nom d'environnement
```

Le checker ne doit pas décider qu'un littéral doit être paramétré uniquement parce qu'il :

```text
fait plus de 8 caractères
apparaît 3 fois
ressemble à une URL
```

Statuts :

```text
OK / KO / NA
```

`WARN` n'est jamais un statut de règle.

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Contexte :

```text
m_ast
m_literal_index
parameter_index
company_policy
connector_signature_index
```

---

## 3. Extraction par parser M

Le code M doit être tokenisé / parsé.

Le checker ne doit pas utiliser une regex comme preuve décisionnelle :

```python
r'(?<!#)"..."'
```

car les chaînes peuvent apparaître dans :

- identifiants quotés ;
- métadonnées ;
- arguments de fonctions ;
- structures de données ;
- expressions imbriquées.

Le parser fournit :

```text
literal_value
query
AST location
parent function
argument position
semantic context
```

---

## 4. Comptage

Le moteur distingue :

```text
occurrence_count
distinct_query_count
```

La policy doit préciser la métrique utilisée.

Exemple :

```yaml
bp_12:
  repetition_metric: DISTINCT_QUERY_COUNT
  repetition_threshold: 3
```

Le seuil n'est jamais hardcodé dans le checker.

---

## 5. Classification du littéral

Valeurs :

```text
PARAMETERIZABLE_CONFIRMED
NON_PARAMETERIZABLE
UNKNOWN
```

### `PARAMETERIZABLE_CONFIRMED`

Preuve possible :

- position de connecteur configurée comme variable d'environnement ;
- policy ciblant certaines valeurs/arguments ;
- contrat de source ;
- annotation de gouvernance.

### `NON_PARAMETERIZABLE`

Exemple :

- enum du connecteur explicitement exclue par policy ;
- valeur fonctionnelle devant rester locale.

### `UNKNOWN`

Aucune preuve suffisante.

Une URL n'est qu'un **candidat** tant que la policy n'établit pas que les endpoints doivent être paramétrés.

---

## 6. Policy de contexte

Exemple :

```yaml
bp_12:
  repetition_threshold: 3

  parameterizable_contexts:
    - function: SharePoint.Tables
      argument: 0

    - function: Databricks.Catalogs
      argument: 0

    - function: Databricks.Catalogs
      argument: 1

  excluded_contexts:
    - function: SharePoint.Tables
      option: Implementation
```

Le checker devient ainsi générique sans coder :

```text
Implementation="2.0"
```

en dur.

---

## 7. Paramètres Power Query existants

Un paramètre est identifié structurellement à partir de ses métadonnées, par exemple :

```text
IsParameterQuery = true
```

Le resolver conserve :

```text
parameter_name
current_expression
DefaultValue
Type
List
```

La valeur effective du paramètre peut être résolue depuis :

1. son expression constante ;
2. `DefaultValue` ;
3. autre métadonnée validée selon le contrat.

---

## 8. Couverture d'un littéral

Valeurs :

```text
FULLY_PARAMETERIZED
PARTIALLY_PARAMETERIZED
NOT_PARAMETERIZED
UNKNOWN
```

### Fully

Toutes les occurrences qui devraient utiliser le paramètre le référencent.

### Partially

Un paramètre existe mais certaines requêtes utilisent encore le littéral brut.

### Not

Aucun paramètre correspondant.

### Unknown

Résolution incomplète.

---

## 9. Décision

Pour un littéral `PARAMETERIZABLE_CONFIRMED` atteignant le seuil :

| Couverture | Statut |
|---|---|
| `FULLY_PARAMETERIZED` | `OK` |
| `PARTIALLY_PARAMETERIZED` | `KO` |
| `NOT_PARAMETERIZED` | `KO` |
| `UNKNOWN` | `NA` |

Pour :

```text
NON_PARAMETERIZABLE
```

```text
NA / OUT_OF_SCOPE
```

Pour :

```text
UNKNOWN
```

```text
NA
```

Un littéral sous le seuil :

```text
NA / OUT_OF_SCOPE
```

---

## 10. Aucun candidat significatif

Si :

- parsing complet ;
- policy configurée ;
- aucun littéral `PARAMETERIZABLE_CONFIRMED` n'atteint le seuil ;

alors :

```text
OK
```

car aucune obligation de paramétrage n'est violée.

---

## 11. Pseudo-code

```python
def evaluate_literal(
    literal,
    context,
):
    policy = context.company_policy.bp12

    if policy is None:
        return finding_na(
            object=literal.id,
            reason="Policy BP-12 non configurée",
        )

    metric_value = literal.distinct_query_count

    if metric_value < policy.repetition_threshold:
        return finding_na(
            object=literal.id,
            reason="Sous le seuil de répétition",
            reason_code="OUT_OF_SCOPE",
        )

    classification = policy.classify_literal_context(
        literal
    )

    if classification == "NON_PARAMETERIZABLE":
        return finding_na(
            object=literal.id,
            reason="Contexte explicitement exclu",
            reason_code="OUT_OF_SCOPE",
        )

    if classification == "UNKNOWN":
        return finding_na(
            object=literal.id,
            reason="Caractère paramétrable non démontré",
        )

    coverage = context.parameter_index.resolve_literal_coverage(
        literal
    )

    if coverage.state == "FULLY_PARAMETERIZED":
        return finding_ok(
            object=literal.id,
            evidence={
                "literal": literal.value,
                "queries": literal.queries,
                "parameter": coverage.parameter_name,
            },
        )

    if coverage.state == "PARTIALLY_PARAMETERIZED":
        return finding_ko(
            object=literal.id,
            reason="Paramétrage partiel",
            evidence={
                "literal": literal.value,
                "parameter": coverage.parameter_name,
                "remaining_raw_occurrences": coverage.remaining_occurrences,
            },
        )

    if coverage.state == "NOT_PARAMETERIZED":
        return finding_ko(
            object=literal.id,
            reason="Valeur répétée non paramétrée",
            evidence={
                "literal": literal.value,
                "queries": literal.queries,
                "repetition_count": metric_value,
                "threshold": policy.repetition_threshold,
            },
        )

    return finding_na(
        object=literal.id,
        reason="Couverture du paramètre non déterminable",
    )
```

---

## 12. Index partagé

Le literal index est construit une seule fois :

```python
m_literal_index = build_m_literal_index(
    context.m_ast
)
```

Il contient :

```text
literal
query
source_file
AST path
function context
argument context
```

BP-12 ne reparcourt pas tous les fichiers avec ses propres regex.

---

## 13. Statut global

Les littéraux sous seuil ou explicitement non paramétrables sont hors périmètre.

```python
evaluable = [
    r for r in results
    if r.reason_code != "OUT_OF_SCOPE"
]

if any(r.status == "KO" for r in evaluable):
    rule_status = "KO"

elif any(r.status == "NA" for r in evaluable):
    rule_status = "NA"

elif evaluable:
    rule_status = "OK"

elif context.m_literal_index.parse_complete:
    rule_status = "OK"

else:
    rule_status = "NA"
```

---

## 14. Preuve obligatoire pour KO

```text
literal
semantic_context
distinct_query_count
threshold
threshold_source
classification = PARAMETERIZABLE_CONFIRMED
parameter_state
queries
source_locations
policy_id
```

---

## 15. Références techniques

Power Query recommande l'utilisation de paramètres pour centraliser et réutiliser des valeurs utilisées dans plusieurs transformations ou requêtes.

Le nombre de répétitions à partir duquel cette pratique devient obligatoire reste une décision de gouvernance du projet.

---

## 16. Résumé

```text
RÈGLE BP-12

PARSER tout le code M
CONSTRUIRE l'index des littéraux

POUR chaque littéral
    SI sous le seuil policy
        -> NA hors périmètre

    CLASSIFIER le contexte

    NON_PARAMETERIZABLE
        -> NA

    UNKNOWN
        -> NA

    PARAMETERIZABLE_CONFIRMED
        VÉRIFIER paramètre

        fully
            -> OK

        partial / none
            -> KO

        unknown
            -> NA
FIN

SI aucun candidat significatif
   ET analyse complète
    -> OK
```
