# BP-26 — Documenter les champs dont l'ambiguïté est démontrée

## 1. Objectif

Vérifier qu'un champ visible identifié comme **ambigu pour l'utilisateur** dispose d'une description.

La présence d'une description est déterministe.

En revanche, décider qu'un nom est « évident » ou « ambigu » est une question contextuelle qui ne doit pas être résolue par une simple liste générique de mots comme :

```text
Color
Status
Type
Code
Value
Result
```

Statuts :

```text
OK / KO / NA
```

---

## 2. Architecture hybride

La règle comporte deux étapes.

### Étape A — qualification de l'ambiguïté

Valeurs :

```text
AMBIGUOUS_CONFIRMED
NOT_AMBIGUOUS
UNKNOWN
```

Cette qualification peut provenir :

- d'une politique d'entreprise ;
- d'un glossaire ;
- d'une liste explicite de champs à documenter ;
- d'un reviewer contextuel ;
- d'une validation humaine.

### Étape B — contrôle déterministe

Pour un champ `AMBIGUOUS_CONFIRMED` :

```text
description présente -> OK
description absente  -> KO
description illisible -> NA
```

---

## 3. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Contexte :

```text
business_glossary
company_policy
context_review_results
field_description_index
```

---

## 4. Périmètre

Par défaut, la règle cible les champs exposés aux utilisateurs.

Un champ masqué :

```text
NA / hors périmètre
```

sauf si la politique d'entreprise exige explicitement sa documentation.

---

## 5. Qualification par politique

Exemple :

```yaml
bp_26:
  fields_requiring_description:
    - MEASURE[Color_Worry]
    - MEASURE[NOTIF_Icon]
    - F_RESPONSES[WORRY_CODE]
```

Ces champs sont alors :

```text
AMBIGUOUS_CONFIRMED
```

sans interprétation du checker.

---

## 6. Qualification par glossaire

Un champ peut être considéré non ambigu si son sens est explicitement résolu par un glossaire fiable.

Exemple :

```text
USER_COUNTRY -> "Pays de résidence déclaré par l'utilisateur"
```

Cela peut alimenter :

```text
NOT_AMBIGUOUS
```

ou servir de preuve contextuelle.

Le simple nom ne suffit pas.

---

## 7. Qualification contextuelle

Un `agent-bi-context-reviewer` peut recevoir :

```text
field_name
table_name
data_type
DAX expression / source context
display folder
usage in report
business glossary
```

et retourner :

```text
AMBIGUOUS_CONFIRMED
NOT_AMBIGUOUS
UNKNOWN
```

Le reviewer ne doit pas produire directement le `rule_status`.

Le checker déterministe applique ensuite la règle documentaire.

---

## 8. Description

États :

```text
PRESENT
ABSENT
UNREADABLE
```

Pseudo-code :

```python
def description_state(field):
    if field.description_parse_error:
        return "UNREADABLE"

    if field.description is None:
        return "ABSENT"

    if not field.description.strip():
        return "ABSENT"

    return "PRESENT"
```

---

## 9. Placeholders

Les placeholders ne sont considérés comme invalides que s'ils sont configurés.

```python
placeholders = (
    context.company_policy
    .description_placeholders
)
```

Exemples possibles :

```text
TODO
TBD
À compléter
```

Le checker ne doit pas inventer de longueur minimale universelle comme `10 caractères`.

---

## 10. Décision

| Ambiguïté | Description | Statut |
|---|---|---|
| `AMBIGUOUS_CONFIRMED` | présente | `OK` |
| `AMBIGUOUS_CONFIRMED` | absente | `KO` |
| `AMBIGUOUS_CONFIRMED` | illisible | `NA` |
| `NOT_AMBIGUOUS` | quelconque | `NA` hors périmètre |
| `UNKNOWN` | quelconque | `NA` |
| champ masqué sans exigence spécifique | — | `NA` |

---

## 11. Pseudo-code

```python
def evaluate_field(
    field,
    context,
):
    if (
        field.is_hidden
        and not context.company_policy.requires_hidden_field_description(
            field.qualified_name
        )
    ):
        return finding_na(
            object=field.qualified_name,
            reason="Champ masqué, hors périmètre",
            reason_code="OUT_OF_SCOPE",
        )

    ambiguity = context.field_ambiguity_index.get(
        field.qualified_name
    )

    if ambiguity == "NOT_AMBIGUOUS":
        return finding_na(
            object=field.qualified_name,
            reason="Champ non ambigu selon le contexte validé",
            reason_code="OUT_OF_SCOPE",
        )

    if ambiguity != "AMBIGUOUS_CONFIRMED":
        return finding_na(
            object=field.qualified_name,
            reason="Ambiguïté non déterminée de manière fiable",
        )

    state = description_state(field)

    if state == "UNREADABLE":
        return finding_na(
            object=field.qualified_name,
            reason="Description non interprétable",
        )

    if state == "ABSENT":
        return finding_ko(
            object=field.qualified_name,
            expected="description présente",
            actual=None,
            evidence={
                "ambiguity": "AMBIGUOUS_CONFIRMED",
                "ambiguity_evidence": context.field_ambiguity_evidence(
                    field.qualified_name
                ),
            },
        )

    if context.company_policy.is_forbidden_description_placeholder(
        field.description
    ):
        return finding_ko(
            object=field.qualified_name,
            reason="Placeholder de description explicitement interdit",
            actual=field.description,
        )

    return finding_ok(
        object=field.qualified_name,
        evidence={
            "description": field.description,
            "ambiguity": "AMBIGUOUS_CONFIRMED",
        },
    )
```

---

## 12. Statut global

Les champs non ambigus / hors périmètre ne comptent pas.

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

## 13. Preuve obligatoire

Pour un `KO` :

```text
field
ambiguity = AMBIGUOUS_CONFIRMED
ambiguity_source
ambiguity_evidence
description_state = ABSENT
source_file
evidence
```

Une regex de nommage ou la présence de `IF/SWITCH` ne suffit jamais seule.

---

## 14. Résumé

```text
RÈGLE BP-26

POUR chaque champ visible
    RÉCUPÉRER la qualification d'ambiguïté

    NOT_AMBIGUOUS
        -> NA

    UNKNOWN
        -> NA

    AMBIGUOUS_CONFIRMED
        LIRE la description

        SI absente
            -> KO

        SI illisible
            -> NA

        SINON
            -> OK
FIN
```
