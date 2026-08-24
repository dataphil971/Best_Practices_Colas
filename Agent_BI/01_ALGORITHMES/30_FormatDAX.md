# BP-30 — Formatage standardisé du code DAX

## 1. Objectif

Vérifier que le code DAX respecte le **profil de formatage explicitement retenu par l'entreprise ou le projet**.

Le checker ne doit pas inventer des standards universels tels que :

```text
ligne < 80 caractères
ligne < 100 caractères
4 espaces d'indentation
une fonction par ligne
```

Ces choix sont des conventions de style.

Ils ne peuvent produire un `KO` que s'ils sont définis dans un profil de formatage applicable au projet.

Statuts :

```text
OK / KO / NA
```

Les écarts purement informatifs sont portés séparément via :

```text
diagnostic_level
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Contexte requis pour un verdict complet :

```text
dax_formatter_profile
company_policy
dax_parser
```

Le profil peut être :

- un formatter approuvé par l'entreprise ;
- un ensemble de règles de style versionnées ;
- une représentation canonique produite par le backend.

---

## 3. Principe de décision

La règle ne juge pas la « beauté » du code.

Elle vérifie une conformité à un contrat.

Exemple de profil :

```yaml
dax_formatting:
  version: 1
  required:
    canonical_formatter: COMPANY_DAX_FORMAT_V1
  advisory:
    max_line_length: 120
```

Dans cet exemple :

- l'écart au formatter canonique peut produire `KO` ;
- la longueur de ligne est seulement un diagnostic.

---

## 4. Extraction

Le moteur doit extraire :

```text
raw_dax
source_file
source_location
```

en conservant :

- espaces ;
- tabulations ;
- sauts de ligne ;
- commentaires.

Si l'expression n'est pas lisible :

```text
NA
```

---

## 5. Parsing

Le code doit être parsé avant toute analyse de style afin de distinguer :

```text
code
chaînes de caractères
commentaires
identifiants
opérateurs
```

Une analyse basée sur :

```python
line.count("(")
line.count(",")
```

n'est pas suffisamment robuste pour produire un verdict.

Pseudo-code :

```python
def parse_measure_for_formatting(
    measure,
    context,
):
    parsed = context.dax_parser.parse(
        measure.expression
    )

    if not parsed.success:
        return None

    return parsed
```

---

## 6. Formatter canonique

Si le profil configure un formatter canonique :

```python
formatted = context.dax_formatter.format(
    parsed.ast,
    profile=context.dax_formatter_profile,
)
```

La comparaison ne doit porter que sur les propriétés de style couvertes par le profil.

Exemple :

```python
comparison = compare_dax_formatting(
    raw=measure.raw_expression,
    canonical=formatted,
    profile=context.dax_formatter_profile,
)
```

Sortie :

```text
COMPLIANT
NON_COMPLIANT
UNKNOWN
```

---

## 7. Règles obligatoires et règles consultatives

Chaque règle du profil doit avoir une sévérité explicite.

```text
REQUIRED
ADVISORY
```

Exemples possibles :

```text
indentation
line_breaks
operator_spacing
comma_spacing
keyword_layout
max_line_length
```

Le backend ne doit pas supposer que `max_line_length` est bloquant.

---

## 8. Décision par mesure

| Situation | Statut |
|---|---|
| profil applicable + toutes les règles `REQUIRED` respectées | `OK` |
| profil applicable + au moins une règle `REQUIRED` violée | `KO` |
| profil absent | `NA` |
| DAX non parsable / extraction incomplète | `NA` |
| uniquement des écarts `ADVISORY` | `OK` + diagnostic |

---

## 9. Pseudo-code

```python
def evaluate_measure_format(
    measure,
    context,
):
    profile = context.dax_formatter_profile

    if profile is None:
        return finding_na(
            object=measure.qualified_name,
            reason="Profil de formatage DAX non configuré",
        )

    parsed = context.dax_parser.parse(
        measure.expression
    )

    if not parsed.success:
        return finding_na(
            object=measure.qualified_name,
            reason="Expression DAX non parsable",
            evidence={
                "parse_error": parsed.error,
            },
        )

    result = context.dax_formatter.check(
        raw_expression=measure.raw_expression,
        ast=parsed.ast,
        profile=profile,
    )

    required_violations = [
        v for v in result.violations
        if v.severity == "REQUIRED"
    ]

    advisory_violations = [
        v for v in result.violations
        if v.severity == "ADVISORY"
    ]

    if required_violations:
        return finding_ko(
            object=measure.qualified_name,
            expected=profile.id,
            actual="NON_COMPLIANT",
            evidence={
                "required_violations": required_violations,
                "advisory_violations": advisory_violations,
                "profile_version": profile.version,
            },
        )

    return finding_ok(
        object=measure.qualified_name,
        evidence={
            "profile_version": profile.version,
            "advisory_violations": advisory_violations,
        },
        diagnostic_level=(
            "INFO"
            if advisory_violations
            else None
        ),
    )
```

---

## 10. Statut global

```python
if not measures:
    rule_status = "NA"

elif any(r.status == "KO" for r in results):
    rule_status = "KO"

elif any(r.status == "NA" for r in results):
    rule_status = "NA"

else:
    rule_status = "OK"
```

Priorité :

```text
KO > NA > OK
```

---

## 11. Preuve obligatoire

Un `KO` doit contenir :

```text
measure
formatter_profile_id
formatter_profile_version
required_rule
expected
actual
source_location
evidence
```

Il ne doit jamais être justifié uniquement par :

```text
"ligne trop longue"
```

sans seuil configuré.

---

## 12. Résumé

```text
RÈGLE BP-30

CHARGER le profil DAX

SI profil absent
    -> NA

POUR chaque mesure
    PARSER le DAX

    SI parsing impossible
        -> NA

    APPLIQUER le formatter / profil

    SI règle REQUIRED violée
        -> KO

    SINON
        -> OK
        + diagnostics advisory éventuels
FIN
```
