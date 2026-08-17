# BP-41 — Détection des visuels redondants ou dupliqués

## 1. Objectif

Détecter de manière déterministe les **candidats** à la redondance visuelle, puis séparer cette détection technique du jugement portant sur leur utilité réelle.

Deux visuels présentant la même signature analytique ne sont pas nécessairement inutiles.

Exemples de répétitions potentiellement justifiées :

- même KPI repris sur plusieurs pages ;
- rappel d'un indicateur de synthèse ;
- même donnée utilisée dans deux contextes narratifs différents ;
- visuel similaire sur une page principale et une page de détail ;
- visuel dupliqué volontairement pour un scénario de navigation.

Par conséquent :

```text
signature identique ≠ redondance métier prouvée
```

Statuts Agent BI :

```text
OK / KO / NA
```

---

## 2. Architecture de la règle

La règle est **hybride**.

### Partie Python déterministe

Elle :

1. parcourt les visuels ;
2. construit une signature canonique ;
3. regroupe les signatures identiques ;
4. produit des `duplicate_candidates`.

### Partie contextuelle / validation

Elle détermine, uniquement pour les candidats :

```text
JUSTIFIED
REDUNDANT_CONFIRMED
UNRESOLVED
```

Cette validation peut provenir :

- d'une politique d'entreprise explicite ;
- d'une justification déclarée ;
- d'un Context Reviewer ;
- d'une validation humaine.

Le checker Python ne doit jamais transformer seul un candidat en `KO` sur la simple égalité des signatures.

---

## 3. Sources

```text
<REPORT_PATH>/definition/pages/pages.json
<REPORT_PATH>/definition/pages/<pageId>/page.json
<REPORT_PATH>/definition/pages/<pageId>/visuals/<visualId>/visual.json
```

Le `AnalysisContext` doit fournir si possible :

```text
page_id
page_name
page_visibility
visual_id
visual_type
query_state
visual_filters
title
position
group
navigation_context
parse_status
```

Les propriétés de présentation ne font pas nécessairement partie de la signature analytique, mais peuvent être conservées comme **contexte de justification**.

---

## 4. Visuels hors périmètre analytique

Exemples :

```text
textbox
image
shape
actionButton
basicShape
visualGroup container
```

Ils sont classés :

```text
NA / hors périmètre
```

Ils ne participent pas à la recherche de doublons analytiques.

---

## 5. Signature analytique canonique

La signature déterministe peut inclure :

1. `visualType` ;
2. rôles de projection ;
3. références techniques de champs/mesures ;
4. filtres propres au visuel normalisés ;
5. tris analytiques lorsque leur effet sur le résultat est pertinent.

Pseudo-code :

```python
def build_visual_signature(visual, context):
    if visual.type in NON_ANALYTICAL_TYPES:
        return None

    if not visual.query_state_parseable:
        raise VisualSignatureError(
            "queryState non interprétable"
        )

    roles = []

    for role_name in sorted(visual.query_state.roles):
        projections = visual.query_state.roles[role_name]

        refs = sorted(
            canonical_query_ref(p)
            for p in projections
        )

        roles.append((
            canonical_role_name(role_name),
            tuple(refs),
        ))

    filters = tuple(sorted(
        canonical_filter(f)
        for f in visual.visual_filters
    ))

    analytical_sort = tuple(sorted(
        canonical_sort(s)
        for s in visual.analytical_sort
    ))

    return (
        visual.type,
        tuple(roles),
        filters,
        analytical_sort,
    )
```

---

## 6. Normalisation

La signature ne doit pas dépendre :

- de l'identifiant technique du visuel ;
- de l'identifiant de page ;
- de l'ordre JSON ;
- du formatage du JSON ;
- de `nativeQueryRef` si `queryRef` permet une référence technique plus stable ;
- de la couleur ;
- de la taille ;
- de la position ;
- du titre.

Ces éléments peuvent toutefois être conservés pour le contexte de revue.

---

## 7. Détection des candidats

```python
def detect_duplicate_candidates(report):
    groups = {}

    for page in report.pages:
        for visual in page.visuals:
            if visual.is_group_container:
                continue

            try:
                signature = build_visual_signature(
                    visual,
                    report.context,
                )
            except VisualSignatureError as exc:
                report.unresolved_visuals.append({
                    "page": page.name,
                    "visual": visual.id,
                    "reason": str(exc),
                })
                continue

            if signature is None:
                report.out_of_scope_visuals.append(
                    visual.id
                )
                continue

            groups.setdefault(signature, []).append({
                "page_id": page.id,
                "page_name": page.name,
                "visual_id": visual.id,
                "visual_type": visual.type,
                "title": visual.title,
                "position": visual.position,
            })

    return [
        {
            "candidate_id": make_candidate_id(sig),
            "signature": sig,
            "occurrences": occurrences,
        }
        for sig, occurrences in groups.items()
        if len(occurrences) >= 2
    ]
```

Une signature identique produit :

```text
duplicate_candidate = true
```

et non :

```text
rule_status = KO
```

---

## 8. Contexte de revue d'un candidat

Pour chaque groupe candidat, le moteur fournit au reviewer :

```text
pages concernées
page visible / masquée
titres des visuels
type de visuel
champs / mesures
filtres
position
navigation éventuelle
groupe éventuel
même page ou pages différentes
```

Exemple :

```json
{
  "candidate_id": "DUP-004",
  "same_page": false,
  "visual_type": "card",
  "measure": "MEASURE[Nb_Responses]",
  "filters": [],
  "occurrences": [
    {
      "page": "Overview",
      "visual_id": "..."
    },
    {
      "page": "Usage",
      "visual_id": "..."
    }
  ]
}
```

---

## 9. Décision contextuelle

Chaque candidat reçoit l'une des décisions suivantes.

### `JUSTIFIED`

Une justification observable ou déclarée explique la répétition.

Exemples :

- KPI de contexte volontairement repris sur plusieurs pages ;
- page de synthèse et page de détail ;
- navigation/documentation du rapport indiquant un rôle différent.

### `REDUNDANT_CONFIRMED`

La redondance est explicitement confirmée.

Exemples :

- copie de test oubliée ;
- doublon déclaré inutile ;
- politique d'entreprise interdisant explicitement ce cas précis et conditions remplies ;
- revue contextuelle/humaine concluant que les deux visuels remplissent le même rôle sans justification.

### `UNRESOLVED`

La signature est identique mais l'intention ne peut pas être déterminée de manière fiable.

---

## 10. Politique déterministe optionnelle

Une entreprise peut définir une règle stricte, par exemple :

```yaml
bp_41:
  forbid_identical_signature_same_page: true
```

Dans ce cas uniquement, un groupe peut produire directement `KO` si toutes les conditions techniques de la politique sont démontrées.

Exemple :

```text
même page
+ même signature
+ règle COMPANY_POLICY explicite
-> KO
```

Sans cette politique :

```text
même page + même signature
-> candidat à revoir
```

---

## 11. Décision du statut de la règle

```python
def evaluate_bp41(
    candidates,
    reviews,
    unresolved_visuals,
    company_policy,
):
    if not candidates:
        if unresolved_visuals:
            return "NA"

        return "OK"

    decisions = []

    for candidate in candidates:
        policy_decision = evaluate_company_policy(
            candidate,
            company_policy,
        )

        if policy_decision is not None:
            decisions.append(policy_decision)
            continue

        review = reviews.get(candidate["candidate_id"])

        if review is None:
            decisions.append("UNRESOLVED")
        else:
            decisions.append(review.decision)

    if "REDUNDANT_CONFIRMED" in decisions:
        return "KO"

    if "UNRESOLVED" in decisions:
        return "NA"

    if all(d == "JUSTIFIED" for d in decisions):
        return "OK"

    return "NA"
```

---

## 12. Matrice de décision

| Situation | Statut |
|---|---|
| aucun candidat et tous les visuels comparables analysés | `OK` |
| aucun candidat mais certains visuels analytiques illisibles pouvant masquer un doublon | `NA` |
| candidat(s) détecté(s), pas encore qualifié(s) | `NA` |
| tous les candidats sont explicitement justifiés | `OK` |
| au moins un candidat est confirmé redondant | `KO` |
| politique d'entreprise interdit explicitement un cas et le cas est démontré | `KO` |
| uniquement visuels non analytiques | `NA` |

---

## 13. Pourquoi l'ancienne logique est insuffisante

Cette logique :

```python
if duplicate_groups:
    rule_status = "KO"
```

est trop forte.

Elle confond :

```text
égalité technique
```

et :

```text
absence de valeur métier
```

Le checker déterministe peut prouver que deux visuels ont la même signature.

Il ne peut pas prouver à lui seul qu'ils n'ont aucune raison d'être présents à deux endroits.

---

## 14. Résultat attendu

Exemple avec candidats non résolus :

```json
{
  "rule_id": "BP-41",
  "rule_status": "NA",
  "duplicate_candidates": [
    {
      "candidate_id": "DUP-004",
      "visual_type": "card",
      "occurrences": [
        {
          "page": "Overview",
          "visual_id": "5ab2..."
        },
        {
          "page": "Usage",
          "visual_id": "2c47..."
        }
      ],
      "review_status": "UNRESOLVED"
    }
  ],
  "diagnostic_level": "WARNING"
}
```

Exemple après revue :

```json
{
  "rule_id": "BP-41",
  "rule_status": "KO",
  "duplicate_candidates": [
    {
      "candidate_id": "DUP-004",
      "review_status": "REDUNDANT_CONFIRMED",
      "reason": "Copie de test oubliée sans différence fonctionnelle"
    }
  ]
}
```

---

## 15. Preuve obligatoire

Chaque candidat doit conserver :

```text
candidate_id
visual_type
canonical_signature
page_id
page_name
visual_id
title
fields
measures
filters
sorts
review_status
review_source
review_evidence
```

Un `KO` doit disposer de :

```text
REDUNDANT_CONFIRMED
```

ou d'une violation explicite d'une `COMPANY_POLICY`.

Sans cela :

```text
NA
```

---

## 16. Résumé

```text
RÈGLE BP-41

POUR chaque visuel analytique
    CONSTRUIRE une signature canonique
FIN

REGROUPER les signatures identiques

SI aucun candidat
    SI analyse complète
        -> OK
    SINON
        -> NA

SINON
    POUR chaque candidat
        SI politique explicite violée
            -> REDUNDANT_CONFIRMED

        SINON
            DEMANDER / CONSOMMER une qualification contextuelle
    FIN

    SI au moins un REDUNDANT_CONFIRMED
        -> KO

    SINON SI au moins un UNRESOLVED
        -> NA

    SINON
        -> OK
```

Le rôle de Python est de détecter les candidats de manière reproductible.

Le rôle du reviewer contextuel ou humain est de déterminer si la duplication est réellement injustifiée.
