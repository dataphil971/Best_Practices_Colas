# BP-35 — Commentaires utiles dans le code complexe

## 1. Objectif

Vérifier la présence et, lorsque le contexte le permet, l'utilité des commentaires dans du code DAX ou M identifié comme nécessitant une documentation interne.

La règle doit séparer deux problèmes :

1. **présence de commentaire** — déterministe ;
2. **qualité / utilité du commentaire** — contextuelle.

Le checker ne doit pas décider qu'un commentaire est « utile » uniquement parce qu'il contient plus de deux mots.

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

Contexte :

```text
dax_parser
m_parser
code_complexity_profile
company_policy
comment_review_results
```

---

## 3. Applicabilité

Valeurs :

```text
COMMENT_REQUIRED
COMMENT_NOT_REQUIRED
UNKNOWN
```

L'applicabilité doit provenir d'un profil versionné.

Exemple :

```yaml
bp_35:
  complexity_profile: CODE_COMPLEXITY_V1
  require_comments_for:
    dax:
      conditional_count: 2
      ast_depth: 8
    m:
      heavy_steps: 2
```

Ces chiffres sont des exemples de configuration, pas des valeurs universelles.

---

## 4. Extraction robuste des commentaires

Les commentaires doivent être extraits par tokenizer / parser afin d'éviter les faux positifs dans les chaînes de caractères.

Types possibles :

### DAX

```text
--
//
// si supporté par le parseur
/* ... */
```

### M

```text
//
/* ... */
```

Pseudo-code :

```python
comments = context.code_parser.extract_comments(
    code,
    language=language,
)
```

---

## 5. État de présence

```text
PRESENT
ABSENT
UNREADABLE
```

```python
def comment_presence(
    parsed_code,
):
    if not parsed_code.success:
        return "UNREADABLE"

    return (
        "PRESENT"
        if parsed_code.comments
        else "ABSENT"
    )
```

---

## 6. Qualité du commentaire

Valeurs du reviewer :

```text
USEFUL
TRIVIAL_OR_MISLEADING
UNKNOWN
```

Le reviewer reçoit :

```text
code
comment
objet
contexte métier disponible
raison pour laquelle le commentaire est requis
```

Il ne doit pas se baser uniquement sur :

```text
longueur
nombre de mots
liste de mots génériques
```

---

## 7. Politique de décision

Deux modes sont possibles.

### Mode A — présence obligatoire

```yaml
require_useful_comment_review: false
```

Alors :

```text
COMMENT_REQUIRED + commentaire présent -> OK
COMMENT_REQUIRED + commentaire absent  -> KO
```

### Mode B — utilité obligatoire

```yaml
require_useful_comment_review: true
```

Alors :

```text
commentaire présent + USEFUL              -> OK
commentaire présent + TRIVIAL_OR_MISLEADING -> KO
commentaire présent + UNKNOWN             -> NA
commentaire absent                        -> KO
```

---

## 8. Code non concerné

Si le profil détermine :

```text
COMMENT_NOT_REQUIRED
```

le résultat élémentaire est :

```text
NA / OUT_OF_SCOPE
```

Une expression triviale n'est donc pas artificiellement comptée `OK`.

---

## 9. Pseudo-code

```python
def evaluate_code_element(
    element,
    context,
):
    parsed = context.code_parser.parse(
        element.code,
        language=element.language,
    )

    if not parsed.success:
        return finding_na(
            object=element.id,
            reason="Code non parsable",
        )

    requirement = (
        context.code_complexity_profile
        .comment_requirement(
            parsed=parsed,
            language=element.language,
        )
        if context.code_complexity_profile
        else "UNKNOWN"
    )

    if requirement == "UNKNOWN":
        return finding_na(
            object=element.id,
            reason="Profil de complexité/commentaires non configuré",
        )

    if requirement == "COMMENT_NOT_REQUIRED":
        return finding_na(
            object=element.id,
            reason="Commentaire non requis pour cet élément",
            reason_code="OUT_OF_SCOPE",
        )

    if not parsed.comments:
        return finding_ko(
            object=element.id,
            expected="commentaire présent",
            actual="absent",
            evidence={
                "requirement": "COMMENT_REQUIRED",
                "complexity_evidence": parsed.complexity_metrics,
            },
        )

    if not context.company_policy.require_useful_comment_review:
        return finding_ok(
            object=element.id,
            evidence={
                "comment_count": len(parsed.comments),
            },
        )

    review = context.comment_reviews.get(
        element.id
    )

    if review is None or review.decision == "UNKNOWN":
        return finding_na(
            object=element.id,
            reason="Utilité du commentaire non qualifiée",
            evidence={
                "comments": parsed.comments,
            },
        )

    if review.decision == "TRIVIAL_OR_MISLEADING":
        return finding_ko(
            object=element.id,
            reason="Commentaire jugé non utile selon le contexte",
            evidence={
                "review": review.to_evidence(),
            },
        )

    return finding_ok(
        object=element.id,
        evidence={
            "review": review.to_evidence(),
        },
    )
```

---

## 10. Statut global

Les éléments pour lesquels aucun commentaire n'est requis sont hors périmètre.

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

## 11. Sur-commentation

La « sur-commentation » est un jugement qualitatif.

Elle ne doit pas créer un statut `WARN`.

Elle peut être transmise au reviewer comme diagnostic :

```text
possible_overcommenting
```

sans modifier `rule_status` tant qu'aucune politique explicite ne l'interdit.

---

## 12. Preuve obligatoire

Pour un `KO` par absence :

```text
element
language
complexity_profile
requirement = COMMENT_REQUIRED
comments_found = 0
complexity_evidence
```

Pour un `KO` qualitatif :

```text
element
comments
review = TRIVIAL_OR_MISLEADING
review_source
review_evidence
```

---

## 13. Résumé

```text
RÈGLE BP-35

POUR chaque mesure DAX / requête M
    PARSER le code
    DÉTERMINER si commentaire requis

    UNKNOWN
        -> NA

    COMMENT_NOT_REQUIRED
        -> NA hors périmètre

    COMMENT_REQUIRED
        SI aucun commentaire
            -> KO

        SI contrôle de présence uniquement
            -> OK

        SINON
            QUALIFIER l'utilité

            USEFUL
                -> OK

            TRIVIAL_OR_MISLEADING
                -> KO

            UNKNOWN
                -> NA
FIN
```
