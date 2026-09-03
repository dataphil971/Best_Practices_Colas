# BP-33 — Utiliser des variables DAX selon une règle de complexité explicite

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier l'utilisation de `VAR` / `RETURN` lorsque le **profil DAX du projet** impose des variables pour certaines mesures.

Le checker ne doit pas inventer une définition universelle de « mesure complexe » à partir de seuils tels que :

```text
120 caractères
profondeur >= 3
2 CALCULATE
```

Ces seuils doivent être configurés ou versionnés dans la politique.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Contexte :

```text
dax_parser
dax_complexity_profile
company_policy
```

---

## 3. Parsing DAX

La complexité doit être mesurée à partir de l'AST, pas par simple comptage de parenthèses.

Métriques possibles :

```text
ast_node_count
function_call_count
conditional_count
iterator_count
max_ast_depth
repeated_subtree_count
```

Le profil précise lesquelles sont décisionnelles.

---

## 4. Profil de complexité

Exemple :

```yaml
bp_33:
  complexity_profile: DAX_COMPLEXITY_V1
  require_var_when:
    repeated_subtree:
      min_ast_nodes: 8
      min_occurrences: 2
    max_ast_depth: 8
```

Le checker ne doit pas fournir ces valeurs par défaut s'il n'existe pas de configuration.

---

## 5. Détection de VAR / RETURN

Le parser doit distinguer :

```text
VAR keyword
RETURN keyword
variable declarations
variable references
```

Pseudo-code :

```python
def has_valid_var_return(
    parsed_dax,
):
    return (
        len(parsed_dax.variables) > 0
        and parsed_dax.has_return
    )
```

Une simple recherche regex de `VAR` dans une chaîne peut être conservée comme fallback non décisionnel.

---

## 6. Sous-expressions répétées

Le moteur peut détecter des sous-arbres AST identiques.

```python
def repeated_significant_subtrees(
    ast,
    profile,
):
    groups = group_identical_subtrees(
        ast
    )

    return [
        group
        for group in groups
        if (
            group.node_count
            >= profile.min_repeated_subtree_nodes
            and group.occurrences
            >= profile.min_repeated_subtree_occurrences
        )
    ]
```

La taille minimale doit provenir du profil.

---

## 7. Applicabilité

Valeurs :

```text
VAR_REQUIRED
VAR_NOT_REQUIRED
UNKNOWN
```

Pseudo-code :

```python
def determine_var_requirement(
    parsed,
    profile,
):
    if profile is None:
        return "UNKNOWN"

    metrics = compute_ast_metrics(
        parsed.ast
    )

    return profile.evaluate_var_requirement(
        metrics=metrics,
        repeated_subtrees=repeated_significant_subtrees(
            parsed.ast,
            profile,
        ),
    )
```

---

## 8. Décision

| Applicabilité | VAR/RETURN | Statut |
|---|---|---|
| `VAR_REQUIRED` | présent | `OK` |
| `VAR_REQUIRED` | absent | `KO` |
| `VAR_NOT_REQUIRED` | présent/absent | `NA` hors périmètre |
| `UNKNOWN` | — | `NA` |
| parsing DAX impossible | — | `NA` |

Une mesure simple n'est donc pas artificiellement comptée `OK` : elle est simplement hors périmètre de l'obligation.

---

## 9. Pseudo-code

```python
def evaluate_measure(
    measure,
    context,
):
    parsed = context.dax_parser.parse(
        measure.expression
    )

    if not parsed.success:
        return finding_na(
            object=measure.qualified_name,
            reason="Expression DAX non parsable",
        )

    requirement = determine_var_requirement(
        parsed,
        context.dax_complexity_profile,
    )

    if requirement == "UNKNOWN":
        return finding_na(
            object=measure.qualified_name,
            reason="Profil de complexité DAX non configuré",
        )

    if requirement == "VAR_NOT_REQUIRED":
        return finding_na(
            object=measure.qualified_name,
            reason="Mesure hors périmètre de l'obligation VAR",
            reason_code="OUT_OF_SCOPE",
        )

    if has_valid_var_return(parsed):
        return finding_ok(
            object=measure.qualified_name,
            evidence={
                "requirement": "VAR_REQUIRED",
                "metrics": compute_ast_metrics(
                    parsed.ast
                ),
            },
        )

    return finding_ko(
        object=measure.qualified_name,
        expected="VAR/RETURN",
        actual="absent",
        evidence={
            "requirement": "VAR_REQUIRED",
            "metrics": compute_ast_metrics(
                parsed.ast
            ),
        },
    )
```

---

## 10. Performance

Le checker ne doit pas affirmer de manière générale :

```text
VAR = évalué une seule fois = toujours plus performant
```

L'usage de variables est principalement évalué ici comme convention de :

- lisibilité ;
- factorisation ;
- maintenabilité.

Une amélioration de performance doit être démontrée séparément par profiling ou analyse adaptée.

---

## 11. Statut global

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

else:
    rule_status = "NA"
```

---

## 12. Preuve obligatoire

Un `KO` doit contenir :

```text
measure
complexity_profile_id
complexity_profile_version
requirement = VAR_REQUIRED
metrics
VAR presence
RETURN presence
source_location
evidence
```

---

## 13. Résumé

```text
RÈGLE BP-33

CHARGER le profil de complexité

POUR chaque mesure
    PARSER le DAX

    SI parsing impossible
        -> NA

    DÉTERMINER si VAR est requis

    UNKNOWN
        -> NA

    VAR_NOT_REQUIRED
        -> NA hors périmètre

    VAR_REQUIRED
        SI VAR/RETURN présent
            -> OK
        SINON
            -> KO
FIN
```
