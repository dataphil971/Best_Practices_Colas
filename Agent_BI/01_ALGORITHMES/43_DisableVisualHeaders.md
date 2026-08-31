# BP-43 — Configurer les en-têtes de visuels selon le besoin utilisateur

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier que l'état effectif des icônes d'en-tête d'un visuel respecte une politique explicite du rapport.

La règle ne doit pas supposer qu'un type de visuel possède ou non un en-tête « utile » uniquement à partir de :

```text
card
gauge
textbox
table
matrix
```

L'utilité des actions disponibles dépend du contexte utilisateur.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<REPORT_PATH>/definition/report.json
<REPORT_PATH>/definition/pages/**/page.json
<REPORT_PATH>/definition/pages/**/visual.json
<REPORT_PATH>/StaticResources/**
```

Contexte :

```text
visual_formatting_index
theme_defaults
report_defaults
company_policy
visual_header_reviews
```

---

## 3. Header icons

Power BI permet :

- de masquer toutes les icônes d'en-tête ;
- de laisser l'en-tête actif ;
- de sélectionner individuellement les icônes exposées.

Exemples d'actions :

```text
focus mode
drill
filter information
more options
help tooltip
personalize visual
copy
```

La règle doit donc contrôler :

```text
effective header configuration
```

et pas seulement un booléen brut.

---

## 4. Résolution de la valeur effective

L'état peut provenir de plusieurs niveaux :

1. propriété spécifique au visuel ;
2. default/report visual properties ;
3. thème ;
4. comportement système.

Le backend doit résoudre la cascade.

Valeurs :

```text
ENABLED
DISABLED
PARTIAL
UNKNOWN
```

Pseudo-code :

```python
def resolve_effective_header(
    visual,
    context,
):
    direct = context.visual_formatting_index.get_header(
        visual.id
    )

    if direct.is_explicit:
        return direct

    report_default = context.report_defaults.resolve_header(
        visual.visual_type
    )

    if report_default is not None:
        return report_default

    theme_default = context.theme_defaults.resolve_header(
        visual.visual_type
    )

    if theme_default is not None:
        return theme_default

    return HeaderState(
        state="UNKNOWN"
    )
```

---

## 5. Point critique : propriété absente

Le comportement suivant est interdit :

```python
if visualHeader is absent:
    header_active = True
```

L'absence de surcharge locale peut simplement signifier :

```text
héritage du thème / default
```

Si la valeur effective n'est pas résolue :

```text
NA
```

---

## 6. Besoin attendu

Valeurs :

```text
HEADER_DISABLED_REQUIRED
HEADER_ENABLED_REQUIRED
HEADER_POLICY
UNKNOWN
```

Exemple :

```yaml
bp_43:
  rules:
    - page: Executive Summary
      visual_role: KPI
      header: disabled
    - visual_type: tableEx
      allowed_icons:
        - focusMode
        - moreOptions
```

---

## 7. Classification par type

Le type du visuel peut aider à sélectionner une policy, mais ne constitue pas en soi la décision.

Exemple :

```text
card -> policy KPI
```

uniquement si cette correspondance est explicitement configurée.

Sans policy :

```text
NA
```

---

## 8. Contrôle des icônes individuelles

Si la policy autorise seulement certaines actions :

```python
expected_icons = policy.allowed_icons
actual_icons = header.enabled_icons
```

Un `KO` nécessite une violation explicite.

Exemple :

```text
export/copy interdit
+
icône correspondante activée
-> KO
```

La règle ne doit pas affirmer que masquer l'en-tête protège à lui seul contre toutes les fonctions d'export du tenant/service.

---

## 9. Décision

| Besoin | État effectif | Statut |
|---|---|---|
| header désactivé requis | `DISABLED` | `OK` |
| header désactivé requis | `ENABLED/PARTIAL` | `KO` |
| header activé requis | `ENABLED/PARTIAL` conforme | `OK` |
| icônes autorisées/interdites configurées et violation démontrée | — | `KO` |
| valeur effective inconnue | — | `NA` |
| besoin inconnu | — | `NA` |

---

## 10. Pseudo-code

```python
def evaluate_visual(
    visual,
    context,
):
    requirement = context.company_policy.resolve_visual_header_requirement(
        page=visual.page,
        visual=visual,
    )

    if requirement is None:
        return finding_na(
            object=visual.id,
            reason="Aucune politique d'en-tête applicable",
            reason_code="OUT_OF_SCOPE_OR_UNKNOWN",
        )

    effective = resolve_effective_header(
        visual,
        context,
    )

    if effective.state == "UNKNOWN":
        return finding_na(
            object=visual.id,
            reason="État effectif des icônes d'en-tête non résolu",
        )

    violations = requirement.find_violations(
        effective
    )

    if violations:
        return finding_ko(
            object=visual.id,
            expected=requirement.to_evidence(),
            actual=effective.to_evidence(),
            evidence={
                "violations": violations,
            },
        )

    return finding_ok(
        object=visual.id,
        evidence={
            "effective_header": effective.to_evidence(),
            "requirement": requirement.to_evidence(),
        },
    )
```

---

## 11. Conteneurs et visuels sans en-tête applicable

Les objets comme :

```text
visualGroup
shape
image
```

peuvent ne pas exposer les mêmes actions d'en-tête selon le format/version.

Ils ne doivent pas être automatiquement classés `OK` ou `KO`.

Si la policy et le schéma les déclarent hors périmètre :

```text
NA / OUT_OF_SCOPE
```

---

## 12. Statut global

```python
evaluable = [
    r for r in results
    if r.reason_code != "OUT_OF_SCOPE_OR_UNKNOWN"
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

## 13. Preuve obligatoire pour KO

```text
page
visual_id
visual_type
header_policy_id
header_policy_version
effective_header_state
enabled_icons
disabled_icons
resolution_sources
violation
source_file
evidence
```

---

## 14. Références techniques

Microsoft documente que :

- les icônes d'en-tête peuvent être désactivées globalement pour un visuel ;
- elles peuvent aussi être activées/désactivées individuellement ;
- certaines fonctionnalités, comme l'aide ou la personnalisation, dépendent directement de ces icônes.

La configuration effective doit donc être comparée à l'intention du rapport.

---

## 15. Résumé

```text
RÈGLE BP-43

POUR chaque visuel concerné
    RÉSOUDRE la policy attendue
    RÉSOUDRE l'état effectif
        visuel
        defaults
        thème

    SI besoin inconnu
        -> NA

    SI état effectif inconnu
        -> NA

    SI violation explicite
        -> KO

    SINON
        -> OK
FIN
```
