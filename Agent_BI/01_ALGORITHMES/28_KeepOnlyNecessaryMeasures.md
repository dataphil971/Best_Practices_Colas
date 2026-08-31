# BP-28 — Détecter les mesures potentiellement redondantes

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Détecter les mesures qui semblent dupliquées ou agir comme des alias, sans confondre :

```text
équivalence technique du calcul
```

avec :

```text
mesure inutile
```

Deux mesures peuvent volontairement partager la même expression DAX tout en ayant :

- des noms métier différents ;
- des formats différents ;
- des descriptions différentes ;
- des dossiers d'affichage différents ;
- des usages différents ;
- un rôle de compatibilité ou de transition.

La détection automatique produit donc des **candidats à redondance**.

Statuts :

```text
OK / KO / NA
```

---

## 2. Architecture hybride

### Python déterministe

Il détecte :

```text
EXACT_EXPRESSION_CANDIDATE
DIRECT_ALIAS_CANDIDATE
STRUCTURAL_SIMILARITY
```

### Qualification contextuelle

Chaque candidat exact/alias reçoit :

```text
JUSTIFIED
REDUNDANT_CONFIRMED
UNRESOLVED
```

Un `KO` n'est produit que pour :

```text
REDUNDANT_CONFIRMED
```

ou en application d'une `COMPANY_POLICY` explicite interdisant le cas.

---

## 3. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Le contexte peut fournir :

```text
DAX AST
measure dependency graph
usage_index
format strings
display folders
descriptions
company policy
review results
```

---

## 4. Canonicalisation DAX

Le checker doit utiliser un tokenizer / parser / AST DAX.

Il ne doit pas retirer les commentaires avec des regex naïves susceptibles d'altérer des chaînes de caractères contenant :

```text
--
//
/*
```

Pseudo-code :

```python
def canonical_dax_expression(
    measure,
    context,
):
    parsed = context.dax_parser.parse(
        measure.expression
    )

    if not parsed.success:
        return CanonicalizationResult(
            status="UNRESOLVED",
            reason=parsed.error,
        )

    canonical = context.dax_canonicalizer.serialize(
        parsed.ast,
        normalize_keyword_case=True,
        normalize_whitespace=True,
        preserve_identifiers=True,
        preserve_literals=True,
    )

    return CanonicalizationResult(
        status="OK",
        canonical=canonical,
    )
```

---

## 5. Doublon d'expression exact

Deux mesures sont candidates si leurs expressions canoniques sont identiques.

```text
expression_identical = true
```

Mais ce constat produit :

```text
candidate
```

et non `KO`.

Le moteur conserve également les métadonnées :

```text
name
formatString
description
displayFolder
host table
usage
```

---

## 6. Alias direct

Exemple :

```dax
Measure B = [Measure A]
```

Le parser peut détecter :

```text
DIRECT_ALIAS_CANDIDATE
```

Cela peut être volontaire.

Exemples :

- nom d'affichage simplifié ;
- migration progressive ;
- façade métier ;
- compatibilité d'un rapport historique.

Donc :

```text
alias direct != KO automatique
```

---

## 7. Similarité structurelle

Des expressions comme :

```text
CALCULATE([Nb], ALL(F[WORRY_LEVEL]))
CALCULATE([Nb], ALL(F[INTEREST_LEVEL]))
```

peuvent partager un patron.

Cette information relève plutôt :

- d'un diagnostic ;
- de BP-34 pour les calculation groups.

Elle ne dégrade pas BP-28.

```text
STRUCTURAL_SIMILARITY -> diagnostic only
```

---

## 8. Détection

```python
def detect_measure_candidates(
    measures,
    context,
):
    exact_groups = {}
    aliases = []
    unresolved = []

    for measure in measures:
        canonical = canonical_dax_expression(
            measure,
            context,
        )

        if canonical.status != "OK":
            unresolved.append({
                "measure": measure.qualified_name,
                "reason": canonical.reason,
            })
            continue

        exact_groups.setdefault(
            canonical.canonical,
            []
        ).append(measure)

        alias = context.dax_ast.detect_direct_measure_alias(
            measure
        )

        if alias is not None:
            aliases.append({
                "measure": measure.qualified_name,
                "target": alias.target_measure,
            })

    exact_candidates = [
        group
        for group in exact_groups.values()
        if len(group) >= 2
    ]

    return {
        "exact_candidates": exact_candidates,
        "alias_candidates": aliases,
        "unresolved": unresolved,
    }
```

---

## 9. Qualification d'un candidat

Le reviewer reçoit au minimum :

```text
canonical expression
measure names
formatString
description
displayFolder
usage locations
dependency graph
```

Décisions :

### `JUSTIFIED`

Les mesures ont une justification distincte démontrée.

### `REDUNDANT_CONFIRMED`

La duplication est confirmée comme inutile.

### `UNRESOLVED`

L'intention ne peut pas être déterminée.

---

## 10. Politique déterministe optionnelle

Une entreprise peut définir une règle stricte, par exemple :

```yaml
bp_28:
  forbid_exact_duplicate_measures_with_identical_metadata: true
```

Le checker peut alors produire `KO` uniquement si **toutes** les conditions configurées sont satisfaites.

Exemple :

```text
même expression canonique
même format
même description
même dossier
aucune justification configurée
+ policy explicite
-> KO
```

Sans policy :

```text
candidate -> NA jusqu'à qualification
```

---

## 11. Décision

| Situation | Statut |
|---|---|
| aucune mesure candidate, parsing complet | `OK` |
| candidat(s) exact(s) ou alias non qualifiés | `NA` |
| tous les candidats sont justifiés | `OK` |
| au moins un candidat est confirmé redondant | `KO` |
| policy explicite violée | `KO` |
| parsing DAX incomplet pouvant masquer un candidat | `NA` |
| aucune mesure dans le modèle | `NA` |

---

## 12. Pseudo-code global

```python
def evaluate_bp28(
    semantic_model,
    context,
):
    measures = semantic_model.all_measures()

    if not measures:
        return rule_na(
            reason="Aucune mesure dans le modèle"
        )

    candidates = detect_measure_candidates(
        measures,
        context,
    )

    if (
        not candidates["exact_candidates"]
        and not candidates["alias_candidates"]
    ):
        if candidates["unresolved"]:
            return rule_na(
                reason="Certaines mesures n'ont pas pu être analysées",
                evidence={
                    "unresolved": candidates["unresolved"],
                },
            )

        return rule_ok(
            evidence={
                "candidate_count": 0,
            },
        )

    decisions = []

    for candidate in build_candidate_objects(
        candidates
    ):
        policy = evaluate_bp28_policy(
            candidate,
            context.company_policy,
        )

        if policy is not None:
            decisions.append(policy)
            continue

        review = context.measure_redundancy_reviews.get(
            candidate.id
        )

        if review is None:
            decisions.append("UNRESOLVED")
        else:
            decisions.append(review.decision)

    if "REDUNDANT_CONFIRMED" in decisions:
        return rule_ko(
            evidence={
                "decisions": decisions,
            },
        )

    if "UNRESOLVED" in decisions:
        return rule_na(
            evidence={
                "decisions": decisions,
            },
        )

    if candidates["unresolved"]:
        return rule_na(
            reason="Analyse DAX partielle",
            evidence={
                "unresolved": candidates["unresolved"],
            },
        )

    return rule_ok(
        evidence={
            "decisions": decisions,
        },
    )
```

---

## 13. Preuve obligatoire

Un `KO` doit contenir :

```text
candidate_id
candidate_type
measure_names
canonical_expression
metadata
usage
decision = REDUNDANT_CONFIRMED
decision_source
decision_evidence
```

Une égalité de hash DAX seule n'est pas suffisante.

---

## 14. Résumé

```text
RÈGLE BP-28

EXTRAIRE toutes les mesures
PARSE le DAX avec AST/tokenizer

DÉTECTER :
    expressions identiques
    alias directs

SI aucun candidat et analyse complète
    -> OK

SI candidat
    QUALIFIER :
        JUSTIFIED
        REDUNDANT_CONFIRMED
        UNRESOLVED

    REDUNDANT_CONFIRMED
        -> KO

    UNRESOLVED
        -> NA

    tous JUSTIFIED
        -> OK

SI parsing incomplet
    -> NA
```

Python détecte la similarité ; il ne décide pas seul qu'une mesure est inutile.
