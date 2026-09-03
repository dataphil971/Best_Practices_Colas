# BP-15 — Maximiser le query folding vers la source

> **Statut d'implémentation : ✅ Implémenté** — moteur : [`03_PYTHON/rules/bp_15.py`](../03_PYTHON/rules/bp_15.py), tests : `03_PYTHON/tests/test_bp_15.py`.

## 1. Objectif

Vérifier le query folding sans transformer une simple analyse statique du code M en preuve de comportement runtime.

Le folding est une propriété d'évaluation de la requête et dépend :

- du connecteur ;
- de ses capacités ;
- de la chaîne d'étapes ;
- du contexte de la requête ;
- du moteur Power Query.

La règle distingue donc :

```text
preuve explicite de folding
preuve explicite de non-folding
configuration empêchant le folding
heuristique statique
```

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
```

Preuves runtime optionnelles :

```text
query plan
folding indicators
View Native Query / native query evidence
diagnostic export
```

Le `AnalysisContext` peut contenir :

```text
folding_capabilities
folding_evidence
m_ast
query_graph
```

---

## 3. États de folding

```text
FOLDED
NOT_FOLDED
UNKNOWN
NOT_APPLICABLE
```

Le checker ne doit pas fabriquer `FOLDED` uniquement parce qu'aucune fonction « suspecte » n'a été trouvée.

---

## 4. Sources non repliables

Si la source est explicitement connue comme non repliable dans le contexte :

```text
NOT_APPLICABLE
```

et :

```text
rule_status = NA
```

Cette règle ne pénalise pas une source pour laquelle le folding n'est pas disponible.

---

## 5. `Value.NativeQuery`

`Value.NativeQuery(..., [EnableFolding=true])` peut permettre le folding d'étapes **ultérieures** lorsque le connecteur et le contexte le supportent.

### Aucun traitement après la requête native

Exemple :

```m
Source =
    Value.NativeQuery(
        Target,
        SqlText,
        null,
        []
    )
in
    Source
```

Il n'existe aucune étape ultérieure à replier.

L'absence de `EnableFolding=true` ne constitue donc pas à elle seule une non-conformité à BP-15.

Résultat :

```text
OK
```

si l'objectif est uniquement de ne pas perdre un folding ultérieur inexistant.

### Étapes après la requête native

Si :

```text
subsequent_steps > 0
```

et que le connecteur est explicitement connu comme supportant le folding sur requête native :

```text
EnableFolding != true
```

alors la configuration empêche de bénéficier du mécanisme prévu pour le folding des étapes suivantes.

```text
KO
```

La preuve doit inclure :

```text
connector_capability
subsequent_steps
EnableFolding
```

### `EnableFolding=true`

La présence de :

```text
EnableFolding=true
```

prouve que le mécanisme est **autorisé**, mais ne prouve pas que toutes les étapes suivantes foldent réellement.

Sans autre preuve :

```text
NA
```

si des étapes ultérieures existent.

---

## 6. Ruptures explicites

Certaines opérations peuvent fournir une preuve statique forte.

### `Table.Buffer`

Si `Table.Buffer` est suivi d'autres transformations, le folding en aval est empêché.

```text
source foldable
+ Table.Buffer
+ étapes après
-> KO
```

Si `Table.Buffer` est la dernière étape :

```text
aucune étape en aval à replier
```

donc le simple fait qu'il soit présent ne suffit pas à produire `KO` pour BP-15.

Un diagnostic de performance peut être ajouté.

### `Table.StopFolding`

Si présent avant des étapes ultérieures :

```text
KO
```

car l'intention même de cette fonction est d'empêcher les opérations en aval d'être exécutées par la source.

### Fonctions à comportement dépendant du contexte

Exemples :

```text
Table.AddColumn
Table.Group
Table.Distinct
Table.Join
```

ne doivent pas être classés automatiquement comme :

```text
FOLD_BREAKING
```

Leur capacité de folding dépend du contexte.

Sans preuve runtime ou contrat précis :

```text
NA + diagnostic
```

---

## 7. Preuves runtime

Lorsqu'un export de diagnostic ou un query plan est disponible :

```python
def evaluate_runtime_folding(evidence):
    if evidence.final_state == "FOLDED":
        return "OK"

    if evidence.final_state == "NOT_FOLDED":
        return "KO"

    return "NA"
```

Cette preuve a priorité sur les heuristiques statiques.

---

## 8. Pseudo-code

```python
def evaluate_query_folding(
    query,
    context,
):
    source_capability = context.folding_capabilities.get(
        query.root_source
    )

    if source_capability == "NON_FOLDABLE":
        return finding_na(
            object=query.name,
            reason="Source non repliable",
            reason_code="NOT_APPLICABLE",
        )

    runtime = context.folding_evidence.get(
        query.name
    )

    if runtime is not None:
        if runtime.final_state == "FOLDED":
            return finding_ok(
                object=query.name,
                evidence=runtime,
            )

        if runtime.final_state == "NOT_FOLDED":
            return finding_ko(
                object=query.name,
                evidence=runtime,
            )

    explicit_break = find_explicit_downstream_folding_break(
        query
    )

    if explicit_break is not None:
        return finding_ko(
            object=query.name,
            reason="Rupture explicite du folding avant des étapes ultérieures",
            evidence=explicit_break,
        )

    native = query.find_value_native_query()

    if native is not None:
        later_steps = query.steps_after(
            native.step
        )

        if not later_steps:
            return finding_ok(
                object=query.name,
                reason="Aucune étape ultérieure à replier",
            )

        capability = context.native_query_folding_support.get(
            query.root_source
        )

        if capability is not True:
            return finding_na(
                object=query.name,
                reason="Capacité de folding sur requête native non démontrée",
            )

        enable = native.options.get(
            "EnableFolding"
        )

        if enable is not True:
            return finding_ko(
                object=query.name,
                expected="EnableFolding=true",
                actual=enable,
                evidence={
                    "subsequent_steps": [
                        s.name for s in later_steps
                    ],
                    "native_query_folding_supported": True,
                },
            )

        return finding_na(
            object=query.name,
            reason=(
                "EnableFolding activé mais folding réel des "
                "étapes suivantes non observé"
            ),
            diagnostic_level="INFO",
        )

    if source_capability != "FOLDABLE":
        return finding_na(
            object=query.name,
            reason="Capacité de folding de la source non déterminée",
        )

    if len(query.transform_steps) == 0:
        return finding_ok(
            object=query.name,
            reason="Aucune transformation après la navigation source",
        )

    return finding_na(
        object=query.name,
        reason="Folding réel non démontré statiquement",
        diagnostics=static_folding_diagnostics(
            query
        ),
    )
```

---

## 9. Détection des ruptures explicites

```python
def find_explicit_downstream_folding_break(
    query,
):
    for index, step in enumerate(query.steps):
        called = step.called_functions

        explicit = None

        if "Table.StopFolding" in called:
            explicit = "Table.StopFolding"

        elif "Table.Buffer" in called:
            explicit = "Table.Buffer"

        if explicit is None:
            continue

        later_steps = query.steps[index + 1:]

        if later_steps:
            return {
                "step": step.name,
                "function": explicit,
                "subsequent_steps": [
                    s.name for s in later_steps
                ],
            }

    return None
```

---

## 10. Matrice de décision

| Situation | Statut |
|---|---|
| source explicitement non repliable | `NA` |
| preuve runtime `FOLDED` | `OK` |
| preuve runtime `NOT_FOLDED` | `KO` |
| `Table.Buffer`/`Table.StopFolding` avec étapes en aval | `KO` |
| `Value.NativeQuery`, aucune étape après | `OK` |
| étapes après native query, support connu, `EnableFolding` absent/faux | `KO` |
| étapes après native query, `EnableFolding=true`, pas de preuve runtime | `NA` |
| source foldable, transformations présentes, pas de preuve runtime | `NA` |
| aucune transformation après source | `OK` |

---

## 11. Statut global

Les requêtes `NOT_APPLICABLE` ne doivent pas faire basculer le résultat.

```python
evaluable = [
    r for r in results
    if r.reason_code != "NOT_APPLICABLE"
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

Un `KO` doit reposer sur au moins une preuve forte :

```text
runtime_state = NOT_FOLDED
```

ou :

```text
explicit_breaking_function + downstream_steps
```

ou :

```text
native_query_folding_supported
+ downstream_steps
+ EnableFolding != true
```

Une liste statique de fonctions « probablement non foldables » n'est jamais suffisante à elle seule.

---

## 13. Références techniques

Cette logique suit les principes documentés par Microsoft Learn concernant :

- le query folding sur `Value.NativeQuery` ;
- l'option `EnableFolding=true` pour permettre le folding des étapes suivantes ;
- les diagnostics/indicateurs de folding ;
- `Table.Buffer`, qui empêche le folding en aval.

---

## 14. Résumé

```text
RÈGLE BP-15

SI source non repliable
    -> NA

SI preuve runtime disponible
    FOLDED -> OK
    NOT_FOLDED -> KO

SINON
    RECHERCHER une rupture explicite

    SI rupture explicite + étapes en aval
        -> KO

    SI Value.NativeQuery
        SI aucune étape après
            -> OK

        SI support du folding inconnu
            -> NA

        SI support connu ET EnableFolding != true
            -> KO

        SI EnableFolding=true mais résultat non observé
            -> NA

    SI aucune transformation
        -> OK

    SINON
        -> NA + diagnostic
```
